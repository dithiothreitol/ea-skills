"""The evaluation harness talks to a language model. The core must never learn how.

SECURITY.md states "no network at runtime" and the repository's whole argument rests on
the deterministic half being deterministic: no check consults a model, and nothing
fetches anything. Adding an API-driven harness puts a network client in the repository
for the first time, so the separation stops being a convention the day someone adds a
convenient import. These tests make it structural -- the same shape as the rule that
keeps `ui` out of artifact-generating modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE = REPO_ROOT / "easkills"
HARNESS = REPO_ROOT / "eval" / "harness"

# Anything that could reach the network, plus the SDK itself.
FORBIDDEN_IN_CORE = {
    "anthropic",
    "openai",
    "httpx",
    "requests",
    "aiohttp",
    "urllib.request",
    "urllib3",
    "http.client",
    "socket",
    "ftplib",
    "telnetlib",
    "smtplib",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


@pytest.mark.parametrize("module", sorted(CORE.glob("*.py")), ids=lambda p: p.name)
def test_no_core_module_can_reach_the_network(module: Path):
    imported = _imports(module)
    offending = sorted(
        name
        for name in imported
        if name in FORBIDDEN_IN_CORE or name.split(".")[0] in {"anthropic", "openai", "httpx", "requests"}
    )
    assert not offending, (
        f"{module.name} imports {offending}: the core is offline by design (SECURITY.md), "
        "and the evaluation harness lives in eval/harness/ precisely so it can be the only "
        "thing that is not"
    )


def test_the_core_never_imports_the_harness():
    for module in CORE.glob("*.py"):
        imported = _imports(module)
        assert not any(name.startswith("eval") for name in imported), (
            f"{module.name} imports the evaluation harness; the dependency runs one way only"
        )


def test_the_sdk_is_not_a_runtime_dependency():
    runtime = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "anthropic" not in runtime, (
        "installing this tooling must never pull an API client; harness dependencies "
        "belong in requirements-eval.txt"
    )
    harness_requirements = (REPO_ROOT / "requirements-eval.txt").read_text(encoding="utf-8")
    assert "anthropic" in harness_requirements


def test_the_harness_never_reads_gold_into_the_scratch_repository():
    """The one correctness property of a blind run, asserted on the source.

    A harness that copied gold's register into the repository it is about to score
    would report a perfect number forever, and the failure would look like success.
    """
    source = (HARNESS / "run.py").read_text(encoding="utf-8")
    copied = [
        line.strip()
        for line in source.splitlines()
        if ("shutil.copy" in line or "copytree" in line) and "gold" in line
    ]
    assert copied, "expected the harness to copy inputs from the gold case"
    for line in copied:
        assert "sources" in line or "ea.config.yaml" in line, (
            f"the harness copies {line!r} out of gold -- only sources and the config may "
            "cross into a blind run"
        )


def test_the_api_key_is_never_committed():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    tracked = (REPO_ROOT / ".git").is_dir()
    if tracked:  # a source checkout, not a packaged copy
        import subprocess

        listed = subprocess.run(
            ["git", "ls-files", ".env", ".env.*"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        # `.env.example` is tracked on purpose -- it is the placeholder that tells a
        # contributor which variable to set. Everything else with that shape is a leak.
        tracked = {line for line in listed.stdout.split() if line != ".env.example"}
        assert not tracked, f"a secrets file is tracked: {sorted(tracked)}"

    example = REPO_ROOT / ".env.example"
    if example.is_file():
        body = example.read_text(encoding="utf-8")
        assert "sk-ant-..." in body or "..." in body, "the example must hold a placeholder"
        assert len([line for line in body.splitlines() if len(line) > 60]) == 0, (
            "a line long enough to be a real key is in .env.example"
        )
