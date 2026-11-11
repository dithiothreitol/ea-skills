"""Command line entry point: ``python -m easkills <command>``.

Commands are the deterministic half of the pipeline -- the part skills call instead
of reasoning about. Exit code 1 means an error-severity finding, so the same
commands work as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (
    airegister,
    alignment,
    analyst,
    aoef,
    check as check_mod,
    contextpack,
    docgen,
    documents as documents_mod,
    dora,
    dora_its,
    diff as diff_mod,
    dsl,
    export as export_mod,
    facts as facts_mod,
    gdpr as gdpr_mod,
    genschema,
    govern,
    impact as impact_mod,
    importer,
    intake,
    maturity as maturity_mod,
    oracle,
    promote as promote_mod,
    propose as propose_mod,
    query as query_mod,
    readiness as readiness_mod,
    reference as reference_mod,
    render as render_mod,
    redact as redact_mod,
    reports,
    review as review_mod,
    scaffold,
    score as score_mod,
    security as security_mod,
    serve as serve_mod,
    tabular,
    timeline,
    ui,
    validate as validate_mod,
)


def _ok(message: str) -> str:
    return f"{ui.green(ui.check())} {message}"


def _error(message: str) -> str:
    return f"{ui.red(ui.bold('ERROR'))}   {message}"


def _oracle_intact() -> bool:
    """Verify the oracle pins before consuming oracle data.

    ``validate`` reports drift as an ``ORACLE001`` finding inside its report, but the
    build and generation commands have no report to put it in -- and one of them
    (``gen-schema``) writes the authoring contract *from* the oracle. Without this
    guard, a tampered or line-ending-mangled oracle file would silently produce
    artifacts and schemas, which is precisely the failure the pins exist to catch.
    """
    try:
        failed = oracle.failed_checksums()
    except oracle.OracleError as exc:
        print(_error(str(exc)))
        return False
    if not failed:
        return True
    print(_error("ORACLE001  vendored oracle does not match its pinned SHA-256 sums:"))
    for result in failed:
        actual = result.actual[:16] if result.actual else "missing file"
        print(f"         {result.name}: pinned {result.expected[:16]}..., found {actual}")
    print("\nRe-pin (`python -m easkills pin-oracle`) only for a deliberate, reviewed oracle upgrade.")
    return False


def _parse_as_of(value: str | None):
    from datetime import date, datetime

    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    parser.add_argument(
        "--zone",
        choices=["approved", "staging"],
        default="approved",
        help="which zone to read; governance metadata is mandatory in 'approved'",
    )


def _add_lang(parser: argparse.ArgumentParser) -> None:
    from . import i18n

    parser.add_argument(
        "--lang",
        choices=i18n.LANGUAGES,
        default=i18n.DEFAULT,
        help="language of the generated document (terminal output stays English)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="easkills", description="Deterministic tooling for the EA skills pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="run the three-layer validator")
    _add_common(p_validate)
    p_validate.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_validate.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures too",
    )

    p_compile = sub.add_parser("compile", help="compile the DSL to ArchiMate Open Exchange XML")
    _add_common(p_compile)
    p_compile.add_argument("--out", type=Path, help="output file (default: <root>/build/model.xml)")
    p_compile.add_argument(
        "--skip-validation",
        action="store_true",
        help="compile even if the validator reports errors (not recommended)",
    )

    p_render = sub.add_parser("render", help="render views to deterministic SVG")
    _add_common(p_render)
    p_render.add_argument("--out", type=Path, help="output directory (default: <root>/docs/views)")
    p_render.add_argument(
        "--heatmap",
        metavar="PROPERTY",
        help="colour each view by this property instead of by layer, written beside it as "
        "<view>.heatmap-<property>.svg",
    )

    p_export = sub.add_parser("export", help="write views as PlantUML (ArchiMate notation) or Mermaid text")
    _add_common(p_export)
    p_export.add_argument("--format", dest="format", choices=export_mod.FORMATS, required=True, help="diagram language")
    p_export.add_argument("--view", help="one view id (default: every view)")
    p_export.add_argument(
        "--out", type=Path, help="output directory (default: print one --view, else <root>/build/diagrams)"
    )

    p_docs = sub.add_parser(
        "docs", help="generate the architecture description (ISO 42010 shape) from the approved zone"
    )
    p_docs.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_docs.add_argument("--out", type=Path, help="output file (default: <root>/docs/architecture-description.md)")
    p_docs.add_argument(
        "--skip-validation",
        action="store_true",
        help="generate even if the validator reports errors (not recommended)",
    )
    _add_lang(p_docs)

    p_import = sub.add_parser(
        "import", help="import an ArchiMate Open Exchange file into model/staging/ (brownfield adoption)"
    )
    p_import.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_import.add_argument("--file", type=Path, required=True, help="the exchange XML to import")
    p_import.add_argument(
        "--out",
        type=Path,
        help="write one file here instead of splitting into model/staging/ by layer "
        "(a single file cannot be promoted in slices)",
    )
    p_import.add_argument(
        "--ids",
        choices=("names", "identifiers"),
        default="names",
        help="derive DSL slugs from element names (default; readable) or from XML identifiers (round-trip)",
    )
    p_import.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_csv = sub.add_parser(
        "intake-csv",
        help="convert a tabular export (CSV/Excel) into a citable source document",
    )
    p_csv.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_csv.add_argument("--file", type=Path, required=True, help="the CSV to convert")
    p_csv.add_argument(
        "--out", type=Path, help="target markdown file (default: <sourcesDir>/<name>.md)"
    )
    p_csv.add_argument(
        "--overwrite", action="store_true", help="replace an existing converted document"
    )
    p_csv.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_doc = sub.add_parser(
        "intake-doc",
        help="convert a PDF, Word, PowerPoint or Excel file into a citable source document",
    )
    p_doc.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_doc.add_argument("--file", type=Path, required=True, help="the .pdf, .docx, .pptx or .xlsx to convert")
    p_doc.add_argument("--out", type=Path, help="target markdown file (default: <sourcesDir>/<name>.md)")
    p_doc.add_argument("--overwrite", action="store_true", help="replace an existing converted document")
    p_doc.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_rtm = sub.add_parser(
        "rtm", help="requirement traceability: what each obligation binds, what meets it, what evidences it"
    )
    _add_common(p_rtm)
    p_rtm.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_rtm.add_argument("--out", type=Path, help="write the matrix as a table (.csv for a spreadsheet, else markdown)")

    p_glossary = sub.add_parser(
        "glossary", help="the entity table as a glossary, with the facts and model elements behind each term"
    )
    p_glossary.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_glossary.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_glossary.add_argument(
        "--out", type=Path, help="write the glossary as a table (.csv for a spreadsheet, else markdown)"
    )

    p_redact = sub.add_parser(
        "intake-redact", help="the committable copy of a sensitive text source, by a human-authored replacement map"
    )
    p_redact.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_redact.add_argument("--file", type=Path, required=True, help="the original .md or .txt (kept outside git)")
    p_redact.add_argument("--map", dest="mapping", type=Path, required=True, help="YAML with `replacements: [{find, replace}]`")
    p_redact.add_argument("--out", type=Path, help="target file (default: <sourcesDir>/<name>.md)")
    p_redact.add_argument("--overwrite", action="store_true", help="replace an existing redacted copy")
    p_redact.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_init = sub.add_parser("init", help="scaffold a new architecture repository, pinned to this release")
    p_init.add_argument("directory", type=Path, help="where to write it (absent or empty)")

    p_doctor = sub.add_parser("doctor", help="what this machine and repository are missing, one line each")
    p_doctor.add_argument(
        "--root", type=Path, default=None, help="also check this architecture repository (default: the machine only)"
    )

    p_review = sub.add_parser(
        "review", help="the review sheet: every staged claim beside its evidence, weakest first"
    )
    p_review.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_review.add_argument(
        "--file",
        dest="files",
        type=Path,
        action="append",
        help="a staging file to review (repeatable; default: everything promote would move)",
    )
    p_review.add_argument("--out", type=Path, help="write the sheet to this markdown file instead of stdout")

    p_promote = sub.add_parser(
        "promote", help="move staging files into approved after the promotion gate passes"
    )
    p_promote.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_promote.add_argument(
        "--file",
        dest="files",
        type=Path,
        action="append",
        help="a staging file to promote (repeatable; default: everything in model/staging/)",
    )
    p_promote.add_argument("--dry-run", action="store_true", help="run the gate and show the plan, move nothing")
    p_promote.add_argument(
        "--approved-by",
        help="who signs this promotion (required unless --dry-run): written into the approval record",
    )
    p_promote.add_argument(
        "--as-of",
        help="the signing date, YYYY-MM-DD (required unless --dry-run): the record's date and the gate's",
    )
    p_promote.add_argument(
        "--seal-existing",
        action="store_true",
        help="write the initial approval record for what model/approved/ already holds; moves nothing, runs once",
    )

    p_gov = sub.add_parser(
        "validate-gov", help="validate the governance log and standards base (SIB/DEC/DISP/COMP rules)"
    )
    p_gov.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_gov.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_gov.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    p_gov.add_argument("--as-of", dest="as_of", help="evaluate expiries against this date (YYYY-MM-DD)")

    for name, help_text in (
        ("staleness", "review-age report over the approved model"),
        ("kpi", "model-quality and portfolio metrics"),
        ("debt", "EA-debt register from deterministic smell queries"),
        ("conformance", "ISO 42010 Clause 6 conformance checklist (checkable subset)"),
        ("correspondences", "ISO 42010 §6.9 correspondences across the AD, and their rules"),
        ("roadmap", "plateaus, gaps, and the portfolio decisions no plateau carries"),
        ("delta", "what the fact register knows that the approved model does not"),
    ):
        p_report = sub.add_parser(name, help=help_text)
        p_report.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
        p_report.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
        if name != "delta":
            p_report.add_argument("--as-of", dest="as_of", help="evaluate against this date (YYYY-MM-DD)")
        if name == "conformance":
            p_report.add_argument("--strict", action="store_true", help="exit 1 if any clause fails")
        if name == "kpi":
            p_report.add_argument(
                "--snapshot",
                action="store_true",
                help="also commit-ready: write governance-log/metrics/<as-of>.json (requires --as-of)",
            )

    p_trend = sub.add_parser("trend", help="the KPI series from committed snapshots, and what regressed")
    p_trend.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_trend.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_trend.add_argument("--last", type=int, metavar="N", help="show only the last N snapshots (the JSON keeps all)")
    p_trend.add_argument(
        "--strict", action="store_true", help="exit 1 if any metric regressed since the previous snapshot"
    )

    p_diff = sub.add_parser("diff", help="what changes between two plateaus, or since a git commit")
    p_diff.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    mode = p_diff.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plateau", nargs=2, metavar=("FROM", "TO"), help="two plateau ids")
    mode.add_argument("--ref", metavar="GIT-REF", help="a commit, tag or branch to compare the approved zone with")
    p_diff.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_query = sub.add_parser("query", help="find elements by type, property and relationship hops (read-only)")
    _add_common(p_query)
    p_query.add_argument("--type", dest="types", action="append", metavar="TYPE", help="element type (repeatable)")
    p_query.add_argument(
        "--where",
        action="append",
        metavar="COND",
        help="key=value, key!=value, key~token (membership), key= (absent); repeatable, all must hold",
    )
    p_query.add_argument("--from", dest="start", metavar="ID", help="walk from this element")
    p_query.add_argument("--hops", type=int, default=1, help="steps from --from (default 1)")
    p_query.add_argument(
        "--rel", dest="relations", action="append", metavar="TYPE",
        help="relationship type to walk, or appliesTo (repeatable; default all)",
    )
    p_query.add_argument("--direction", choices=query_mod.DIRECTIONS, default="both", help="which way to walk")
    p_query.add_argument("--show", action="append", metavar="KEY", help="add a property column (repeatable)")
    p_query.add_argument("--json", dest="json_out", type=Path, help="also write the result as JSON")

    p_serve = sub.add_parser("serve", help="serve the approved model as a read-only MCP server over stdio")
    p_serve.add_argument(
        "--root",
        type=Path,
        help="where to look for the repository (default: $CLAUDE_PROJECT_DIR, else cwd; the nearest "
        "directory upwards holding ea.config.yaml is used)",
    )

    p_context = sub.add_parser(
        "context", help="generate an agent context pack for one element or capability (AD-09)"
    )
    p_context.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_context.add_argument("--scope", required=True, help="element id to scope the pack to")
    p_context.add_argument("--out", type=Path, help="write to a file instead of stdout")
    p_context.add_argument("--as-of", dest="as_of", help="evaluate freshness against this date (YYYY-MM-DD)")

    p_impact = sub.add_parser(
        "impact", help="blast radius of a change to one element, with the Phase H stakeholder count"
    )
    p_impact.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_impact.add_argument("--scope", required=True, help="element id the change is about")
    p_impact.add_argument(
        "--zone",
        choices=["approved", "staging"],
        default="approved",
        help="which zone to read; 'staging' answers what a *proposed* model would touch",
    )
    p_impact.add_argument(
        "--depth", type=int, help="stop after N hops (default: unbounded, the whole reachable set)"
    )
    p_impact.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_impact.add_argument("--as-of", dest="as_of", help="evaluate dispensation expiry against this date")

    p_check = sub.add_parser(
        "check", help="lint a consuming repository against the standards its EA element claims (AD-09)"
    )
    p_check.add_argument("--root", type=Path, default=Path.cwd(), help="EA repository root (default: cwd)")
    p_check.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository to check (default: cwd)"
    )
    p_check.add_argument("--scope", required=True, help="element id this repository implements")
    p_check.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_check.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    p_check.add_argument("--as-of", dest="as_of", help="evaluate dispensation expiry against this date")
    p_check.add_argument(
        "--sbom",
        dest="sboms",
        type=Path,
        action="append",
        help="a CycloneDX or SPDX JSON document to read as well (repeatable)",
    )

    p_exposure = sub.add_parser(
        "exposure", help="what an attacker holding each publicly exposed element could reach"
    )
    _add_common(p_exposure)
    p_exposure.add_argument("--depth", type=int, help="stop after N hops (default: unbounded)")
    p_exposure.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

    p_score = sub.add_parser("score", help="score a candidate repository against a golden one (P/R/F1)")
    p_score.add_argument("--root", type=Path, default=Path.cwd(), help="candidate repository root (default: cwd)")
    p_score.add_argument("--gold", type=Path, required=True, help="golden repository root")
    p_score.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_score.add_argument(
        "--min-f1",
        type=float,
        metavar="PCT",
        help="exit 1 if the minimum F1 across categories falls below this percentage (0-100), "
        "or if the candidate fails its own validation gates",
    )

    p_facts = sub.add_parser("validate-facts", help="validate the fact register (facts/register + entities)")
    p_facts.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_facts.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_facts.add_argument("--strict", action="store_true", help="treat warnings as failures too")

    p_chunk = sub.add_parser("chunk", help="split source documents into deterministic extraction chunks")
    p_chunk.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_chunk.add_argument("--file", type=Path, help="one source file (default: every file under facts/sources)")
    p_chunk.add_argument("--max-chars", type=int, default=intake.DEFAULT_MAX_CHARS, help="chunk budget in characters")
    p_chunk.add_argument("--json", dest="json_out", action="store_true", help="print chunks as JSON")

    p_coverage = sub.add_parser("coverage", help="report which parts of the sources produced no facts")
    p_coverage.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_coverage.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_coverage.add_argument(
        "--min-coverage",
        type=float,
        metavar="PCT",
        help="exit 1 if overall coverage falls below this percentage (0-100)",
    )

    p_readiness = sub.add_parser(
        "readiness", help="per-layer definition of done: the checkpoints each layer has not met"
    )
    _add_common(p_readiness)
    p_readiness.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_readiness.add_argument(
        "--strict", action="store_true", help="exit 1 while any checkpoint is open (completeness gate)"
    )

    p_align = sub.add_parser(
        "align", help="two-way coverage of the model against the reference models in reference/"
    )
    _add_common(p_align)
    p_align.add_argument(
        "--reference",
        dest="reference",
        action="append",
        metavar="NAME",
        help="reference pack to align against (repeatable; default: every pack under reference/)",
    )
    p_align.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_align.add_argument("--strict", action="store_true", help="treat warnings (gaps) as failures too")
    p_align.add_argument(
        "--min-coverage",
        type=float,
        metavar="PCT",
        help="exit 1 if reference coverage falls below this percentage (0-100)",
    )

    p_dora = sub.add_parser(
        "dora-register", help="generate the DORA Register of Information from the approved model"
    )
    p_dora.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_dora.add_argument("--out", type=Path, help="write the register document here (default: print the findings)")
    p_dora.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_dora.add_argument("--as-of", dest="as_of", metavar="YYYY-MM-DD", help="evaluate waiver expiry against this date")
    p_dora.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    p_dora.add_argument(
        "--format",
        dest="format",
        choices=("markdown", "its-csv"),
        default="markdown",
        help="markdown document (default), or one CSV per ITS template into the --out directory",
    )
    _add_lang(p_dora)

    p_ai_act = sub.add_parser(
        "ai-act-register", help="generate the EU AI Act system inventory from the approved model"
    )
    p_ai_act.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_ai_act.add_argument(
        "--out", type=Path, help="write the inventory document here (default: print the findings)"
    )
    p_ai_act.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_ai_act.add_argument(
        "--as-of", dest="as_of", metavar="YYYY-MM-DD", help="evaluate waiver expiry against this date"
    )
    p_ai_act.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    _add_lang(p_ai_act)

    p_gdpr = sub.add_parser(
        "gdpr-register", help="generate the GDPR Art. 30 record of processing activities from the approved model"
    )
    p_gdpr.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_gdpr.add_argument("--out", type=Path, help="write the record here (default: print the findings)")
    p_gdpr.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_gdpr.add_argument("--as-of", dest="as_of", metavar="YYYY-MM-DD", help="evaluate waiver expiry against this date")
    p_gdpr.add_argument("--strict", action="store_true", help="treat warnings as failures too")
    _add_lang(p_gdpr)

    p_maturity = sub.add_parser(
        "maturity", help="level 1-5 per dimension from measured signals, with the items blocking the next"
    )
    p_maturity.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_maturity.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_maturity.add_argument("--as-of", dest="as_of", metavar="YYYY-MM-DD", help="evaluate against this date")

    p_propose = sub.add_parser(
        "propose", help="turn findings into skeletons: staged requirements and work packages, or open questions"
    )
    p_propose.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_propose.add_argument(
        "--from",
        dest="source",
        choices=propose_mod.SOURCES,
        required=True,
        help="which report's findings to propose from",
    )
    # Required, unlike everywhere else. Every other command *reports* a date; this one
    # writes it into a file that gets committed, and a wall-clock stamp there would make
    # the output differ between two runs of an unchanged repository.
    p_propose.add_argument(
        "--as-of",
        dest="as_of",
        metavar="YYYY-MM-DD",
        required=True,
        help="the date recorded in every generated rationale (required: the output is a committed file)",
    )
    p_propose.add_argument(
        "--reference",
        dest="reference",
        action="append",
        metavar="NAME",
        help="restrict `--from align` to these packs (repeatable; default: every pack present)",
    )
    p_propose.add_argument("--out", type=Path, help="write here instead of the default staging file")
    p_propose.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_propose.add_argument("--dry-run", action="store_true", help="show what would be proposed, write nothing")
    p_propose.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print the file it would write, exactly, and write nothing (for a shell that may not write)",
    )

    p_pin_ref = sub.add_parser(
        "pin-reference", help="rewrite a reference pack's SHA256SUMS after a deliberate upgrade"
    )
    p_pin_ref.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_pin_ref.add_argument("--reference", dest="reference", metavar="NAME", help="the pack under reference/ to pin")
    # For a pack that does not sit under a repository's `reference/` -- the open library
    # in this repository is one (`references/`, plural, because it is a library to copy
    # *from*, not a pack to align against).
    p_pin_ref.add_argument("--dir", dest="directory", type=Path, help="the pack directory to pin, by path")

    sub.add_parser("gen-schema", help="regenerate the JSON Schemas under schema/ from the oracle")
    sub.add_parser("pin-oracle", help="rewrite oracle/SHA256SUMS from the current oracle files")
    sub.add_parser("oracle-info", help="print oracle version and coverage")

    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_mod.validate(args.root.resolve(), zone=args.zone)
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def cmd_compile(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not _oracle_intact():
        return 1
    if not args.skip_validation:
        report = validate_mod.validate(root, zone=args.zone)
        if not report.ok:
            print(report.render())
            print("\nRefusing to compile a model with validation errors (use --skip-validation to override).")
            return 1
    try:
        result = aoef.compile_model(root, zone=args.zone, out=args.out)
    except aoef.CompileError as exc:
        print(_error(str(exc)))
        return 1
    print(
        _ok(
            f"Compiled {result.elements} elements, {result.relationships} relationships, "
            f"{result.views} view(s) {ui.arrow()} {ui.bold(str(result.path))}"
        )
    )
    if result.schema_errors:
        print("\nOpen Exchange XSD validation FAILED:")
        for error in result.schema_errors[:20]:
            print(f"  {error}")
        return 1
    print(_ok("Open Exchange XSD validation passed."))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not _oracle_intact():
        return 1
    try:
        result = render_mod.render_all(root, zone=args.zone, out_dir=args.out, heatmap=args.heatmap)
    except render_mod.RenderError as exc:
        print(_error(str(exc)))
        return 1
    for view_id, path in result.views:
        print(_ok(f"Rendered {ui.bold(view_id)} {ui.arrow()} {path}"))
    if not result.views:
        print("No views to render.")
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not _oracle_intact():
        return 1
    if not args.skip_validation:
        report = validate_mod.validate(root, zone="approved")
        if not report.ok:
            print(report.render())
            print("\nRefusing to document a model with validation errors (use --skip-validation to override).")
            return 1
    try:
        result = docgen.generate(root, out=args.out, lang=args.lang)
    except render_mod.RenderError as exc:
        print(_error(str(exc)))
        return 1
    print(_ok(f"Rendered {len(result.views_rendered)} view(s); wrote {ui.bold(str(result.path))}"))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    if not _oracle_intact():
        return 1
    try:
        report = importer.import_exchange(
            args.root.resolve(), source=args.file, out=args.out, ids=args.ids
        )
    except importer.ImportRefusal as exc:
        print(_error(str(exc)))
        return 1
    _emit_report(args, report.as_dict(), _render_import(report))
    return 0


def _render_import(report: importer.ImportReport) -> str:
    lines = [
        _ok(
            f"Imported {report.elements} element(s), {report.relationships} relationship(s), "
            f"{report.views} view(s) into {len(report.targets)} file(s)"
        ),
        ui.dim(f"source: {report.source} (sha256 {report.sha256[:16]}); ids: {report.ids}"),
        *(f"  {ui.bold(target)}" for target in report.targets),
    ]
    if report.skipped:
        lines.append("")
        lines.append(ui.yellow(ui.bold(f"Not imported ({len(report.skipped)}):")))
        for item in report.skipped:
            lines.append(f"  {item['kind']:<13} {ui.bold(item['identifier'])} {ui.dim(item['reason'])}")
    if report.renamed:
        lines.append("")
        lines.append(ui.bold(f"Identifiers renamed ({len(report.renamed)}):"))
        for item in report.renamed[:20]:
            lines.append(f"  {item['from']} {ui.dim('->')} {item['to']}")
        if len(report.renamed) > 20:
            lines.append(ui.dim(f"  ... and {len(report.renamed) - 20} more (full list in --json)"))
    for note in report.notes:
        lines.append(ui.dim(f"note: {note}"))
    if report.xsd_errors:
        lines.append(
            ui.yellow(
                f"note: the source does not validate against the Open Exchange XSD "
                f"({len(report.xsd_errors)} finding(s)); imported best-effort"
            )
        )
    lines += [
        "",
        ui.dim(
            "The import is a staging proposal: run `validate --zone staging` to see what it "
            "still lacks (owners, review dates, evidence), then promote deliberately -- one "
            "element file at a time as owners vouch for it, and `relations.yaml` once both "
            "endpoints are approved."
        ),
    ]
    return "\n".join(lines)


def cmd_intake_csv(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config = dsl.load_config(root)
    sources_dir = root / str(config.get("sourcesDir", "facts/sources"))
    target = args.out or (sources_dir / f"{args.file.stem}.md")
    try:
        report = tabular.convert(args.file, target, overwrite=args.overwrite)
    except tabular.TabularError as exc:
        print(_error(str(exc)))
        return 1
    delimiter = "tab" if report.delimiter == "\t" else report.delimiter
    lines = [
        _ok(
            f"Converted {report.rows} row(s) x {len(report.columns)} column(s) -> "
            f"{ui.bold(report.target)}"
        ),
        ui.dim(
            f"source: {report.source} (sha256 {report.sha256[:16]}); read as {report.encoding}, "
            f"delimiter '{delimiter}'"
        ),
        ui.dim("columns: " + ", ".join(report.columns)),
    ]
    if report.ragged:
        lines.append(
            ui.yellow(
                f"{len(report.ragged)} ragged row(s) (cell count differs from the header): "
                + ", ".join(str(item["row"]) for item in report.ragged)
            )
        )
    if report.flattened:
        lines.append(
            ui.dim(
                f"{len(report.flattened)} row(s) had line breaks inside a cell; flattened so "
                "each row stays one quotable line"
            )
        )
    lines += [
        "",
        ui.dim(
            "Commit the CSV next to the converted document: the SHA-256 in the header is what "
            "ties a verified quote back to the original bytes. Extract facts from it with "
            "ea-intake; nothing here interpreted a single column."
        ),
    ]
    _emit_report(args, report.as_dict(), "\n".join(lines))
    return 0


def cmd_intake_doc(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config = dsl.load_config(root)
    sources_dir = root / str(config.get("sourcesDir", "facts/sources"))
    target = args.out or (sources_dir / f"{args.file.stem}.md")
    try:
        report = documents_mod.convert(args.file, target, overwrite=args.overwrite)
    except documents_mod.DocumentError as exc:
        print(_error(str(exc)))
        return 1
    lines = [
        _ok(f"Converted a {report.kind} ({report.sections} section(s), {report.lines} line(s)) -> {ui.bold(report.target)}"),
        ui.dim(f"source: {report.source} (sha256 {report.sha256[:16]}); read with {report.library}"),
    ]
    for note in report.notes:
        lines.append(ui.yellow(f"note: {note}"))
    lines += [
        "",
        ui.dim(
            "Commit the original next to the converted document: the SHA-256 in the header is "
            "what ties a verified quote back to the bytes it came from. Extract facts from it "
            "with ea-intake; nothing here interpreted a single heading, table or slide."
        ),
    ]
    _emit_report(args, report.as_dict(), "\n".join(lines))
    return 0


def cmd_rtm(args: argparse.Namespace) -> int:
    matrix = analyst.rtm(args.root.resolve(), zone=args.zone)
    _emit_report(args, matrix.as_dict(), analyst.render_rtm(matrix))
    if args.out:
        analyst.write_table(args.out, "Requirement traceability", analyst.rtm_table(matrix))
        print(_ok(f"Matrix written to {args.out}"))
    return 0


def cmd_glossary(args: argparse.Namespace) -> int:
    data = analyst.glossary(args.root.resolve())
    _emit_report(args, data.as_dict(), analyst.render_glossary(data))
    if args.out:
        analyst.write_table(args.out, "Glossary", analyst.glossary_table(data))
        print(_ok(f"Glossary written to {args.out}"))
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    try:
        today = _parse_as_of(args.as_of)
    except ValueError:
        print(_error(f"--as-of must be a real date in YYYY-MM-DD form, got {args.as_of!r}"))
        return 1
    try:
        if args.seal_existing:
            if args.files:
                print(_error("--seal-existing seals what the approved zone already holds; it takes no --file"))
                return 1
            result = promote_mod.seal_existing(
                args.root.resolve(), args.approved_by, args.as_of, dry_run=args.dry_run, today=today
            )
        else:
            result = promote_mod.promote(
                args.root.resolve(),
                files=args.files,
                dry_run=args.dry_run,
                today=today,
                approved_by=args.approved_by,
                as_of=args.as_of,
            )
    except promote_mod.PromoteError as exc:
        print(_error(str(exc)))
        return 1
    print(result.render())
    return 0 if result.ok else 1


def cmd_intake_redact(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    config = dsl.load_config(root)
    sources_dir = root / str(config.get("sourcesDir", "facts/sources"))
    target = args.out or (sources_dir / f"{args.file.stem}.md")
    try:
        report = redact_mod.redact(args.file, args.mapping, target, overwrite=args.overwrite)
    except (redact_mod.RedactError, UnicodeDecodeError) as exc:
        print(_error(str(exc)))
        return 1
    lines = [
        _ok(f"Redacted {report.replacements} occurrence(s) by {report.rules} rule(s) -> {ui.bold(report.target)}"),
        ui.dim(f"original: sha256 {report.sha256[:16]}; neither its name nor the map is recorded in the copy"),
    ]
    if args.out is None:
        lines.append(
            ui.yellow(
                f"note: the copy is named after the original ({target.name}); if that name is itself "
                "sensitive, re-run with --out and delete this file before committing"
            )
        )
    for number in report.unmatched:
        lines.append(
            ui.yellow(f"note: rule {number} matched nothing -- a name spelled differently in the source is a name left in")
        )
    lines += [
        "",
        ui.dim(
            "Commit the redacted copy, never the original or the map. Quotes are verified against the copy; "
            "the digest in its header is what ties it to the original."
        ),
    ]
    _emit_report(args, report.as_dict(), "\n".join(lines))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    target = args.directory.resolve()
    try:
        written = scaffold.init(target)
    except scaffold.ScaffoldError as exc:
        print(_error(str(exc)))
        return 1
    from . import __version__

    print(_ok(f"Scaffolded {len(written)} file(s) into {ui.bold(str(target))}, pinned to ea-skills {__version__}"))
    print(
        "\n".join(
            [
                "",
                "Next:",
                f"  cd {target}",
                "  git init && git add -A && git commit -m \"Scaffold the architecture repository\"",
                "  edit ea.config.yaml (name, documentation) and .github/CODEOWNERS (your board)",
                "  easkills doctor --root .",
                "",
                ui.dim(
                    "The workflow in .github/workflows/ runs the gates on every push and a nightly "
                    "check against today's date; CODEOWNERS makes the signed zone need a reviewer."
                ),
            ]
        )
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = args.root.resolve() if args.root else None
    checks = scaffold.doctor(root)
    marks = {"ok": ui.green("ok  "), "warn": ui.yellow("warn"), "fail": ui.red("FAIL")}
    from . import __version__

    print(ui.bold(f"ea-skills {__version__} doctor") + (f" -- {root}" if root else ""))
    for check in checks:
        print(f"  {marks[check.status]}  {check.name:<15} {check.detail}")
    failed = sum(1 for c in checks if c.status == "fail")
    warned = sum(1 for c in checks if c.status == "warn")
    print("")
    print(f"{failed} failure(s), {warned} warning(s)" + ("" if failed else " -- nothing that makes a gate wrong"))
    return 1 if failed else 0


def cmd_review(args: argparse.Namespace) -> int:
    try:
        sheet = review_mod.review(args.root.resolve(), files=args.files)
    except review_mod.ReviewError as exc:
        print(_error(str(exc)))
        return 1
    document = review_mod.markdown(sheet)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(document, encoding="utf-8", newline="\n")
        print(_ok(f"Review sheet for {len(sheet.claims)} staged claim(s) written to {args.out}"))
    else:
        print(document, end="")
    return 0


def cmd_validate_gov(args: argparse.Namespace) -> int:
    report = govern.validate_governance(args.root.resolve(), today=_parse_as_of(args.as_of))
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def _emit_report(args: argparse.Namespace, data: dict, rendered: str) -> None:
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")


def cmd_staleness(args: argparse.Namespace) -> int:
    data = reports.staleness(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_staleness(data))
    return 0


def cmd_kpi(args: argparse.Namespace) -> int:
    if args.snapshot and not args.as_of:
        # The file name is the date. A wall-clock date there would make two runs of an
        # unchanged repository disagree, which a committed record must never do.
        print(_error("--snapshot needs --as-of: the snapshot is named by its date"))
        return 1
    root = args.root.resolve()
    data = reports.kpi(root, today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_kpi(data))
    if args.snapshot:
        try:
            path, written = timeline.write_snapshot(root, data)
        except timeline.TimelineError as exc:
            print(_error(str(exc)))
            return 1
        print(_ok(f"Snapshot {'written to' if written else 'unchanged at'} {path}"))
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    data = timeline.trend(args.root.resolve(), last=args.last)
    _emit_report(args, data, timeline.render_trend(data))
    if data["errors"]:
        return 1
    return 1 if args.strict and data["regressions"] else 0


def cmd_diff(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    try:
        if args.plateau:
            data = diff_mod.plateaus(root, *args.plateau)
            rendered = diff_mod.render_plateaus(data)
        else:
            data = diff_mod.since(root, args.ref)
            rendered = diff_mod.render_since(data)
    except diff_mod.DiffError as exc:
        print(_error(str(exc)))
        return 1
    _emit_report(args, data, rendered)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    try:
        data = query_mod.run(
            args.root.resolve(),
            zone=args.zone,
            types=args.types,
            where=args.where,
            start=args.start,
            hops=args.hops,
            relations=args.relations,
            direction=args.direction,
            show=args.show,
        )
    except query_mod.QueryError as exc:
        print(_error(str(exc)))
        return 1
    _emit_report(args, data, query_mod.render(data))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    try:
        diagrams = export_mod.export(root, args.format, zone=args.zone, view_id=args.view)
    except export_mod.ExportError as exc:
        print(_error(str(exc)))
        return 1
    if args.view and not args.out:
        print(diagrams.get(args.view, ""), end="")
        return 0
    out_dir = args.out or (root / "build" / "diagrams")
    out_dir.mkdir(parents=True, exist_ok=True)
    for view_id, text in diagrams.items():
        path = out_dir / f"{view_id}{export_mod.SUFFIX[args.format]}"
        path.write_text(text, encoding="utf-8", newline="\n")
        print(_ok(f"Exported {ui.bold(view_id)} {ui.arrow()} {path}"))
    if not diagrams:
        print("No views to export.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    root = (args.root or serve_mod.default_root()).resolve()
    return serve_mod.serve(root)


def cmd_debt(args: argparse.Namespace) -> int:
    data = reports.debt(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_debt(data))
    return 0


def cmd_conformance(args: argparse.Namespace) -> int:
    data = reports.conformance(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_conformance(data))
    return 1 if getattr(args, "strict", False) and data["failed"] else 0


def cmd_roadmap(args: argparse.Namespace) -> int:
    data = reports.roadmap(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_roadmap(data))
    return 0


def cmd_correspondences(args: argparse.Namespace) -> int:
    data = reports.correspondences(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_correspondences(data))
    return 0


def cmd_delta(args: argparse.Namespace) -> int:
    data = reports.delta(args.root.resolve())
    _emit_report(args, data, reports.render_delta(data))
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    try:
        pack = contextpack.build(args.root.resolve(), scope=args.scope, today=_parse_as_of(args.as_of))
    except contextpack.ContextError as exc:
        print(_error(str(exc)))
        return 1
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(pack.markdown, encoding="utf-8", newline="\n")
        print(_ok(f"Context pack for {ui.bold(pack.scope)} written to {args.out}"))
    else:
        print(pack.markdown)
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    try:
        report = impact_mod.analyse(
            args.root.resolve(),
            scope=args.scope,
            depth=args.depth,
            today=_parse_as_of(args.as_of),
            zone=args.zone,
        )
    except impact_mod.ImpactError as exc:
        print(_error(str(exc)))
        return 1
    _emit_report(args, report.as_dict(), impact_mod.render(report))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    report = check_mod.check(
        args.root.resolve(),
        args.repo.resolve(),
        scope=args.scope,
        today=_parse_as_of(args.as_of),
        sboms=[path.resolve() for path in args.sboms or []],
    )
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def cmd_exposure(args: argparse.Namespace) -> int:
    report = security_mod.exposure(args.root.resolve(), zone=args.zone, depth=args.depth)
    _emit_report(args, report.as_dict(), security_mod.render_exposure(report))
    # Always 0: a path an attacker could take is a decision to make, not a defect to gate on.
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    report = score_mod.score(args.root.resolve(), args.gold.resolve())
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if args.min_f1 is not None:
        if not report.gates_ok:
            print("\nCandidate fails its own validation gates.")
            return 1
        if report.min_f1 * 100 < args.min_f1:
            print(f"\nMinimum F1 {report.min_f1:.0%} is below the required {args.min_f1:.0f}%")
            return 1
    return 0


def cmd_validate_facts(args: argparse.Namespace) -> int:
    report = facts_mod.validate_facts(args.root.resolve())
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def cmd_chunk(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if args.file:
        path = args.file if args.file.is_absolute() else root / args.file
        if not path.is_file():
            print(f"ERROR   source file not found: {path}")
            return 1
        targets = [path]
    else:
        register, _docs, _entities = facts_mod.load(root)
        targets = facts_mod.iter_source_files(register)
        if not targets:
            print(f"No source files found under {register.sources_dir()}")
            return 1
    chunks: list[intake.Chunk] = []
    for path in targets:
        chunks.extend(intake.chunk_file(path, facts_mod._rel(root, path), max_chars=args.max_chars))
    if args.json_out:
        print(json.dumps([c.as_dict() for c in chunks], indent=2, ensure_ascii=False))
    else:
        print(intake.render_chunks(chunks))
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    report = intake.coverage(args.root.resolve())
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if args.min_coverage is not None and report.ratio * 100 < args.min_coverage:
        print(f"\nCoverage {report.ratio:.0%} is below the required {args.min_coverage:.0f}%")
        return 1
    return 0


def cmd_readiness(args: argparse.Namespace) -> int:
    report = readiness_mod.analyse(args.root.resolve(), zone=args.zone)
    _emit_report(args, report.as_dict(), report.render())
    return 1 if args.strict and report.warnings else 0


def cmd_dora_register(args: argparse.Namespace) -> int:
    register = dora.build(args.root.resolve(), today=_parse_as_of(args.as_of))
    print(dora.render(register))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(register.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nJSON report written to {args.json_out}")
    if args.format == "its-csv" and not args.out:
        print(_error("--format its-csv writes one CSV per template; pass --out <directory>"))
        return 1
    if args.out:
        # Refusing to write an empty document is the point: a page that looks like a
        # filing and says nothing is the worst artifact this command could produce.
        try:
            if args.format == "its-csv":
                written = dora_its.export(register, args.out, dora_its.provider_leis(args.root.resolve()))
                print(_ok(f"{len(written) - 1} ITS template worksheet(s) and README.md written to {args.out}"))
            else:
                document = dora.markdown(register, args.lang)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(document, encoding="utf-8", newline="\n")
                print(_ok(f"Register written to {args.out}"))
        except dora.DoraError as exc:
            print(_error(str(exc)))
            return 1
    if not register.ok:
        return 1
    return 1 if args.strict and register.warnings else 0


def cmd_ai_act_register(args: argparse.Namespace) -> int:
    register = airegister.build(args.root.resolve(), today=_parse_as_of(args.as_of))
    print(airegister.render(register))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(register.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nJSON report written to {args.json_out}")
    if args.out:
        # Same refusal as dora-register: an empty page that looks like a compliance
        # record is the worst artifact this command could produce.
        try:
            document = airegister.markdown(register, args.lang)
        except airegister.AiActError as exc:
            print(_error(str(exc)))
            return 1
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(document, encoding="utf-8", newline="\n")
        print(_ok(f"Inventory written to {args.out}"))
    if not register.ok:
        return 1
    return 1 if args.strict and register.warnings else 0


def cmd_gdpr_register(args: argparse.Namespace) -> int:
    register = gdpr_mod.build(args.root.resolve(), today=_parse_as_of(args.as_of))
    print(gdpr_mod.render(register))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(register.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"\nJSON report written to {args.json_out}")
    if args.out:
        try:
            document = gdpr_mod.markdown(register, args.lang)
        except gdpr_mod.GdprError as exc:
            print(_error(str(exc)))
            return 1
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(document, encoding="utf-8", newline="\n")
        print(_ok(f"Record written to {args.out}"))
    if not register.ok:
        return 1
    return 1 if args.strict and register.warnings else 0


def cmd_maturity(args: argparse.Namespace) -> int:
    report = maturity_mod.assess(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, report.as_dict(), report.render())
    # Always 0. A level is a description, not a verdict; a maturity report that failed a
    # build would be switched off within a week and then measure nothing.
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    if args.print_only and args.json_out:
        # stdout is the file and nothing else under --print, and --print writes nothing;
        # dropping --json silently would leave a caller waiting for a report that never comes.
        print(_error("--print writes nothing, so it takes no --json: run the two separately"))
        return 1
    unwritable: propose_mod.ProposeUnwritable | None = None
    try:
        report = propose_mod.propose(
            args.root.resolve(),
            source=args.source,
            as_of=_parse_as_of(args.as_of),
            references=args.reference,
            out=args.out,
            dry_run=args.dry_run,
            print_only=args.print_only,
        )
    except (propose_mod.ProposeRefusal, alignment.AlignmentError) as exc:
        # AlignmentError too: `--from align` reaches the same loader `align` does, so a
        # typo in --reference must produce the same one-line refusal there as here, not
        # a traceback because this command forgot to catch it.
        print(_error(str(exc)))
        return 1
    except propose_mod.ProposeUnwritable as exc:
        unwritable, report = exc, exc.report
    if args.print_only:
        # The file and nothing else, as UTF-8 with LF endings whatever the console's code
        # page: what a file tool writes from this must be byte for byte what a run writes.
        sys.stdout.flush()
        binary = getattr(sys.stdout, "buffer", None)
        if binary is not None:
            binary.write(report.content.encode("utf-8"))
            binary.flush()
        else:  # a text-only stdout (an embedding host, a redirect): the text, unconverted
            sys.stdout.write(report.content)
        if not report.content:
            print("nothing to propose", file=sys.stderr)
        return 0
    print(propose_mod.render(report, failed=unwritable is not None))
    json_failed = False
    if args.json_out:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"\nJSON report written to {args.json_out}")
        except OSError as exc:
            print(_error(f"could not write {args.json_out}: {exc.strerror or exc}"))
            json_failed = True  # a report asked for and not written is a failed run
    if unwritable is not None:
        print(_error(
            f"could not write {unwritable.target.resolve()}: {unwritable.reason}. The proposals file "
            "was not written. Run the same command again with --print: it writes nothing and prints "
            "exactly this file, in full -- do not pipe it through head or tail -- for a file tool to "
            "put at that path unchanged."
        ))
        return 1
    if json_failed:
        return 1
    # Always 0: proposing nothing is a clean repository, not a failure, and a generator
    # that exited 1 on "no findings" would be unusable in a pipeline.
    return 0


def cmd_align(args: argparse.Namespace) -> int:
    try:
        report = alignment.align(args.root.resolve(), zone=args.zone, references=args.reference)
    except alignment.AlignmentError as exc:
        print(_error(str(exc)))
        return 1
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    if args.min_coverage is not None:
        # Refusing rather than passing vacuously: with nothing in scope there is no
        # coverage to compare, and a gate that reads "100%" of nothing is how an
        # unmeasured repository ends up looking aligned.
        if report.ratio is None:
            print(
                f"\nNo reference node is in scope, so coverage cannot be measured -- "
                f"the --min-coverage {args.min_coverage:.0f}% gate cannot pass. Add a pack under "
                f"{reference_mod.REFERENCE_DIRNAME}/, or drop the flag."
            )
            return 1
        if report.ratio * 100 < args.min_coverage:
            print(f"\nReference coverage {report.ratio:.0%} is below the required {args.min_coverage:.0f}%")
            return 1
    return 1 if args.strict and report.warnings else 0


def cmd_pin_reference(args: argparse.Namespace) -> int:
    if bool(args.reference) == bool(args.directory):
        print(_error("pass exactly one of --reference <name> or --dir <path>"))
        return 1
    if args.directory:
        directory = args.directory if args.directory.is_absolute() else Path.cwd() / args.directory
    else:
        directory = reference_mod.reference_dir(args.root.resolve()) / args.reference
    try:
        lines = reference_mod.write_pins(directory)
    except reference_mod.ReferenceError as exc:
        print(_error(str(exc)))
        return 1
    print(f"Pinned {len(lines)} file(s) of reference pack '{directory.name}':")
    for line in lines:
        print(f"  {line}")
    print(
        "\nRe-pin only for a deliberate, reviewed upgrade of the pack -- never to silence "
        "ALN001, which exists because coverage measured against an edited taxonomy is not a "
        "measurement."
    )
    return 0


def cmd_gen_schema(_args: argparse.Namespace) -> int:
    if not _oracle_intact():
        return 1
    for path in genschema.write_all_schemas():
        print(_ok(f"Wrote {path}"))
    print(f"(ArchiMate {oracle.matrix_version()}, {len(oracle.element_types())} element types)")
    return 0


def cmd_pin_oracle(_args: argparse.Namespace) -> int:
    files = sorted(
        p.name
        for p in oracle.ORACLE_DIR.iterdir()
        if p.is_file() and p.suffix in {".xml", ".xsd"}
    )
    lines = [f"{oracle.sha256(oracle.ORACLE_DIR / name)}  {name}" for name in files]
    oracle.CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Pinned {len(lines)} oracle file(s) in {oracle.CHECKSUMS}")
    for line in lines:
        print(f"  {line}")
    return 0


def cmd_oracle_info(_args: argparse.Namespace) -> int:
    print(f"ArchiMate version      : {oracle.matrix_version()}")
    print(f"Element types          : {len(oracle.element_types())}")
    print(f"Relationship types     : {len(oracle.relationship_types())}")
    unmapped = oracle.unmapped_layers()
    print(f"Concepts without layer : {', '.join(sorted(unmapped)) if unmapped else 'none'}")
    print("Checksum pins:")
    for result in oracle.verify_checksums():
        status = ui.green("OK  ") if result.ok else ui.red("FAIL")
        print(f"  {status} {result.name}")
    return 0


HANDLERS = {
    "validate": cmd_validate,
    "compile": cmd_compile,
    "render": cmd_render,
    "docs": cmd_docs,
    "import": cmd_import,
    "intake-csv": cmd_intake_csv,
    "intake-doc": cmd_intake_doc,
    "rtm": cmd_rtm,
    "glossary": cmd_glossary,
    "promote": cmd_promote,
    "review": cmd_review,
    "init": cmd_init,
    "intake-redact": cmd_intake_redact,
    "doctor": cmd_doctor,
    "validate-gov": cmd_validate_gov,
    "staleness": cmd_staleness,
    "kpi": cmd_kpi,
    "trend": cmd_trend,
    "diff": cmd_diff,
    "query": cmd_query,
    "export": cmd_export,
    "serve": cmd_serve,
    "debt": cmd_debt,
    "conformance": cmd_conformance,
    "correspondences": cmd_correspondences,
    "roadmap": cmd_roadmap,
    "delta": cmd_delta,
    "context": cmd_context,
    "impact": cmd_impact,
    "check": cmd_check,
    "exposure": cmd_exposure,
    "score": cmd_score,
    "validate-facts": cmd_validate_facts,
    "chunk": cmd_chunk,
    "coverage": cmd_coverage,
    "readiness": cmd_readiness,
    "align": cmd_align,
    "dora-register": cmd_dora_register,
    "ai-act-register": cmd_ai_act_register,
    "gdpr-register": cmd_gdpr_register,
    "propose": cmd_propose,
    "maturity": cmd_maturity,
    "pin-reference": cmd_pin_reference,
    "gen-schema": cmd_gen_schema,
    "pin-oracle": cmd_pin_oracle,
    "oracle-info": cmd_oracle_info,
}


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy codepage (cp1250/cp437) that cannot print
    # arrows or the warning sign used in reports; never let encoding crash a gate.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ui.enable_windows_vt()
    args = build_parser().parse_args(argv)
    refusal = _tooling_version_refusal(args)
    if refusal:
        print(_error(refusal))
        return 1
    return HANDLERS[args.command](args)


# Commands that must run whatever a repository's toolingVersion says: `doctor` reports the
# mismatch instead of refusing it, and `init` writes the version in the first place.
VERSION_EXEMPT = {"doctor", "init", "gen-schema", "pin-oracle", "oracle-info"}


def _version_tuple(text: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in str(text).split("."))
    except ValueError:
        return None


def _tooling_version_refusal(args: argparse.Namespace) -> str:
    """Refuse, by name, to read a repository written for a newer release than this one.

    Content written for a newer release can use keys, rules or record kinds this release
    does not know; reading it anyway produces findings about what it misunderstands and
    silence about what it cannot see. An unparseable value is SCHEMA002's to report.
    """
    from . import __version__

    root = getattr(args, "root", None)
    if args.command in VERSION_EXEMPT or root is None:
        return ""
    required = dsl.load_config(Path(root).resolve()).get("toolingVersion")
    needed, running = _version_tuple(required) if required else None, _version_tuple(__version__)
    if needed and running and needed > running:
        return (
            f"this repository needs ea-skills {required} or later (toolingVersion in ea.config.yaml); "
            f"this is {__version__}. Upgrade the plugin (`/plugin update ea-skills`) or the clone, "
            "rather than read content written for a release this one does not know."
        )
    return ""


if __name__ == "__main__":
    sys.exit(main())
