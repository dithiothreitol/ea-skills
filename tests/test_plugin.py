"""The plugin surface: manifests, skill frontmatter, the approved-zone hook, the wrapper.

None of this is consulted by the deterministic core, and all of it decides whether the
skills reach a host at all. A misspelled frontmatter key is ignored by the host without a
word (the host's own validator passes it -- checked when this file was written), a hook
that never fires looks exactly like a hook that is never needed, and a manifest whose
version drifts from the package's pins users to a release that does not match the code.
So each property is pinned here, the same bargain the documentation tests make.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(p for p in (REPO_ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())

# The frontmatter keys Claude Code documents for a skill. The host ignores anything else
# silently, so the vocabulary is closed here instead -- an `allowed-tool` typo would
# otherwise leave every invocation prompting for permission and nobody would know why.
SKILL_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
    "metadata", "license", "compatibility",
}
EASKILLS_TOOLS = {"Bash(easkills *)", "Bash(python -m easkills *)"}


def _frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    head, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(head), body


# ------------------------------------------------------------------------- manifests


def test_the_plugin_manifest_carries_the_package_version():
    manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert manifest["name"] == "ea-skills"
    assert manifest["version"] == project["version"], (
        "plugin.json pins installed users to its version; it must be the release the code is"
    )
    assert manifest["license"] == project["license"]


def test_the_marketplace_serves_this_repository_as_the_plugin():
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["owner"]["name"]
    assert [entry["name"] for entry in market["plugins"]] == ["ea-skills"]
    assert market["plugins"][0]["source"] == "./", "the repository root is the plugin root (D1)"


# ------------------------------------------------------------------- skill frontmatter


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_every_skill_uses_only_documented_frontmatter_keys(skill):
    meta, _ = _frontmatter(skill / "SKILL.md")
    unknown = set(meta) - SKILL_KEYS
    assert not unknown, f"{skill.name}: unknown frontmatter key(s) {sorted(unknown)} -- the host ignores them silently"
    assert meta["name"] == skill.name
    listing = str(meta["description"]) + str(meta.get("when_to_use", ""))
    assert len(listing) <= 1536, f"{skill.name}: the host truncates the listing at 1536 characters"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_every_skill_pre_approves_the_cli_and_nothing_else(skill):
    meta, _ = _frontmatter(skill / "SKILL.md")
    tools = set(meta.get("allowed-tools") or [])
    assert tools == EASKILLS_TOOLS, (
        f"{skill.name}: allowed-tools should pre-approve the deterministic CLI and only that -- "
        f"found {sorted(tools)}. In particular, nothing that spends money (the eval harness) "
        "may run without a prompt."
    )


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.name)
def test_skill_prose_names_the_command_the_plugin_puts_on_path(skill):
    _, body = _frontmatter(skill / "SKILL.md")
    # Naming the clone spelling to explain it is fine (ea-run does); *instructing* it is not.
    assert not re.search(r"python -m easkills [a-z]", body), (
        f"{skill.name}: an installed plugin is not importable as `python -m easkills`; the "
        "skills say `easkills`, which the plugin's bin/ provides"
    )


def test_only_promotion_is_withheld_from_model_invocation():
    withheld = {p.name for p in SKILLS if _frontmatter(p / "SKILL.md")[0].get("disable-model-invocation")}
    assert withheld == {"ea-approve"}, (
        "promotion asserts a human sign-off, so it is the one skill a model must not load on "
        f"its own initiative; found {sorted(withheld)}"
    )


# ------------------------------------------------------------------------ executables


@pytest.mark.parametrize("relative", ["bin/easkills", "hooks/guard-approved"])
def test_the_scripts_the_host_runs_are_executable_in_git(relative):
    if not (REPO_ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listed = subprocess.run(
        ["git", "ls-files", "-s", relative], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.split()
    if not listed:
        pytest.skip(f"{relative} is not committed yet")
    assert listed[0] == "100755", f"{relative} must be committed executable, or the host cannot run it"


def _shell() -> str | None:
    return shutil.which("sh") or shutil.which("bash")


def test_the_wrapper_runs_the_cli():
    shell = _shell()
    if not shell:
        pytest.skip("no POSIX shell")
    env = {**os.environ, "EASKILLS_PYTHON": sys.executable}
    done = subprocess.run(
        [shell, str(REPO_ROOT / "bin" / "easkills"), "oracle-info"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        cwd=Path(os.environ.get("TMPDIR", os.environ.get("TEMP", "/"))),
    )
    assert done.returncode == 0, done.stderr
    assert "ArchiMate version" in done.stdout


# ------------------------------------------------------------------------------ hook


def _guard():
    spec = importlib.util.spec_from_file_location("guard_approved", REPO_ROOT / "hooks" / "guard_approved.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def ea_repo(tmp_path):
    (tmp_path / "ea.config.yaml").write_text("name: Test\n", encoding="utf-8")
    (tmp_path / "model" / "approved").mkdir(parents=True)
    (tmp_path / "model" / "staging").mkdir(parents=True)
    return tmp_path


def test_hooks_json_runs_the_guard_on_every_writing_tool():
    config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    groups = config["hooks"]["PreToolUse"]
    matched = {tool for group in groups for tool in group["matcher"].split("|")}
    assert {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"} <= matched
    commands = [hook["command"] for group in groups for hook in group["hooks"]]
    assert any("hooks/guard-approved" in command for command in commands)


@pytest.mark.parametrize(
    ("tool", "tool_input", "refused"),
    [
        ("Write", {"file_path": "model/approved/application.yaml"}, True),
        ("Edit", {"file_path": "model/approved/sub/x.yaml"}, True),
        ("Write", {"file_path": "model/staging/application.yaml"}, False),
        ("Read", {"file_path": "model/approved/application.yaml"}, False),
        ("Bash", {"command": "cat model/approved/application.yaml"}, False),
        ("Bash", {"command": "cp model/staging/a.yaml model/approved/"}, True),
        ("Bash", {"command": "cp model/approved/a.yaml model/staging/a.yaml"}, False),
        ("Bash", {"command": "mv model/staging/a.yaml model/approved/a.yaml"}, True),
        ("Bash", {"command": "echo x > model/approved/a.yaml"}, True),
        ("Bash", {"command": "echo x >> 'model/approved/a.yaml'"}, True),
        ("Bash", {"command": "easkills validate --root . 2>&1 | tee /tmp/out.txt"}, False),
        ("Bash", {"command": "sed -i 's/a/b/' model/approved/a.yaml"}, True),
        ("Bash", {"command": "sed 's/a/b/' model/approved/a.yaml > model/staging/a.yaml"}, False),
        ("Bash", {"command": "rm model/approved/a.yaml"}, True),
        ("Bash", {"command": "git rm model/approved/a.yaml"}, True),
        ("Bash", {"command": "easkills promote --root ."}, False),
        ("Bash", {"command": "python -m easkills promote --root . --file model/staging/a.yaml"}, False),
        ("Bash", {"command": "easkills promote --root . && rm model/approved/b.yaml"}, True),
        ("PowerShell", {"command": "Set-Content -Path model/approved/a.yaml -Value x"}, True),
        ("PowerShell", {"command": "Copy-Item model/approved/a.yaml model/staging/a.yaml"}, False),
        ("PowerShell", {"command": "Copy-Item model/staging/a.yaml -Destination model/approved/"}, True),
        ("PowerShell", {"command": "Get-Content model/approved/a.yaml"}, False),
    ],
)
def test_the_guard_refuses_exactly_the_writes_into_the_approved_zone(ea_repo, tool, tool_input, refused):
    payload = {"tool_name": tool, "tool_input": tool_input, "cwd": str(ea_repo)}
    message = _guard().decide(payload)
    assert bool(message) is refused, f"{tool} {tool_input} -> {message!r}"
    if refused:
        assert "easkills promote" in message and "model/staging/" in message


def test_the_guard_reads_absolute_and_windows_paths(ea_repo):
    guard = _guard()
    target = ea_repo / "model" / "approved" / "a.yaml"
    for raw in (str(target), str(target).replace("/", "\\")):
        assert guard.decide({"tool_name": "Write", "tool_input": {"file_path": raw}, "cwd": "/"})


def test_the_guard_leaves_a_model_approved_folder_outside_an_architecture_repository(tmp_path):
    (tmp_path / "model" / "approved").mkdir(parents=True)
    payload = {"tool_name": "Write", "tool_input": {"file_path": "model/approved/a.txt"}, "cwd": str(tmp_path)}
    assert _guard().decide(payload) is None, "no ea.config.yaml, no architecture repository, no guard"


def test_the_guard_leaves_the_tooling_repositorys_own_fixtures_alone():
    target = REPO_ROOT / "eval" / "example" / "model" / "approved" / "application.yaml"
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(target)}, "cwd": str(REPO_ROOT)}
    assert _guard().decide(payload) is None, "maintaining gold and fixtures is not a promotion"


def test_the_guard_script_exits_2_with_the_reason_and_fails_open_on_garbage(ea_repo):
    script = REPO_ROOT / "hooks" / "guard_approved.py"
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "model/approved/a.yaml"}, "cwd": str(ea_repo)})
    refused = subprocess.run([sys.executable, str(script)], input=payload, capture_output=True, text=True)
    assert refused.returncode == 2 and "easkills promote" in refused.stderr
    garbage = subprocess.run([sys.executable, str(script)], input="not json", capture_output=True, text=True)
    assert garbage.returncode == 0, "a guard that cannot parse its input must not block the host"


# ----------------------------------------------------------------------------- evals

EVAL_PROMPT_KEYS = {
    "schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome",
    "model", "max_turns", "timeout_seconds", "allowed_tools", "append_system_prompt", "env",
}
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
CASES = sorted(p for p in (REPO_ROOT / "evals").iterdir() if p.is_dir() and p.name != "results")


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_every_eval_case_loads(case):
    """`claude plugin eval` rejects an unknown prompt.md key and a case with no grader."""
    prompt = case / "prompt.md"
    assert prompt.is_file()
    meta, body = _frontmatter(prompt)
    assert set(meta) <= EVAL_PROMPT_KEYS, f"{case.name}: unknown prompt.md key(s) {sorted(set(meta) - EVAL_PROMPT_KEYS)}"
    assert body.strip(), f"{case.name}: empty prompt"
    graders = sorted((case / "graders").glob("*.md"))
    assert graders, f"{case.name}: a case without a grader fails to load"
    for grader in graders:
        spec, _ = _frontmatter(grader)
        assert spec["type"] in GRADER_TYPES, f"{grader}: unknown grader type {spec['type']!r}"
        for key in ("input_match", "pattern"):
            if key in spec:
                re.compile(spec[key])  # the host runs them as JavaScript; the subset used here is shared
    case_yaml = case / "case.yaml"
    if case_yaml.is_file():
        spec = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        assert spec["schema_version"] == "1.1" and spec["name"] == case.name
        script = spec.get("context", {}).get("scaffold_script")
        if script:
            source = (case / script).read_text(encoding="utf-8")
            for relative in re.findall(r'\$root/([\w./-]+)', source):
                assert (REPO_ROOT / relative.rstrip("/.")).exists(), f"{case.name}: scaffold copies a missing {relative}"


def test_the_marker_grader_catches_prose_written_into_a_skeleton(tmp_path):
    """The one regex grader encodes a judgement, so it is proved against both answers."""
    spec, _ = _frontmatter(REPO_ROOT / "evals" / "proposals-stay-skeletons" / "graders" / "no-prose-written.md")
    pattern = re.compile(spec["pattern"])
    skeleton = "documentation: >-\n      PROPOSED -- state the business outcome for 'X'.\n"
    assert not pattern.search(skeleton)
    assert pattern.search("documentation: >-\n      One customer record finance trusts.\n")
    assert pattern.search("documentation: One customer record finance trusts.\n")
