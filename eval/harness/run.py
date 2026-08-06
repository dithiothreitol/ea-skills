"""Run the extraction and modelling skills against a golden case, and score the result.

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
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_DIR = Path(__file__).resolve().parent
# Run as a script (`python eval/harness/run.py`), so the repository root is not on the
# path. The harness reads the core's vocabulary; it never writes to it.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BASELINE_PATH = HARNESS_DIR / "baseline.json"
CASES = {
    "clinic": REPO_ROOT / "eval" / "golden" / "clinic",
    "contested": REPO_ROOT / "eval" / "golden" / "contested",
}
DEFAULT_MODEL = "claude-sonnet-5"
MAX_REPAIRS = 3  # the cap the skills themselves prescribe (research: repair loops plateau at 3-4)
MAX_TOKENS = 16000

FILE_MARKER = re.compile(r"^FILE:\s*(?P<path>[A-Za-z0-9._/-]+)\s*$", re.MULTILINE)
FENCE = re.compile(r"```(?:yaml|yml)?\s*\n(?P<body>.*?)```", re.DOTALL)


# --------------------------------------------------------------------------- plumbing


def load_key() -> str:
    """Environment first, then a local ``.env``. The value is never logged."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "ANTHROPIC_API_KEY is not set. Export it, or put it in .env (which is gitignored)."
    )


