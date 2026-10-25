"""PreToolUse hook: the approved zone changes only through `easkills promote` (AD-02).

The two-zone design has always said that `model/approved/` is human-signed content and
that promotion is the only write path into it. Until this hook, that was a sentence in
`ea-approve` -- an instruction an agent could forget, misread, or be talked out of. A rule
that must hold every time belongs in a mechanism, so this file is the mechanism: the host
runs it before every file-editing or shell tool call, and a call that would write under an
architecture repository's `model/approved/` by any other route is refused with the reason.

Exact for the file-editing tools (Write, Edit, MultiEdit, NotebookEdit), whose target
path is a field. **Best-effort for shell commands** (Bash, PowerShell), whose target has to
be read out of a command line: redirections, the usual file-mutating commands, and the
PowerShell cmdlets that write. A determined shell one-liner can get past a pattern; the
gate this protects is still the promotion gate plus the git commit that records it. What
the hook buys is that an agent cannot bypass the gate *by accident*.

Scope, so it never fires where it should not:

* **Only inside an architecture repository** -- a `model/approved/` whose repository root
  (the directory holding `model/`) carries an `ea.config.yaml`. A project that merely
  happens to have a `model/approved` folder is left alone.
* **Never inside the ea-skills tooling repository itself.** Its worked example, golden
  cases and negative fixtures are architecture repositories by shape, and editing them is
  the deliberate, reviewed work of maintaining the tooling -- not a promotion.
* **`easkills promote` is the path, so it passes** -- in either spelling
  (`easkills promote`, `python -m easkills promote`).

Fails open on malformed input: a hook that crashed would block nothing and explain
nothing, and a hook that refused everything it could not parse would make the host
unusable. Exit 2 with a reason on stderr is the refusal the host documents.

Standard library only: this runs in whatever interpreter the hook shell finds, before
anything of this repository has been imported.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

APPROVED = ("model", "approved")
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

REFUSAL = (
    "ea-skills: refused a write into {path}. model/approved/ is the human-signed zone, and "
    "its only write path is `easkills promote`, run on an explicit human instruction "
    "(AD-02; see the ea-approve skill). Write the change to model/staging/ instead -- the "
    "staging zone validates as an overlay on approved, so re-using an id proposes an "
    "update -- and ask the human to promote it."
)

# POSIX commands that write to every path argument they are given.
WRITE_ANY = {"rm", "rmdir", "touch", "truncate", "tee", "mkdir", "shred", "unlink"}
# POSIX commands whose *last* operand is the destination; the others are sources, and
# copying out of the approved zone (to propose an update in staging) is legitimate.
WRITE_LAST = {"cp", "mv", "install", "ln", "rsync"}
# Editors-in-place: they only write when told to.
IN_PLACE = {"sed": "-i", "perl": "-i"}
# PowerShell cmdlets (and their aliases) that write to their path argument(s).
PS_WRITE_ANY = {
    "set-content", "sc", "add-content", "ac", "out-file", "new-item", "ni",
    "remove-item", "ri", "del", "erase", "rd", "clear-content", "clc",
}
PS_WRITE_DEST = {"copy-item", "cpi", "copy", "move-item", "mi", "move"}
PS_PATH_PARAMS = {"-path", "-literalpath", "-filepath", "-destination"}

SEGMENT_SPLIT = re.compile(r"\|\||&&|[;|\n]")
REDIRECT = re.compile(r"(?:^|[\s0-9])>>?\|?\s*(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")


def _is_tooling_repository(path: Path) -> bool:
    """True inside a checkout of ea-skills itself (fixtures and gold live there)."""
    for parent in path.parents:
        if (parent / "easkills" / "__init__.py").is_file() and (parent / "oracle" / "relationships.xml").is_file():
            return True
    return False


def _approved_root(path: Path) -> Path | None:
    """The architecture repository whose approved zone ``path`` is in, or None."""
    parts = path.parts
    for index in range(len(parts) - 1):
        if (parts[index], parts[index + 1]) == APPROVED:
            root = Path(*parts[:index]) if index else Path(path.anchor or ".")
            if (root / "ea.config.yaml").is_file():
                return root
    return None


def protected(raw: str, cwd: Path) -> bool:
    """Whether writing ``raw`` (as given to a tool, relative or absolute) hits a guarded zone."""
    text = raw.strip().strip("\"'")
    if not text or "approved" not in text:
        return False
    candidate = Path(text.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = cwd / candidate
    candidate = Path(os.path.normpath(str(candidate)))
    root = _approved_root(candidate)
    return root is not None and not _is_tooling_repository(candidate)


def _tokens(segment: str, powershell: bool) -> list[str]:
    try:
        return shlex.split(segment, posix=not powershell)
    except ValueError:
        return segment.split()


def _promote_segment(tokens: list[str]) -> bool:
    joined = " ".join(tokens)
    return bool(re.search(r"\beaskills\s+promote\b", joined))


def shell_targets(command: str, powershell: bool) -> list[str]:
    """Paths a shell command line would write to, as best a pattern can tell."""
    targets: list[str] = []
    for segment in SEGMENT_SPLIT.split(command):
        tokens = _tokens(segment, powershell)
        if not tokens or _promote_segment(tokens):
            continue
        for match in REDIRECT.finditer(segment):
            targets.append(match.group(1))
        name = tokens[0].lower().rsplit("/", 1)[-1]
        args = tokens[1:]
        if powershell:
            named: list[tuple[str, str]] = []
            positional: list[str] = []
            index = 0
            while index < len(args):
                token = args[index]
                if token.lower() in PS_PATH_PARAMS and index + 1 < len(args):
                    named.append((token.lower(), args[index + 1]))
                    index += 2
                    continue
                if not token.startswith("-"):
                    positional.append(token)
                index += 1
            if name in PS_WRITE_ANY:
                targets += [value for _, value in named] + positional
            elif name in PS_WRITE_DEST:
                destinations = [value for param, value in named if param == "-destination"]
                targets += destinations or positional[1:2]
            continue
        operands = [token for token in args if not token.startswith("-")]
        if name == "git" and args[:1] in (["mv"], ["rm"]):
            targets += [token for token in args[1:] if not token.startswith("-")]
        elif name in WRITE_ANY:
            targets += operands
        elif name in WRITE_LAST and operands:
            targets.append(operands[-1])
        elif name in IN_PLACE and any(token.startswith(IN_PLACE[name]) for token in args):
            targets += operands
    return targets


def decide(payload: dict) -> str | None:
    """The refusal message for this tool call, or None to let it through."""
    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    if tool in EDIT_TOOLS:
        raw = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        return REFUSAL.format(path=raw) if protected(raw, cwd) else None
    if tool in SHELL_TOOLS:
        command = str(tool_input.get("command") or "")
        for target in shell_targets(command, powershell=tool == "PowerShell"):
            if protected(target, cwd):
                return REFUSAL.format(path=target)
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    message = decide(payload)
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
