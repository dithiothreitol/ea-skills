"""Stop hook: no turn ends on governed changes whose gate result the model has not seen (D1).

`run_gate.py` runs the owning gate after every write it can see -- exactly for the
file-editing tools, by pattern for shell commands. What no pattern sees (a script that
writes files, a generator, a hand edit in another window) is caught here, when the model
is about to end its turn: if the working tree differs from `HEAD` under a governed path,
the owning gates run, and errors stop the turn once with the findings.

**Once.** The hook reports and the model repairs or reports what it could not; it never
grinds (D2). It passes whenever the host says the turn is already continuing because of a
stop hook (`stop_hook_active`), and it remembers, per session, which failure it already
reported -- so an unchanged failure left over from earlier work is said once, not at the
end of every turn. That memory is the only state it keeps: a digest per session in the
temporary directory, never anything inside the repository.

**In a git repository.** "What changed" is the difference from `HEAD`; an architecture
repository is a git repository by design (the commit is the approval record). Outside
one the hook cannot tell what changed, says so to the person once per session, and lets
the turn end.

Same scope as the other hooks: only inside an architecture repository, never inside the
ea-skills tooling repository. A passing gate produces no output -- any output from a Stop
hook would continue the turn.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_approved as guard  # noqa: E402
import run_gate  # noqa: E402

GOVERNED_DIRS = sorted({"/".join(prefix) for prefix, _gate in run_gate.GOVERNED})
# Inside the host's Stop timeout (hooks.json: 300 s) with room to print: up to four gates
# can run here, one after another, and a killed hook says nothing at all.
BUDGET_SECONDS = 270


def repository_root(cwd: Path) -> Path | None:
    # Resolved, because git reports long paths and a Windows working directory can arrive in
    # its 8.3 short form (C:\Users\DARIUS~1\...): two spellings of one directory must not
    # make a relative path fail and the hook crash -- a crashed hook reports nothing.
    cwd = cwd.resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "ea.config.yaml").is_file():
            return None if guard._is_tooling_repository(candidate / "model") else candidate
    return None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done if done.returncode == 0 else None


def changed_paths(root: Path) -> list[Path] | None:
    """Governed paths that differ from HEAD (untracked included), or None outside git.

    Porcelain paths are relative to the git top level, which is not the architecture
    repository's root when the repository is a directory inside a larger checkout.
    """
    top = _git(root, "rev-parse", "--show-toplevel")
    if top is None or not top.stdout.strip():
        return None
    toplevel = Path(top.stdout.strip()).resolve()
    done = _git(root, "status", "--porcelain", "-z", "--untracked-files=all", "--", *GOVERNED_DIRS)
    if done is None:
        return None
    paths: list[Path] = []
    entries = done.stdout.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, name = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            index += 1  # the rename's source path follows; the destination is what exists now
        # A deletion is a change too: the file is gone, and the gate runs on what remains --
        # which is exactly where a reference to the deleted content now dangles.
        paths.append(Path(os.path.normpath(str(toplevel / name))))
    return paths


def dependent_model_gates(root: Path) -> list[str]:
    """The model gates a fact change can break: approved always, staging when it exists."""
    gates = ["validate"]
    staging = root / "model" / "staging"
    if staging.is_dir() and any(p.suffix in run_gate.YAML_SUFFIXES for p in staging.rglob("*")):
        gates.append("validate --zone staging")
    return gates


def _state_file(session: str) -> Path:
    safe = hashlib.sha256(session.encode("utf-8")).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / "ea-skills-hooks" / f"stop-{safe}.json"


def _already_said(session: str, key: str) -> bool:
    """True if this session was already told exactly this; records it otherwise."""
    if not session:
        return False
    path = _state_file(session)
    try:
        said = set(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        said = set()
    if key in said:
        return True
    said.add(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sorted(said)), encoding="utf-8")
    except OSError:
        pass  # without memory the hook may repeat itself; it must never fail the turn for it
    return False


def decide(payload: dict) -> dict | None:
    if payload.get("stop_hook_active"):
        return None
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    root = repository_root(cwd)
    if root is None:
        return None
    session = str(payload.get("session_id") or "")
    changed = changed_paths(root)
    if changed is None:
        if _already_said(session, "no-git"):
            return None
        return {
            "systemMessage": (
                "ea-skills: this architecture repository is not a git repository, so the "
                "end-of-turn gate check cannot tell what changed and did not run. `git init` "
                "and a first commit turn it on."
            )
        }
    gates: dict[tuple[Path, str], list[str]] = {}
    for path in changed:
        owned = run_gate.gate_for(path)
        if owned is None:
            continue
        relative = path.relative_to(owned[0]).as_posix()
        gates.setdefault(owned, []).append(relative)
        if owned[1] == "validate-facts":
            # The model gate re-verifies every fact it cites, so a changed or deleted fact
            # can break the model without a model file changing: gate both zones too.
            for dependent in dependent_model_gates(owned[0]):
                gates.setdefault((owned[0], dependent), []).append(relative)
    failing: list[str] = []
    ordered = sorted(gates.items(), key=lambda item: (str(item[0][0]), item[0][1]))
    results = run_gate.run_within([owned for owned, _files in ordered], budget=BUDGET_SECONDS)
    for ((_gate_root, _gate), files_changed), result in zip(ordered, results):
        if result.ran and not result.errors:
            continue
        files = ", ".join(sorted(files_changed)[:5]) + (" ..." if len(files_changed) > 5 else "")
        failing.append(run_gate.message(result, f"this turn's uncommitted changes ({files})"))
    if not failing:
        return None
    text = "\n\n".join(failing)
    if _already_said(session, hashlib.sha256(text.encode("utf-8")).hexdigest()):
        return None
    return {
        "decision": "block",
        "reason": (
            text
            + "\n\nRepair what you can, or end by naming what is still failing -- do not report this "
            "work as done while its gate fails. This check runs once per failure."
        ),
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        print("ea-skills stop hook: unreadable hook input; no gate ran", file=sys.stderr)
        return 0
    if not isinstance(payload, dict):
        return 0
    output = decide(payload)
    if output:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