def easkills(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a core command exactly as a user would, from the repository root."""
    return subprocess.run(
        [sys.executable, "-m", "easkills", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def skill(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def extract_files(text: str) -> dict[str, str]:
    """Parse ``FILE: <path>`` + fenced block pairs out of a model reply.

    A reply that produces no parseable file is a failed run, reported as such -- the
    harness never falls back to "best effort", because a scored run that silently used
    half an answer is worse than no number.
    """
    out: dict[str, str] = {}
    markers = list(FILE_MARKER.finditer(text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        fence = FENCE.search(text, marker.end(), end)
        if fence:
            out[marker.group("path")] = fence.group("body")
    return out


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, response: Any) -> None:
        self.calls += 1
        self.input_tokens += getattr(response.usage, "input_tokens", 0)
        self.output_tokens += getattr(response.usage, "output_tokens", 0)


@dataclass
class RunResult:
    case: str
    model: str
    ok: bool
    scores: dict[str, Any] = field(default_factory=dict)
    gates: dict[str, Any] = field(default_factory=dict)
    repairs: dict[str, int] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""
    seconds: float = 0.0


class Session:
    """One conversation per phase, so a repair sees what it is repairing."""

    def __init__(self, client: Any, model: str, system: str, usage: Usage) -> None:
        self.client = client
        self.model = model
        self.system = system
        self.usage = usage
        self.messages: list[dict[str, Any]] = []

    def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system,
            messages=self.messages,
        )
        self.usage.add(response)
        text = "".join(block.text for block in response.content if block.type == "text")
        self.messages.append({"role": "assistant", "content": text})
        return text


# ------------------------------------------------------------------------- the pipeline

OUTPUT_CONTRACT = """
Reply with nothing but the files. For each file, one line

FILE: <path relative to the repository root>

followed by one fenced ```yaml block holding that file's entire content. No prose
before, between or after the blocks -- anything else is discarded by the harness.
"""


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
        for relative, body in files.items():
            target = (scratch / relative).resolve()
            if not target.is_relative_to(scratch.resolve()):
                raise ValueError(f"refusing to write outside the scratch repository: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8", newline="\n")

    try:
        # ---------------------------------------------------------------- intake
        chunks = easkills("chunk", "--root", str(scratch), "--json")
        sources = "\n\n".join(
            f"=== {path.name} ===\n{path.read_text(encoding='utf-8')}"
            for path in sorted((scratch / "facts" / "sources").iterdir())
        )
        intake = Session(
            client,
            model,
            skill("ea-intake") + "\n\n" + OUTPUT_CONTRACT,
            usage,
        )
        reply = intake.ask(
            "Extract the fact register for this repository.\n\n"
            "Write exactly two files: `facts/register/extracted.yaml` (key `facts:`) and "
            "`facts/entities.yaml` (key `entities:`). Every fact needs a verbatim quote "
            "that occurs in the source character-for-character.\n\n"
            f"Deterministic chunking:\n{chunks.stdout}\n\nSources:\n{sources}"
        )
        record("intake", reply)
        files = extract_files(reply)
        if not files:
            raise ValueError("intake produced no parseable file")
        write(files)

        repairs = 0
        while repairs < MAX_REPAIRS:
            gate = easkills("validate-facts", "--root", str(scratch))
            if gate.returncode == 0:
                break
            repairs += 1
            reply = intake.ask(
                "The evidence gate refused this register. Repair it and reply with the "
                "corrected files in the same format.\n\n" + gate.stdout
            )
            record(f"intake repair {repairs}", reply)
            files = extract_files(reply)
            if not files:
                raise ValueError("intake repair produced no parseable file")
            write(files)
        result.repairs["facts"] = repairs
        facts_gate = easkills("validate-facts", "--root", str(scratch))
        result.gates["facts"] = facts_gate.returncode

        # ---------------------------------------------------------------- modelling
        register = "\n\n".join(
            f"=== {path.relative_to(scratch)} ===\n{path.read_text(encoding='utf-8')}"
            for path in sorted((scratch / "facts").rglob("*.yaml"))
        )
        from easkills import oracle  # local: the harness reads the same vocabulary the gate does

        modelling = Session(
            client,
            model,
            skill("ea-model") + "\n\n" + OUTPUT_CONTRACT,
            usage,
        )
        reply = modelling.ask(
            "Model this fact register. Write the ArchiMate model into files under "
            "`model/staging/` (elements by layer, relationships in "
            "`model/staging/relations.yaml`, views in `model/staging/views.yaml`), plus "
            "stakeholders and concerns.\n\n"
            "Every concept needs `owner`, `lastReviewed` (use 2026-08-06) and provenance "
            "citing a fact id, because these files will be promoted to the approved zone.\n\n"
            f"Permitted element types: {', '.join(sorted(oracle.element_types()))}\n"
            f"Permitted relationship types: {', '.join(sorted(oracle.relationship_types()))}\n\n"
            f"The register:\n{register}"
        )
        record("modelling", reply)
        files = extract_files(reply)
        if not files:
            raise ValueError("modelling produced no parseable file")
        write(files)

        repairs = 0
        while repairs < MAX_REPAIRS:
            gate = easkills("validate", "--root", str(scratch), "--zone", "staging")
            if gate.returncode == 0:
                break
            repairs += 1
            reply = modelling.ask(
                "The model gate refused this. Repair it and reply with the corrected files "
                "in the same format.\n\n" + gate.stdout
            )
            record(f"modelling repair {repairs}", reply)
            files = extract_files(reply)
            if not files:
                raise ValueError("modelling repair produced no parseable file")
            write(files)
        result.repairs["model"] = repairs

        # ---------------------------------------------------------------- promote & score
        promotion = easkills("promote", "--root", str(scratch))
        result.gates["promotion"] = promotion.returncode

        score_json = workdir / f"{case}-score.json"
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
    result.usage = {
        "calls": usage.calls,
        "inputTokens": usage.input_tokens,
        "outputTokens": usage.output_tokens,
    }
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
        entry["tokens"] = {
            "input": sum(run.usage.get("inputTokens", 0) for run in of_case),
            "output": sum(run.usage.get("outputTokens", 0) for run in of_case),
        }
        out[case] = entry
    return out


def render(summary: dict[str, Any], model: str) -> str:
    lines = [f"Golden-set harness -- model {model}", ""]
    for case, entry in summary.items():
        lines.append(f"{case}: {entry['completed']}/{entry['runs']} runs completed, "
                     f"{entry['gatesGreen']} with green gates")
        for name, spread in entry["f1"].items():
            width = "{:<16}".format(name)
            lines.append(
                f"  {width} min {spread['min']:.0%}  median {spread['median']:.0%}  max {spread['max']:.0%}"
            )
        if entry["failures"]:
            lines.append("  failures: " + "; ".join(entry["failures"]))
        lines.append(
            f"  repairs: {entry['repairs']}  tokens in/out: "
            f"{entry['tokens']['input']}/{entry['tokens']['output']}"
        )
        lines.append("")
    return "\n".join(lines)


def compare(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Regressions against the committed baseline, by median F1 per category."""
    regressions: list[str] = []
    for case, entry in summary.items():
        before = (baseline.get("cases") or {}).get(case)
        if not before:
            continue
        for name, spread in entry["f1"].items():
            was = (before.get("f1") or {}).get(name)
            if was and spread["median"] + 1e-9 < was["median"]:
                regressions.append(
                    f"{case}/{name}: median {was['median']:.0%} -> {spread['median']:.0%}"
                )
    return regressions


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
        "--workdir", type=Path, help="scratch directory (default: a temp dir, kept for inspection)"
    )
    args = parser.parse_args(argv)

    cases = [args.case] if args.case else sorted(CASES)
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install -r requirements-eval.txt") from None
    client = anthropic.Anthropic(api_key=load_key())

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
        )

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")) if BASELINE_PATH.is_file() else {}
    if args.baseline:
        BASELINE_PATH.write_text(
            json.dumps({"model": args.model, "runs": args.runs, "cases": summary}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"baseline written to {BASELINE_PATH}")
        return 0

    regressions = compare(summary, baseline)
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
