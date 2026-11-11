"""What an adopter's repository is given (D6): init, the pins, the workflow, doctor, redaction.

Every file `init` writes is a promise about the adopter's CI, so each is held to something
that can fail here: the version pins equal the release, every `easkills` command the
scaffolded workflow runs exists, the hashed constraints sit inside the ranges the project
declares, `doctor` names what is wrong, and a redacted source records the original's
digest and never the map.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

from easkills import __version__, cli, dsl, redact, scaffold

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / "template" / ".github" / "workflows" / "ea-gates.yml"


def _commands() -> set[str]:
    parser = cli.build_parser()
    return set(next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction").choices)


def test_init_writes_the_template_pinned_to_this_release(tmp_path):
    target = tmp_path / "new-ea"
    written = scaffold.init(target)
    assert (target / ".github" / "CODEOWNERS") in written
    assert dsl.load_config(target)["toolingVersion"] == __version__
    workflow = (target / ".github" / "workflows" / "ea-gates.yml").read_text(encoding="utf-8")
    assert set(re.findall(r"dithiothreitol/ea-skills@(v[0-9.]+)", workflow)) == {f"v{__version__}"}
    assert (target / "governance-log" / "approvals").is_dir()


def test_init_never_writes_into_an_existing_repository(tmp_path):
    (tmp_path / "old").mkdir()
    (tmp_path / "old" / "ea.config.yaml").write_text("name: Old\n", encoding="utf-8")
    with pytest.raises(scaffold.ScaffoldError, match="not empty"):
        scaffold.init(tmp_path / "old")
    assert cli.main(["init", str(tmp_path / "old")]) == 1


def test_the_template_carries_this_release(repo_root):
    """`cp -r template` is still a documented path, so the template itself is pinned too --
    and moves with every release, like plugin.json."""
    config = yaml.safe_load((repo_root / "template" / "ea.config.yaml").read_text(encoding="utf-8"))
    assert config["toolingVersion"] == __version__
    refs = set(re.findall(r"dithiothreitol/ea-skills@(v[0-9.]+)", WORKFLOW.read_text(encoding="utf-8")))
    assert refs == {f"v{__version__}"}


def test_every_command_the_scaffolded_workflow_runs_exists():
    """The CONTRIBUTING-block test, reused: a workflow naming a command the CLI lacks fails
    an adopter's first push, in their repository, where nobody here sees it."""
    text = WORKFLOW.read_text(encoding="utf-8")
    named = set(re.findall(r"\beaskills ([a-z][a-z-]*)", text))
    assert {"validate", "validate-facts", "validate-gov", "docs", "diff", "staleness"} <= named
    assert named <= _commands(), f"the template workflow runs commands the CLI lacks: {named - _commands()}"


def test_the_workflow_and_the_action_never_interpolate_an_input_into_a_script(repo_root):
    action = (repo_root / "action.yml").read_text(encoding="utf-8")
    run_blocks = re.findall(r"run: \|\n((?:        .*\n)+)", action)
    assert run_blocks and not any("${{" in block for block in run_blocks), "inputs reach scripts via env only"
    assert "--require-hashes" in action


def test_the_constraints_pin_the_whole_runtime_closure_inside_the_declared_ranges(repo_root):
    pins = scaffold.pinned_versions(repo_root / "constraints.txt")
    project = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for requirement in project["dependencies"]:
        name, minimum = re.match(r"([A-Za-z0-9_.-]+)>=([0-9.]+)", requirement).groups()
        pinned = pins[name.lower()]
        assert tuple(int(p) for p in pinned.split(".")[:2]) >= tuple(int(p) for p in minimum.split(".")[:2]), (
            f"constraints.txt pins {name}=={pinned}, below the declared {requirement}"
        )
    text = (repo_root / "constraints.txt").read_text(encoding="utf-8")
    for name in pins:
        hashed = re.search(rf"^{re.escape(name)}==[^\n]*\\\n    --hash=sha256:[0-9a-f]{{64}}", text, re.IGNORECASE | re.MULTILINE)
        assert hashed, f"{name} is pinned without a hash"
    assert {"pyyaml", "jsonschema", "lxml", "referencing", "rpds-py", "attrs"} <= set(pins)


def test_doctor_names_what_is_missing(tmp_path):
    target = tmp_path / "new-ea"
    scaffold.init(target)
    checks = {c.name: c for c in scaffold.doctor(target)}
    assert checks["python"].status == "ok" and checks["oracle"].status == "ok"
    assert checks["toolingVersion"].status == "ok"
    assert checks["git"].status == "warn" and "git init" in checks["git"].detail
    config = target / "ea.config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace(f'"{__version__}"', '"99.0.0"'), encoding="utf-8")
    checks = {c.name: c for c in scaffold.doctor(target)}
    assert checks["toolingVersion"].status == "fail"
    assert cli.main(["doctor", "--root", str(target)]) == 1


