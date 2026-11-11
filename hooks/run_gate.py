"""PostToolUse hook: the gate a skill prescribes, run by the host after the write (D1).

Every skill that writes governed content ends the same way: run the gate, repair, and do
not call the work done while it reports errors. The first host eval (2026-10-25) measured
that instruction for the first time, and it did not hold: in no run did the host call
`validate-facts` or `validate --zone staging`. Phase 8 had already decided that *a rule
that must hold every time is a hook, not a sentence* -- and applied it to the approved
zone only. This file applies it to the gates.

After a write into a governed directory of an architecture repository, the owning gate
runs and its verdict goes back to the model:

* `facts/register/`, `facts/entities.yaml`, `facts/questions/` -> `validate-facts`
* `model/staging/` -> `validate --zone staging`
* `standards/`, `governance-log/`, `services/` -> `validate-gov`

Errors come back as the hook's `block` decision with the findings, which the host shows
next to the tool result; a passing gate comes back as one line of context, so the model
has seen the result either way. The hook reports and the model repairs -- the skills'
three-repair cap still caps (D2).

Exact for the file-editing tools, whose target is a field; best-effort for shell
commands, whose write targets are read out of the command line by the same patterns the
approved-zone guard uses. What a pattern cannot see (a script writing files, a generator)
the end-of-session check in `gate_on_stop.py` catches, in a git repository.

Scope, the guard's own: only inside an architecture repository (a root holding
`ea.config.yaml`), never inside the ea-skills tooling repository, only YAML files.

A gate that could not run says so by name -- no interpreter with the runtime
dependencies, a timeout, a crash. A hook that silently did nothing would look exactly
like a gate that found nothing, which is the failure this file exists to remove.
Standard library only: it runs before anything of this repository is imported, and the
gate itself runs in a child process with the plugin's own copy of the tooling.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_approved as guard  # noqa: E402 -- sibling module, stdlib only

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
YAML_SUFFIXES = {".yaml", ".yml"}
RUNTIME_MODULES = ("yaml", "jsonschema", "lxml")
TIMEOUT_SECONDS = 60
# The whole hook must finish inside the host's timeout (hooks.json: 120 s), or the host kills
# it with no output -- which reads exactly like a passing gate. Several gates run one after
# another, so each gets what is left of this budget, and a gate the budget cannot reach is
# reported as not run, by name.
BUDGET_SECONDS = 100
MIN_GATE_SECONDS = 5
MAX_FINDINGS = 8

# Governed path prefix (relative to the repository root) -> the gate that owns it.
GOVERNED: tuple[tuple[tuple[str, ...], str], ...] = (
    (("facts", "register"), "validate-facts"),
    (("facts", "questions"), "validate-facts"),
    (("facts", "entities.yaml"), "validate-facts"),
    (("model", "staging"), "validate --zone staging"),
    (("model", "approved"), "validate"),
    (("standards",), "validate-gov"),
    (("governance-log",), "validate-gov"),
    (("services",), "validate-gov"),
)

BOOT = (
    "import sys\n"
    "root = sys.argv.pop(1)\n"
    "sys.path.insert(0, root)\n"
    "from easkills.cli import main\n"
    "sys.argv[0] = 'easkills'\n"
    "sys.exit(main())\n"
)


@dataclass
class GateResult:
    gate: str
    root: Path
    ran: bool
    ok: bool = True
    errors: int = 0
    warnings: int = 0
    findings: list[dict] = field(default_factory=list)
    problem: str = ""

    @property
    def verdict(self) -> str:
        """The gate's own closing line, in the plain form the CLI prints it."""
        return f"{self.errors} error(s), {self.warnings} warning(s) -- {'PASS' if self.ok else 'FAIL'}"

    def command(self) -> str:
        return f"easkills {self.gate} --root {self.root}"

    def lines(self, severity: str, limit: int = MAX_FINDINGS) -> list[str]:
        chosen = [f for f in self.findings if f.get("severity") == severity]
        out = []
        for finding in chosen[:limit]:
            where = finding.get("file") or "-"
            if finding.get("locator"):
                where = f"{where}:{finding['locator']}"
            concept = f" [{finding['concept']}]" if finding.get("concept") else ""
            out.append(f"  {severity.upper():<7} {finding.get('code', '?')}  {where}{concept}  {finding.get('message', '')}")
        if len(chosen) > limit:
            out.append(f"  ... and {len(chosen) - limit} more -- run `{self.command()}` for the full list")
        return out


def architecture_root(path: Path) -> Path | None:
    """The nearest directory above ``path`` holding ``ea.config.yaml``, outside the tooling repo."""
    for parent in path.parents:
        if (parent / "ea.config.yaml").is_file():
            return None if guard._is_tooling_repository(path) else parent
    return None


def gate_for(path: Path) -> tuple[Path, str] | None:
    """(repository root, gate) for a written path, or None if no gate owns it."""
    if path.suffix not in YAML_SUFFIXES:
        return None
    root = architecture_root(path)
    if root is None:
        return None
    parts = path.relative_to(root).parts
    for prefix, gate in GOVERNED:
        if parts[: len(prefix)] == prefix:
            return root, gate
    return None


