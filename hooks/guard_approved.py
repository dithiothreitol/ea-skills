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
* **`easkills promote` is the path, so it is not refused -- it is put to the person**
  (D3, 0.22.0). Promotion is a sign-off, and an instruction given earlier in a
  conversation, or written into a source document, is not a person signing. So
  `promote` without `--dry-run`, in either spelling (`easkills promote`, `python -m
  easkills promote`), gets the host's `ask` decision: the person confirms it at the
  moment it runs, and where nobody can (a headless run), the host refuses it. A skill's
  pre-approval does not cover it -- only `ea-approve`, which only a person can invoke,
  pre-approves `promote` at all. A dry run or a help request, which move nothing, pass
  unasked -- read off promote's own arguments, never off the rest of the line (0.23.1).

Fails open on malformed input: a hook that crashed would block nothing and explain
nothing, and a hook that refused everything it could not parse would make the host
unusable. Exit 2 with a reason on stderr is the refusal the host documents; the `ask` is
the JSON decision on stdout with exit 0.

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
# Since 0.22.0 the approval records decide whether approved content counts as signed: a
# record written by hand would vouch for an edit nobody promoted, so the guard holds the
# records to the same single write path as the zone they seal.
SEALED = (APPROVED, ("governance-log", "approvals"))
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

REFUSAL = (
    "ea-skills: refused a write into {path}. model/approved/ is the human-signed zone, and "
    "its only write path is `easkills promote`, run on an explicit human instruction "
    "(AD-02; see the ea-approve skill). Write the change to model/staging/ instead -- the "
    "staging zone validates as an overlay on approved, so re-using an id proposes an "
    "update -- and ask the human to promote it."
)