def test_a_repository_written_for_a_newer_release_is_refused_by_name(tmp_path, capsys):
    target = tmp_path / "new-ea"
    scaffold.init(target)
    config = target / "ea.config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace(f'"{__version__}"', '"99.0.0"'), encoding="utf-8")
    assert cli.main(["validate", "--root", str(target)]) == 1
    assert "needs ea-skills 99.0.0 or later" in capsys.readouterr().out
    assert cli.main(["doctor", "--root", str(target)]) == 1, "doctor reports instead of refusing to run"


def test_redaction_records_the_originals_digest_and_never_the_map(tmp_path):
    original = tmp_path / "private" / "interview.md"
    original.parent.mkdir()
    original.write_text("# Interview\n\nJan Kowalski runs billing. Jan Kowalski says the ERP is slow.\n", encoding="utf-8")
    mapping = tmp_path / "private" / "map.yaml"
    mapping.write_text("replacements:\n  - find: Jan Kowalski\n    replace: '[billing lead]'\n  - find: Anna Nowak\n    replace: '[CFO]'\n", encoding="utf-8")
    out = tmp_path / "repo" / "facts" / "sources" / "interview.md"
    report = redact.redact(original, mapping, out)
    text = out.read_text(encoding="utf-8")
    assert "Jan Kowalski" not in text and "[billing lead] runs billing" in text
    assert report.replacements == 2 and report.unmatched == [2]
    assert report.sha256 in text
    assert "Anna Nowak" not in text and "map.yaml" not in text, "the map names what was removed"
    with pytest.raises(redact.RedactError, match="--overwrite"):
        redact.redact(original, mapping, out)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("replacements: []\n", "non-empty"),
        ("replacements:\n  - replace: x\n", "find"),
        ("replacements:\n  - find: Jan\n    replace: Jan Kowalski\n", "puts back"),
    ],
)
def test_a_map_that_cannot_redact_is_refused(tmp_path, body, message):
    original = tmp_path / "a.md"
    original.write_text("Jan\n", encoding="utf-8")
    mapping = tmp_path / "map.yaml"
    mapping.write_text(body, encoding="utf-8")
    with pytest.raises(redact.RedactError, match=message):
        redact.redact(original, mapping, tmp_path / "out.md")


def test_the_scaffold_keeps_sources_byte_exact_and_private_originals_out(repo_root):
    attributes = (repo_root / "template" / ".gitattributes").read_text(encoding="utf-8")
    assert "facts/sources/** -text" in attributes
    assert "facts/sources-private/" in (repo_root / "template" / ".gitignore").read_text(encoding="utf-8")


def test_a_later_rule_cannot_put_back_what_an_earlier_one_removed(tmp_path):
    original = tmp_path / "a.md"
    original.write_text("Jan Kowalski runs billing.\n", encoding="utf-8")
    mapping = tmp_path / "map.yaml"
    mapping.write_text(
        "replacements:\n  - find: Kowalski\n    replace: K.\n  - find: Jan K.\n    replace: Jan Kowalski (HR)\n",
        encoding="utf-8",
    )
    with pytest.raises(redact.RedactError, match="put it back"):
        redact.redact(original, mapping, tmp_path / "out.md")
    assert not (tmp_path / "out.md").exists()


def test_a_name_split_across_a_windows_line_break_is_still_found(tmp_path):
    original = tmp_path / "a.md"
    original.write_bytes(b"Meeting with Anna\r\nNowak about billing.\r\n")
    mapping = tmp_path / "map.yaml"
    mapping.write_text('replacements:\n  - find: "Anna\\nNowak"\n    replace: "[CFO]"\n', encoding="utf-8")
    report = redact.redact(original, mapping, tmp_path / "out.md")
    assert report.replacements == 1 and "[CFO] about billing" in (tmp_path / "out.md").read_text(encoding="utf-8")


def test_the_redacted_copy_does_not_carry_the_originals_name(tmp_path):
    original = tmp_path / "interview-jan-kowalski.md"
    original.write_text("Jan Kowalski runs billing.\n", encoding="utf-8")
    mapping = tmp_path / "map.yaml"
    mapping.write_text("replacements:\n  - find: Jan Kowalski\n    replace: '[lead]'\n", encoding="utf-8")
    redact.redact(original, mapping, tmp_path / "out.md")
    assert "kowalski" not in (tmp_path / "out.md").read_text(encoding="utf-8").lower()
