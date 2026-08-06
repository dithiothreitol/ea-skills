"""Run the extraction, modelling and documentation skills against a golden case.

This is the only code in the repository that touches the network, and it is deliberately
**outside** ``easkills/``. The core's security posture -- "no network at runtime",
stated in SECURITY.md and proved by a test -- has to keep being true, so a quarantine
test asserts that no module under ``easkills/`` imports an HTTP client or this SDK.
Nothing here is imported by the core, shipped in ``requirements.txt``, or run by the
default gate.

**What it measures.** The skills are prose that instructs an agent. The harness gives a
model that prose, the deterministic command output it prescribes, and the repair loop it
prescribes (three iterations, then stop), and scores what comes out against gold. That
is the product's central claim under test: *do the written instructions, over this
deterministic core, produce a faithful model?*

Five skills' prose is measured, declared in ``MEASURED_SKILLS`` and pinned to the README
by a test: `ea-intake`; `ea-model` + `ea-capability-map`; `ea-stakeholders` + `ea-views`.
The first two phases are scored against gold. The third is judged by **contract** -- gold
holds no stakeholders or views, so the measurement is the ISO 42010 conformance checklist
the core computes, reported and never gated.

**What it does not measure.** A host like Claude Code executing the same skills with its
own tools, multi-turn, with its own planning. The number here is a regression signal for
the skill *text*, not a benchmark of an agent. Runs use the API default temperature, so
several runs per case are the point: the spread is the honest part.

Usage::

    python eval/harness/run.py --case clinic --runs 3
    python eval/harness/run.py --case contested --runs 3 --model claude-opus-5
    python eval/harness/run.py --all --baseline   # rewrite eval/harness/baseline.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Run as a script (`python eval/harness/run.py`), so this directory is sys.path[0] and the
# shared plumbing imports plainly. `common` puts the repository root on the path too: the
# harness reads the core's vocabulary, and never writes to it.
from common import (  # noqa: E402
    DEFAULT_MODEL,
    HARNESS_DIR,
    MAX_REPAIRS,
    OUTPUT_CONTRACT,
    REPO_ROOT,
    Session,
    Usage,
    client as api_client,
    easkills,
    extract_files,
    skill,
    write_files,
)

BASELINE_PATH = HARNESS_DIR / "baseline.json"
CASES = {
    "clinic": REPO_ROOT / "eval" / "golden" / "clinic",
    "contested": REPO_ROOT / "eval" / "golden" / "contested",
}
# Which skills' prose this harness actually puts in front of the model, per phase. The
# list is the honest answer to "what is measured here" -- everything else in `skills/` is
# unmeasured, and a test pins this declaration to the claim in README.md so the two
# cannot drift apart the way the tutorial once drifted from the CLI.
MEASURED_SKILLS: dict[str, tuple[str, ...]] = {
    "intake": ("ea-intake",),
    "modelling": ("ea-model", "ea-capability-map"),
    "apparatus": ("ea-stakeholders", "ea-views"),
}


def phase_system(phase: str) -> str:
    """The system prompt for a phase: every skill it measures, then the output contract."""
    return "\n\n".join([skill(name) for name in MEASURED_SKILLS[phase]] + [OUTPUT_CONTRACT])


@dataclass
class RunResult:
    case: str
    model: str
    ok: bool
    scores: dict[str, Any] = field(default_factory=dict)
    gates: dict[str, Any] = field(default_factory=dict)
    repairs: dict[str, int] = field(default_factory=dict)
    # The apparatus phase is judged by contract, not by matching gold: ISO 42010's loop
    # either closes or it does not. Reported, never gated.
    apparatus: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""
    seconds: float = 0.0


# ------------------------------------------------------------------------- the pipeline


def measure_apparatus(scratch: Path, workdir: Path) -> dict[str, Any]:
    """Judge the apparatus phase by contract: does ISO 42010's loop close?

    Gold has no stakeholders, concerns or views, so there is nothing to match against --
    and inventing gold for them would make the number a similarity to one author's
    documentation taste. The clauses below are checkable properties instead: concerns held
    by someone, views governed by a viewpoint, every concern framed. Never gated, because
    an unframed concern is an honest finding about a repository, not a skill regression.
    """
    from easkills import dsl  # local import: the harness reads the core, never the reverse

    report = workdir / "conformance.json"
    report.unlink(missing_ok=True)  # never read a previous invocation's answer
    easkills("conformance", "--root", str(scratch), "--json", str(report))
    clauses: dict[str, str] = {}
    if report.is_file():
        payload = json.loads(report.read_text(encoding="utf-8"))
        clauses = {item["clause"]: item["status"] for item in payload.get("items", [])}
    try:
        promoted, _documents, _config = dsl.load(scratch, "approved")
        counts = {
            "stakeholders": len(promoted.stakeholders),
            "concerns": len(promoted.concerns),
            "views": len(promoted.views),
        }
    except Exception:  # noqa: BLE001 - an unloadable model is data, not a crash
        counts = {"stakeholders": 0, "concerns": 0, "views": 0}
    return {
        "clauses": clauses,
        "clausesPassed": sum(1 for status in clauses.values() if status == "pass"),
        "clausesFailed": sum(1 for status in clauses.values() if status == "fail"),
        **counts,
    }


def run_case(client: Any, case: str, model: str, workdir: Path) -> RunResult:
    started = time.monotonic()
    gold = CASES[case]
    usage = Usage()
    result = RunResult(case=case, model=model, ok=False)

    # A scratch repository holding *only* the inputs. Gold's register and model never
    # exist here: a leaked answer makes the number meaningless.
    scratch = workdir / case
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / "facts" / "register").mkdir(parents=True)
    (scratch / "model" / "staging").mkdir(parents=True)
    (scratch / "model" / "approved").mkdir(parents=True)
    shutil.copy(gold / "ea.config.yaml", scratch / "ea.config.yaml")
    shutil.copytree(gold / "facts" / "sources", scratch / "facts" / "sources")

    transcript = scratch / "_harness-transcript.md"

    def record(phase: str, text: str) -> None:
        """Keep every reply next to the artifacts it produced.

        A surprising score has to be explainable without re-running: the first
        investigation of a 0% category was reverse-engineered from YAML files, which is
        slower and less reliable than reading what the model actually said.
        """
        with transcript.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\n\n## {phase}\n\n{text}\n")

    def write(files: dict[str, str]) -> None:
        write_files(scratch, files)

    def phase(label: str, session: Session, prompt: str, gate: list[str]) -> int:
        """Ask, write the files, then repair against the real gate until it passes.

        One shape for all three phases: the skills prescribe exactly this loop, capped at
        three iterations, and a phase that cannot produce a parseable file is a failed run
        rather than a partial one.

        The final gate verdict is recorded, not inferred from the repair count. Exhausting
        the cap and converging on the last attempt produce the same number, and a run that
        gave up must not be reported beside one that succeeded.
        """
        reply = session.ask(prompt)
        record(label, reply)
        files = extract_files(reply)
        if not files:
            raise ValueError(f"{label} produced no parseable file")
        write(files)
        repairs = 0
        while repairs < MAX_REPAIRS:
            checked = easkills(*gate)
            if checked.returncode == 0:
                break
            repairs += 1
            reply = session.ask(
                "The gate refused this. Repair it and reply with the corrected files in "
                "the same format.\n\n" + checked.stdout
            )
            record(f"{label} repair {repairs}", reply)
            files = extract_files(reply)
            if not files:
                raise ValueError(f"{label} repair produced no parseable file")
            write(files)
        result.repairs[label] = repairs
        result.gates[label] = easkills(*gate).returncode
        return repairs

    try:
        # ---------------------------------------------------------------- intake
        chunks = easkills("chunk", "--root", str(scratch), "--json")
        sources = "\n\n".join(
            f"=== {path.name} ===\n{path.read_text(encoding='utf-8')}"
            for path in sorted((scratch / "facts" / "sources").iterdir())
        )
        intake = Session(client, model, phase_system("intake"), usage)
        phase(
            "intake",
            intake,
            "Extract the fact register for this repository.\n\n"
            "Write exactly two files: `facts/register/extracted.yaml` (key `facts:`) and "
            "`facts/entities.yaml` (key `entities:`). Every fact needs a verbatim quote "
            "that occurs in the source character-for-character.\n\n"
            f"Deterministic chunking:\n{chunks.stdout}\n\nSources:\n{sources}",
            ["validate-facts", "--root", str(scratch)],
        )

        # ---------------------------------------------------------------- modelling
        register = "\n\n".join(
            f"=== {path.relative_to(scratch)} ===\n{path.read_text(encoding='utf-8')}"
            for path in sorted((scratch / "facts").rglob("*.yaml"))
        )
        from easkills import oracle  # local: the harness reads the same vocabulary the gate does

        modelling = Session(client, model, phase_system("modelling"), usage)
        phase(
            "modelling",
            modelling,
            "Model this fact register. Write the ArchiMate model into files under "
            "`model/staging/` (elements by layer, relationships in "
            "`model/staging/relations.yaml`).\n\n"
            "Every concept needs `owner`, `lastReviewed` (use 2026-08-06) and provenance "
            "citing a fact id, because these files will be promoted to the approved zone.\n\n"
            f"Permitted element types: {', '.join(sorted(oracle.element_types()))}\n"
            f"Permitted relationship types: {', '.join(sorted(oracle.relationship_types()))}\n\n"
            f"The register:\n{register}",
            ["validate", "--root", str(scratch), "--zone", "staging"],
        )

        # ---------------------------------------------------------------- apparatus
        # Stakeholders, concerns and views: the ISO 42010 loop. Gold holds none of these,
        # so nothing here is scored against it -- the measurement is the conformance
        # checklist the core computes, which is a contract rather than a similarity.
        staged = "\n\n".join(
            f"=== {path.relative_to(scratch)} ===\n{path.read_text(encoding='utf-8')}"
            for path in sorted((scratch / "model" / "staging").rglob("*.yaml"))
        )
        apparatus = Session(client, model, phase_system("apparatus"), usage)
        phase(
            "apparatus",
            apparatus,
            "Add the ISO 42010 apparatus to this model: write "
            "`model/staging/stakeholders.yaml` (keys `stakeholders:` and `concerns:`) and "
            "`model/staging/views.yaml` (key `views:`).\n\n"
            "Every stakeholder holds at least one concern, every concern is framed by at "
            "least one view, every view declares a viewpoint and a `documentation` line "
            "naming the concern it frames and for whom. Do not restate the elements; the "
            "model below is already staged.\n\n"
            f"The staged model:\n{staged}\n\nThe register:\n{register}",
            ["validate", "--root", str(scratch), "--zone", "staging"],
        )

        # ---------------------------------------------------------------- promote & score
        promotion = easkills("promote", "--root", str(scratch))
        result.gates["promotion"] = promotion.returncode
        result.apparatus = measure_apparatus(scratch, workdir)

        # Removed before the run, not after: the work directory is reused across
        # invocations, and reading a file the *previous* run left behind would report last
        # week's numbers as this run's -- a failure that looks exactly like a result.
        score_json = workdir / f"{case}-score.json"
        score_json.unlink(missing_ok=True)
        scored = easkills(
            "score", "--root", str(scratch), "--gold", str(gold), "--json", str(score_json)
        )
        if score_json.is_file():
            result.scores = json.loads(score_json.read_text(encoding="utf-8"))
            result.ok = True
        else:
            raise ValueError(f"scoring produced no report: {scored.stdout[-600:]}")
    except Exception as exc:  # noqa: BLE001 - a failed run is data, not a crash
        result.error = f"{type(exc).__name__}: {exc}"
    result.usage = usage.as_dict()
    result.seconds = round(time.monotonic() - started, 1)
    return result


# ------------------------------------------------------------------------- reporting


def summarise(runs: list[RunResult]) -> dict[str, Any]:
    """Spread, not a single number: the point of running a case more than once."""
    out: dict[str, Any] = {}
    for case in sorted({run.case for run in runs}):
        of_case = [run for run in runs if run.case == case]
        good = [run for run in of_case if run.ok]
        entry: dict[str, Any] = {
            "runs": len(of_case),
            "completed": len(good),
            "failures": [run.error for run in of_case if not run.ok],
            "repairs": [run.repairs for run in of_case],
            "gatesGreen": sum(1 for run in good if run.scores.get("gatesOk")),
            # Two different claims, kept apart: `gatesGreen` is the candidate repository
            # passing its own validators at the end; `phasesGreen` is every phase gate
            # having passed within the three-repair cap. A run that gave up on the third
            # attempt can still leave a repository that validates, and reporting only the
            # first number would hide the giving up.
            "phasesGreen": sum(
                1 for run in good if all(code == 0 for code in run.gates.values())
            ),
            "gaveUp": [
                sorted(label for label, code in run.gates.items() if code != 0)
                for run in good
                if any(code != 0 for code in run.gates.values())
            ],
        }
        categories: dict[str, list[float]] = {}
        for run in good:
            for name, values in (run.scores.get("categories") or {}).items():
                categories.setdefault(name, []).append(round(values["f1"], 4))
        entry["f1"] = {
            name: {"min": min(values), "median": sorted(values)[len(values) // 2], "max": max(values)}
            for name, values in sorted(categories.items())
        }
        entry["minF1"] = [round(run.scores.get("minF1", 0.0), 4) for run in good]
        # Apparatus: reported per run, aggregated as a median, never compared to a baseline.
        entry["apparatus"] = {
            metric: sorted(values)[len(values) // 2]
            for metric, values in sorted(
                {
                    metric: [run.apparatus[metric] for run in good if metric in run.apparatus]
                    for metric in ("clausesPassed", "clausesFailed", "stakeholders", "concerns", "views")
                }.items()
            )
            if values
        }
        entry["apparatusClauseFailures"] = sorted(
            {
                clause
                for run in good
                for clause, status in (run.apparatus.get("clauses") or {}).items()
                if status == "fail"
            }
        )
        entry["tokens"] = {
            "input": sum(run.usage.get("inputTokens", 0) for run in of_case),
            "output": sum(run.usage.get("outputTokens", 0) for run in of_case),
        }
        out[case] = entry
    return out


def render(summary: dict[str, Any], model: str) -> str:
    lines = [f"Golden-set harness -- model {model}", ""]
    for case, entry in summary.items():
        lines.append(
            f"{case}: {entry['completed']}/{entry['runs']} runs completed, "
            f"{entry['gatesGreen']} with green gates, "
            f"{entry.get('phasesGreen', entry['gatesGreen'])} with every phase gate passed"
            + (f"  (gave up on: {entry['gaveUp']})" if entry.get("gaveUp") else "")
        )
        for name, spread in entry["f1"].items():
            width = "{:<16}".format(name)
            lines.append(
                f"  {width} min {spread['min']:.0%}  median {spread['median']:.0%}  max {spread['max']:.0%}"
            )
        if entry.get("apparatus"):
            apparatus = entry["apparatus"]
            failures = entry.get("apparatusClauseFailures") or []
            lines.append(
                "  {:<16} {} stakeholder(s), {} concern(s), {} view(s); ISO clauses "
                "{} pass / {} fail{}  -- diagnostic, not gated".format(
                    "apparatus",
                    apparatus.get("stakeholders", 0),
                    apparatus.get("concerns", 0),
                    apparatus.get("views", 0),
                    apparatus.get("clausesPassed", 0),
                    apparatus.get("clausesFailed", 0),
                    f" ({', '.join(failures)})" if failures else "",
                )
            )
        if entry["failures"]:
            lines.append("  failures: " + "; ".join(entry["failures"]))
        lines.append(
            f"  repairs: {entry['repairs']}  tokens in/out: "
            f"{entry['tokens']['input']}/{entry['tokens']['output']}"
        )
        lines.append("")
    return "\n".join(lines)


def compare(summary: dict[str, Any], baseline: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Regressions and movements against the committed baseline, per category.

    Returns ``(regressions, movements)``. A regression is a median that fell **below the
    baseline's observed minimum** -- outside the spread the baseline itself measured. A
    median that fell but stayed inside that spread is a *movement*: reported, not a
    failure. With three runs at API default temperature, a three-point median move says
    nothing, and the first baseline comparison duly flagged one (`contested/entities`
    83% -> 80%, spread 77-83 versus 67-86) alongside a real one. A gate that cries wolf
    gets ignored, which costs more than the noise it reports.
    """
    regressions: list[str] = []
    movements: list[str] = []
    for case, entry in summary.items():
        before = (baseline.get("cases") or {}).get(case)
        if not before:
            continue
        for name, spread in entry["f1"].items():
            was = (before.get("f1") or {}).get(name)
            if not was or spread["median"] + 1e-9 >= was["median"]:
                continue
            moved = f"{case}/{name}: median {was['median']:.0%} -> {spread['median']:.0%}"
            if spread["median"] + 1e-9 < was.get("min", was["median"]):
                regressions.append(f"{moved} (below the baseline's own minimum {was['min']:.0%})")
            else:
                movements.append(f"{moved} (inside the baseline spread "
                                 f"{was['min']:.0%}-{was['max']:.0%})")
    return regressions, movements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the skills against the golden set")
    parser.add_argument("--case", choices=sorted(CASES), help="one case (default: all)")
    parser.add_argument("--all", action="store_true", help="every case")
    parser.add_argument("--runs", type=int, default=3, help="runs per case (default: 3)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, help="write the raw run records here")
    parser.add_argument(
        "--baseline", action="store_true", help="rewrite eval/harness/baseline.json from this run"
    )
    parser.add_argument(
        "--from-records",
        type=Path,
        help="rebuild the baseline from a saved --out file instead of running again "
        "(the decision to accept a number is separate from the run that produced it)",
    )
    parser.add_argument(
        "--workdir", type=Path, help="scratch directory (default: a temp dir, kept for inspection)"
    )
    args = parser.parse_args(argv)

    if args.from_records:
        records = json.loads(args.from_records.read_text(encoding="utf-8"))
        replayed = [
            RunResult(
                case=record["case"],
                model=record["model"],
                ok=record["ok"],
                scores=record["scores"],
                repairs=record["repairs"],
                apparatus=record.get("apparatus") or {},  # absent in pre-v2 record files
                usage=record["usage"],
                error=record["error"],
            )
            for record in records
        ]
        summary = summarise(replayed)
        print(render(summary, replayed[0].model if replayed else args.model))
        BASELINE_PATH.write_text(
            json.dumps(
                {"model": replayed[0].model if replayed else args.model, "runs": args.runs, "cases": summary},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",  # a baseline whose bytes depend on the author's OS is diff noise
        )
        print(f"baseline written from {args.from_records}")
        return 0

    cases = [args.case] if args.case else sorted(CASES)
    client = api_client()

    workdir = args.workdir or Path(os.environ.get("TEMP", "/tmp")) / "ea-harness"
    workdir.mkdir(parents=True, exist_ok=True)

    runs: list[RunResult] = []
    for case in cases:
        for index in range(args.runs):
            print(f"[{case} {index + 1}/{args.runs}] running...", flush=True)
            run = run_case(client, case, args.model, workdir / f"run{index + 1}")
            status = "ok" if run.ok else f"FAILED ({run.error})"
            print(f"[{case} {index + 1}/{args.runs}] {status} in {run.seconds}s", flush=True)
            runs.append(run)

    summary = summarise(runs)
    print()
    print(render(summary, args.model))

    if args.out:
        args.out.write_text(
            json.dumps([run.__dict__ for run in runs], indent=2, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")) if BASELINE_PATH.is_file() else {}
    if args.baseline:
        BASELINE_PATH.write_text(
            json.dumps({"model": args.model, "runs": args.runs, "cases": summary}, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"baseline written to {BASELINE_PATH}")
        return 0

    regressions, movements = compare(summary, baseline)
    for line in movements:
        print(f"moved, within the measured spread: {line}")
    if regressions:
        print("REGRESSION against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1
    if baseline:
        print("No category regressed against the baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
