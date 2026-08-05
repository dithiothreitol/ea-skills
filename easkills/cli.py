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
    aoef,
    check as check_mod,
    contextpack,
    docgen,
    facts as facts_mod,
    genschema,
    govern,
    impact as impact_mod,
    importer,
    intake,
    oracle,
    promote as promote_mod,
    render as render_mod,
    reports,
    score as score_mod,
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

    p_import = sub.add_parser(
        "import", help="import an ArchiMate Open Exchange file into model/staging/ (brownfield adoption)"
    )
    p_import.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_import.add_argument("--file", type=Path, required=True, help="the exchange XML to import")
    p_import.add_argument(
        "--out", type=Path, help="target YAML file (default: model/staging/<source-stem>.yaml)"
    )
    p_import.add_argument(
        "--ids",
        choices=("names", "identifiers"),
        default="names",
        help="derive DSL slugs from element names (default; readable) or from XML identifiers (round-trip)",
    )
    p_import.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")

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
        result = render_mod.render_all(root, zone=args.zone, out_dir=args.out)
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
        result = docgen.generate(root, out=args.out)
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
            f"{report.views} view(s) into {ui.bold(report.target)}"
        ),
        ui.dim(f"source: {report.source} (sha256 {report.sha256[:16]}); ids: {report.ids}"),
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
            "still lacks (owners, review dates, evidence), then promote deliberately."
        ),
    ]
    return "\n".join(lines)


def cmd_promote(args: argparse.Namespace) -> int:
    try:
        result = promote_mod.promote(args.root.resolve(), files=args.files, dry_run=args.dry_run)
    except promote_mod.PromoteError as exc:
        print(_error(str(exc)))
        return 1
    print(result.render())
    return 0 if result.ok else 1


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
    data = reports.kpi(args.root.resolve(), today=_parse_as_of(args.as_of))
    _emit_report(args, data, reports.render_kpi(data))
    return 0


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
            args.root.resolve(), scope=args.scope, depth=args.depth, today=_parse_as_of(args.as_of)
        )
    except impact_mod.ImpactError as exc:
        print(_error(str(exc)))
        return 1
    _emit_report(args, report.as_dict(), impact_mod.render(report))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    report = check_mod.check(
        args.root.resolve(), args.repo.resolve(), scope=args.scope, today=_parse_as_of(args.as_of)
    )
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


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
    "promote": cmd_promote,
    "validate-gov": cmd_validate_gov,
    "staleness": cmd_staleness,
    "kpi": cmd_kpi,
    "debt": cmd_debt,
    "conformance": cmd_conformance,
    "correspondences": cmd_correspondences,
    "roadmap": cmd_roadmap,
    "delta": cmd_delta,
    "context": cmd_context,
    "impact": cmd_impact,
    "check": cmd_check,
    "score": cmd_score,
    "validate-facts": cmd_validate_facts,
    "chunk": cmd_chunk,
    "coverage": cmd_coverage,
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
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
