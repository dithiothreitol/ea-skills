"""``init`` and ``doctor``: an adopter's repository gets the mechanism, not a sentence (D6).

Before 0.22.0 an architecture repository was a copy of ``template/`` -- which a plugin user
does not have, because a plugin is not a clone -- and everything this repository relies on
to keep its promises (CI running the gates, a nightly run that makes an expiry loud, code
owners on the signed zone, the tooling version the content was written for) was a
paragraph in GETTING-STARTED that each adopter had to turn into files by hand.

``init`` writes the scaffold from the tooling's own ``template/``, with two values pinned
to the running release: ``toolingVersion`` in ``ea.config.yaml`` (an older tool refuses the
repository by name) and the version of the composite action its workflow uses. ``doctor``
says what the machine and the repository are missing, one line each, and exits 1 when
something would make a gate wrong rather than merely slow.
"""

from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import __version__, dsl, oracle

TOOLING_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = TOOLING_ROOT / "template"
CONSTRAINTS = TOOLING_ROOT / "constraints.txt"
ACTION_REF = re.compile(r"(dithiothreitol/ea-skills@)v[0-9]+\.[0-9]+\.[0-9]+")
TOOLING_LINE = re.compile(r'^toolingVersion: .*$', re.MULTILINE)


class ScaffoldError(RuntimeError):
    pass


def init(target: Path) -> list[Path]:
    """Write a new architecture repository into ``target`` (absent or empty)."""
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ScaffoldError(f"{target} exists and is not empty; init writes a new repository, never into an old one")
    if not TEMPLATE.is_dir():
        raise ScaffoldError(f"the template is missing from this installation ({TEMPLATE})")
    shutil.copytree(TEMPLATE, target, dirs_exist_ok=True)
    config = target / "ea.config.yaml"
    text = config.read_text(encoding="utf-8")
    if not TOOLING_LINE.search(text):
        raise ScaffoldError("template/ea.config.yaml lost its toolingVersion line")
    config.write_text(TOOLING_LINE.sub(f'toolingVersion: "{__version__}"', text, count=1), encoding="utf-8", newline="\n")
    workflow = target / ".github" / "workflows" / "ea-gates.yml"
    text = workflow.read_text(encoding="utf-8")
    workflow.write_text(ACTION_REF.sub(rf"\g<1>v{__version__}", text), encoding="utf-8", newline="\n")
    return sorted(p for p in target.rglob("*") if p.is_file())


# --------------------------------------------------------------------------- doctor


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str


def pinned_versions(path: Path = CONSTRAINTS) -> dict[str, str]:
    pins: dict[str, str] = {}
    if not path.is_file():
        return pins
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([0-9][^ ;\\]*)", line)
        if match:
            pins[match.group(1).lower()] = match.group(2)
    return pins


def _version_tuple(text: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in str(text).split("."))
    except ValueError:
        return None


def doctor(root: Path | None) -> list[Check]:
    checks: list[Check] = []
    python = sys.version.split()[0]
    checks.append(
        Check("python", "ok" if sys.version_info >= (3, 11) else "fail", f"{sys.executable} is Python {python}")
    )

    pins = pinned_versions()
    drift, missing = [], []
    for name, pinned in sorted(pins.items()):
        if name == "typing-extensions" and sys.version_info >= (3, 13):
            continue  # pinned with a marker; not installed on 3.13+
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            continue
        if installed != pinned:
            drift.append(f"{name} {installed} (pinned {pinned})")
    if missing:
        checks.append(
            Check("dependencies", "fail", f"missing: {', '.join(missing)} -- {sys.executable} -m pip install --require-hashes -r {CONSTRAINTS}")
        )
    elif drift:
        checks.append(
            Check(
                "dependencies",
                "warn",
                "installed versions differ from constraints.txt: " + ", ".join(drift)
                + " -- the gates still work; generated files are byte-stable only with the pinned versions",
            )
        )
    else:
        checks.append(Check("dependencies", "ok", f"the pinned closure ({len(pins)} packages) is installed"))

    try:
        failed = oracle.failed_checksums()
        checks.append(
            Check("oracle", "fail" if failed else "ok", "pins do not verify: " + ", ".join(r.name for r in failed) if failed else "ArchiMate 3.2 oracle, every pin verified")
        )
    except oracle.OracleError as exc:
        checks.append(Check("oracle", "fail", str(exc)))

    hooks = TOOLING_ROOT / "hooks"
    wanted = ["hooks.json", "guard-approved", "run-gate", "gate-on-stop"]
    absent = [name for name in wanted if not (hooks / name).is_file()]
    if absent:
        checks.append(Check("hooks", "fail", f"missing from {hooks}: {', '.join(absent)}"))
    else:
        try:
            events = sorted(json.loads((hooks / "hooks.json").read_text(encoding="utf-8"))["hooks"])
            checks.append(Check("hooks", "ok", f"{', '.join(events)} -- active while the Claude Code plugin is enabled"))
        except (ValueError, KeyError) as exc:
            checks.append(Check("hooks", "fail", f"hooks.json is unreadable: {exc}"))

    git = shutil.which("git")
    if root is None:
        checks.append(Check("git", "ok" if git else "warn", git or "not found -- the commit is the approval record"))
        return checks

    if not git:
        checks.append(Check("git", "warn", "not found -- the commit is the approval record, and the end-of-turn gate check compares with HEAD"))
    else:
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
        checks.append(
            Check("git", "ok" if inside.returncode == 0 else "warn", "a git repository" if inside.returncode == 0 else "not a git repository -- `git init` and a first commit")
        )

    config = dsl.load_config(root)
    required = config.get("toolingVersion")
    if not required:
        checks.append(Check("toolingVersion", "warn", "not set -- `easkills init` writes it; pin the release this content is written for"))
    else:
        needed, running = _version_tuple(required), _version_tuple(__version__)
        if needed is None:
            checks.append(Check("toolingVersion", "fail", f"{required!r} is not a version (SCHEMA002)"))
        elif needed > running:
            checks.append(Check("toolingVersion", "fail", f"the repository needs {required}; this is {__version__} -- upgrade"))
        elif needed < running:
            checks.append(
                Check(
                    "toolingVersion",
                    "ok",
                    f"written for {required}, read by {__version__} -- the CHANGELOG's 'Upgrading' sections "
                    "between the two say what got stricter; raise toolingVersion once the repository is clean",
                )
            )
        else:
            checks.append(Check("toolingVersion", "ok", f"{required}, this release"))

    from . import seal

    if not seal.approved_files(root):
        checks.append(Check("seal", "ok", "the approved zone is empty"))
    elif not seal.record_files(root):
        checks.append(Check("seal", "warn", "not sealed -- `easkills promote --seal-existing --approved-by <who> --as-of <date>`"))
    else:
        problems = [f for f in seal.check_seal(root)]
        records = len(seal.record_files(root))
        checks.append(
            Check(
                "seal",
                "fail" if problems else "ok",
                f"{len(problems)} approved file(s) or record(s) fail APR001-APR003 -- run `easkills validate`" if problems else f"sealed by {records} record(s), every approved file vouched for",
            )
        )
    return checks