def written_paths(payload: dict) -> list[Path]:
    """Absolute paths this tool call wrote, as far as can be told."""
    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    raw: list[str] = []
    if tool in FILE_TOOLS:
        raw.append(str(tool_input.get("file_path") or tool_input.get("notebook_path") or ""))
    elif tool in guard.SHELL_TOOLS:
        raw += guard.shell_targets(str(tool_input.get("command") or ""), powershell=tool == "PowerShell")
    paths = []
    for text in raw:
        text = text.strip().strip("\"'")
        if not text:
            continue
        candidate = Path(text.replace("\\", "/"))
        if not candidate.is_absolute():
            candidate = cwd / candidate
        try:
            paths.append(candidate.resolve())  # one spelling per directory (8.3 short names)
        except OSError:
            paths.append(Path(os.path.normpath(str(candidate))))
    return paths


def missing_runtime() -> list[str]:
    return [name for name in RUNTIME_MODULES if importlib.util.find_spec(name) is None]


def run_gate(root: Path, gate: str, timeout: float = TIMEOUT_SECONDS) -> GateResult:
    """Run one gate in a child process and read its JSON report."""
    if timeout < MIN_GATE_SECONDS:
        return GateResult(gate, root, ran=False, problem="the hook's time budget ran out before it could start")
    if sys.version_info < (3, 11):
        return GateResult(gate, root, ran=False, problem=f"Python {sys.version.split()[0]} is older than 3.11")
    missing = missing_runtime()
    if missing:
        return GateResult(
            gate,
            root,
            ran=False,
            problem=(
                f"{sys.executable} lacks {', '.join(missing)} -- install them: "
                f"{sys.executable} -m pip install -r {PLUGIN_ROOT / 'requirements.txt'}"
            ),
        )
    handle, report_path = tempfile.mkstemp(prefix="ea-gate-", suffix=".json")
    os.close(handle)
    os.unlink(report_path)  # the gate writes it; a stale file must never be read as a result
    try:
        try:
            # `-P`: the architecture repository must not be on the import path, or a planted
            # `yaml.py` there would run in place of the real dependency on every governed write.
            done = subprocess.run(
                [sys.executable, "-P", "-c", BOOT, str(PLUGIN_ROOT), *gate.split(), "--root", str(root), "--json", report_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(root),
            )
        except subprocess.TimeoutExpired:
            return GateResult(gate, root, ran=False, problem=f"it did not finish within {int(timeout)} s")
        except OSError as exc:
            return GateResult(gate, root, ran=False, problem=f"it could not start: {exc}")
        try:
            data = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["no output"]
            return GateResult(gate, root, ran=False, problem=f"it exited {done.returncode} without a report: {tail[0]}")
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass
    summary = data.get("summary") or {}
    return GateResult(
        gate,
        root,
        ran=True,
        ok=bool(data.get("ok")),
        errors=int(summary.get("errors", 0) or 0),
        warnings=int(summary.get("warnings", 0) or 0),
        findings=[f for f in data.get("findings") or [] if isinstance(f, dict)],
    )


def message(result: GateResult, after: str) -> str:
    head = f"ea-skills gate ({result.gate}) after {after}:"
    if not result.ran:
        return (
            f"{head} the gate could not run -- {result.problem}. Nothing was checked; run "
            f"`{result.command()}` yourself before reporting the work done."
        )
    lines = [f"{head} {result.verdict}"]
    if result.errors:
        lines += result.lines("error")
        lines.append(
            "Repair these before reporting the work done (three repair rounds at most, then report "
            "what is unresolved). The approved zone is not the place to fix them."
        )
    elif result.warnings:
        lines += result.lines("warning", limit=4)
    return "\n".join(lines)


def run_within(gates: list[tuple[Path, str]], budget: float = BUDGET_SECONDS) -> list[GateResult]:
    """Run gates one after another inside one time budget; what it cannot reach is named."""
    deadline = time.monotonic() + budget
    return [run_gate(root, gate, timeout=min(TIMEOUT_SECONDS, deadline - time.monotonic())) for root, gate in gates]


def decide(payload: dict) -> dict | None:
    """The hook's JSON output for this tool call, or None for no output."""
    owned_paths: dict[tuple[Path, str], str] = {}
    for path in written_paths(payload):
        owned = gate_for(path)
        if owned is not None and owned not in owned_paths:
            owned_paths[owned] = path.relative_to(owned[0]).as_posix()
    gates = list(owned_paths)
    results = list(zip(run_within(gates), owned_paths.values()))
    if not results:
        return None
    text = "\n\n".join(message(result, f"writing {after}") for result, after in results)
    if any(result.ran and result.errors for result, _after in results):
        return {"decision": "block", "reason": text}
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print("ea-skills gate hook: unreadable hook input; no gate ran", file=sys.stderr)
        return 0
    if not isinstance(payload, dict):
        return 0
    output = decide(payload)
    if output:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