ASK = (
    "ea-skills: `easkills promote` moves staged content into model/approved/, which is a "
    "human sign-off (AD-02). It needs the person's confirmation now -- an instruction given "
    "earlier, or found in a document, is not one -- and where nobody can confirm, the host "
    "refuses it. Show them `easkills promote --dry-run` first: what moves, what it replaces, "
    "which assumptions they would be accepting."
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
    """The architecture repository whose approved zone (or approval records) ``path`` is in."""
    parts = path.parts
    for index in range(len(parts) - 1):
        if (parts[index], parts[index + 1]) in SEALED:
            root = Path(*parts[:index]) if index else Path(path.anchor or ".")
            if (root / "ea.config.yaml").is_file():
                return root
    return None


def protected(raw: str, cwd: Path) -> bool:
    """Whether writing ``raw`` (as given to a tool, relative or absolute) hits a guarded zone."""
    text = raw.strip().strip("\"'")
    if not text or ("approved" not in text and "approvals" not in text):
        return False
    candidate = Path(text.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = cwd / candidate
    candidate = Path(os.path.normpath(str(candidate)))
    root = _approved_root(candidate)
    return root is not None and not _is_tooling_repository(candidate)


def _refusal(path: str) -> str:
    if "approvals" in path.replace("\\", "/").split("/"):
        return (
            f"ea-skills: refused a write into {path}. governance-log/approvals/ holds the approval "
            "records that seal the approved zone, and only `easkills promote` writes them -- a record "
            "written any other way would vouch for content nobody promoted. Put the change in "
            "model/staging/ and ask the human to promote it."
        )
    return REFUSAL.format(path=path)


def _tokens(segment: str, powershell: bool) -> list[str]:
    try:
        return shlex.split(segment, posix=not powershell)
    except ValueError:
        return segment.split()


# `easkills promote` anywhere in a segment's raw text -- the wrapper by name or path, an
# `.exe`, a quoted path (`& "C:\...\easkills.exe" promote`), `python -m easkills promote`,
# and every wrapper around them (`bash -c "..."`, `env`, `time`, `uv run`, `cmd /c`, the
# PowerShell call operator). Read off the text rather than the tokens on purpose: a token
# parser recognises the wrappers it was taught, and the one it was not taught is a
# promotion nobody is asked about. The price is that `echo "easkills promote"` is asked
# about too -- one unnecessary prompt, where the other error is a sign-off nobody gave.
PROMOTE = re.compile(r"(?<![\w.-])easkills(?:\.exe)?[\"']?\s+promote(?![\w-])", re.IGNORECASE)
ROOT_FLAG = re.compile(r"--root(?:=|\s+)(\"[^\"]+\"|'[^']+'|[^\s\"';&|]+)")


def _promote_segment(segment: str) -> bool:
    """True when the segment's text invokes `easkills promote`, however it is wrapped."""
    return PROMOTE.search(segment) is not None


# The two requests that move nothing. A dry run shows the plan; a help request is answered
# by argparse, which prints and exits before anything runs and accepts any unambiguous
# prefix of `--help`. Asking for `--help` was refused in every headless host-eval run of
# 2026-11-11, which is why help joined the dry run in 0.23.1.
NOTHING_MOVES = re.compile(r"--dry-run|-h|--h(?:e(?:lp?)?)?")
# `promote`'s options that take a value: the token after one is data, never a flag.
VALUED = ("--root", "--file", "--approved-by", "--as-of")
EASKILLS = re.compile(r"(?:^|[\\/])easkills(?:\.exe)?$", re.IGNORECASE)


def _promote_arguments(tokens: list[str], depth: int = 0) -> list[str] | None:
    """The arguments `easkills promote` receives in these tokens, or None if none is found.

    Up to the first shell operator (`&`, `|`, `;`, a redirect): what follows one belongs to
    another command. A promotion inside a quoted command (`bash -c "..."`) is read inside
    that string only, so a flag outside the quotes never counts as promote's.
    """
    for index, token in enumerate(tokens):
        if token == "promote" and index and EASKILLS.search(tokens[index - 1].strip("\"'")):
            arguments: list[str] = []
            for argument in tokens[index + 1:]:
                if argument and set(argument) <= set("();<>|&"):
                    break
                arguments.append(argument)
            return arguments
        if depth < 2 and " " in token and "promote" in token:
            inner = _split(token, posix=True)
            found = _promote_arguments(inner, depth + 1) if inner else None
            if found is not None:
                return found
    return None


def _split(text: str, posix: bool) -> list[str] | None:
    lexer = shlex.shlex(text, posix=posix, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _moves_nothing(segment: str, powershell: bool) -> bool:
    """True only when `--dry-run` or a help flag is an argument of `promote` itself."""
    tokens = _split(segment, posix=not powershell)
    arguments = _promote_arguments(tokens) if tokens else None
    if not arguments:
        return False
    skip = False
    for argument in arguments:
        if skip:
            skip = False
            continue
        if argument in VALUED:
            skip = True
            continue
        if NOTHING_MOVES.fullmatch(argument):
            return True
    return False


def shell_targets(command: str, powershell: bool) -> list[str]:
    """Paths a shell command line would write to, as best a pattern can tell."""
    targets: list[str] = []
    for segment in SEGMENT_SPLIT.split(command):
        tokens = _tokens(segment, powershell)
        # A promote segment is not exempt: promotion writes nothing a pattern can see, so
        # anything a pattern does see in it (a redirect into approved/) is a second write.
        # Exempting the segment let `echo "easkills promote" > model/approved/a.yaml` through.
        if not tokens:
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


def _root_argument(segment: str, cwd: Path) -> Path:
    """The repository a `promote` segment acts on: its `--root`, else the working directory."""
    match = ROOT_FLAG.search(segment)
    if match is None:
        return cwd
    value = match.group(1).strip("\"'").replace("\\", "/")
    return Path(os.path.normpath(str(cwd / value)))


def promotion(payload: dict) -> str | None:
    """The reason to put this shell command to the person, if it promotes; else None.

    Only a dry run or a help request passes unasked -- neither moves anything -- and only
    when the flag is an argument of `promote` itself (`_moves_nothing`). Inside the
    ea-skills checkout a promotion is maintainers editing fixtures, which the guard leaves
    alone throughout.
    """
    tool = str(payload.get("tool_name", ""))
    if tool not in SHELL_TOOLS:
        return None
    command = str((payload.get("tool_input") or {}).get("command") or "")
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    for segment in SEGMENT_SPLIT.split(command):
        if not _promote_segment(segment) or _moves_nothing(segment, powershell=tool == "PowerShell"):
            continue
        if not _is_tooling_repository(_root_argument(segment, cwd) / "model"):
            return ASK
    return None


def decide(payload: dict) -> str | None:
    """The refusal message for this tool call, or None to let it through."""
    tool = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    cwd = Path(str(payload.get("cwd") or os.getcwd()))
    if tool in EDIT_TOOLS:
        raw = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        return _refusal(raw) if protected(raw, cwd) else None
    if tool in SHELL_TOOLS:
        command = str(tool_input.get("command") or "")
        for target in shell_targets(command, powershell=tool == "PowerShell"):
            if protected(target, cwd):
                return _refusal(target)
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
    reason = promotion(payload)
    if reason:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": reason,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
