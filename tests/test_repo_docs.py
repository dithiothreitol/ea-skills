"""The documentation makes checkable claims; these tests check them.

A README that states a count, a CONTRIBUTING that says "CI runs exactly this", or a CLI
reference that lists a flag are all assertions about the repository. Left unchecked they
rot silently, and a contributor who trusts them loses the round-trip. So every claim of
that shape is mechanically verified here -- the same bargain the rest of the repository
makes with the model: judgement in prose, proof in code.
"""

from __future__ import annotations

import argparse
import re

import pytest

from easkills import cli

DOC_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/CLI.md",
    "docs/GETTING-STARTED.md",
    "docs/RULES.md",
)


def _read(repo_root, relative: str) -> str:
    return (repo_root / relative).read_text(encoding="utf-8")


def _subparsers() -> dict[str, argparse.ArgumentParser]:
    parser = cli.build_parser()
    for action in parser._actions:  # argparse exposes subcommands nowhere public
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    raise AssertionError("the CLI parser has no subcommands")


def _implemented_rule_codes(repo_root) -> list[str]:
    rules = _read(repo_root, "docs/RULES.md").split("## Not yet implemented", 1)[0]
    return re.findall(r"^\| `([A-Z]+\d{3})`", rules, re.MULTILINE)


def _easkills_invocations(text: str) -> set[str]:
    """Normalized ``python -m easkills ...`` command lines found in a block of text."""
    found: set[str] = set()
    for line in text.splitlines():
        start = line.find("python -m easkills")
        if start < 0:
            continue
        command = line[start:]
        for terminator in ("#", "&&", "||", ";", "|", "`"):
            cut = command.find(terminator)
            if cut >= 0:
                command = command[:cut]
        found.add(" ".join(command.split()))
    return found


def test_documented_rule_count_matches_the_catalogue(repo_root):
    """The badge and the docs index both state a rule count; RULES.md is the truth."""
    codes = _implemented_rule_codes(repo_root)
    assert len(codes) == len(set(codes)), "duplicate rule codes in docs/RULES.md"
    readme = _read(repo_root, "README.md")
    claimed = re.findall(r"validation%20rules-(\d+)", readme) + re.findall(r"(\d+) validation rules", readme)
    assert claimed, "the README no longer states a rule count -- update this test with it"
    for number in claimed:
        assert int(number) == len(codes), (
            f"README claims {number} validation rules, docs/RULES.md lists {len(codes)}"
        )


def test_documented_skill_count_matches_the_skills_directory(repo_root):
    skills = sorted(p for p in (repo_root / "skills").iterdir() if (p / "SKILL.md").is_file())
    assert skills, "no skills found"
    for relative in DOC_FILES:
        for number in re.findall(r"(\d+)\s*(?:\*\*)?\s*\[?agent skills", _read(repo_root, relative)):
            assert int(number) == len(skills), (
                f"{relative} claims {number} agent skills, skills/ holds {len(skills)}"
            )


def test_every_debt_kind_is_documented_and_every_documented_kind_exists(repo_root):
    """A debt item nobody can interpret is noise with a label on it.

    `docs/CLI.md` says when each kind fires; `ea-health` says what the honest response
    is. Both matter, and the second is the one that decays -- a query is easy to add and
    easy to leave unexplained, which is how a register becomes a page people skim.
    """
    from easkills import reports

    source = _read(repo_root, "easkills/reports.py")
    emitted = set(re.findall(r"add\(\s*\"([a-z-]+)\"", source)) | set(
        re.findall(r"\"kind\":\s*\"([a-z-]+)\"", source)
    )
    assert emitted == set(reports.DEBT_KINDS), (
        "reports.py emits kinds that DEBT_KINDS does not list (or the reverse): "
        f"{emitted ^ set(reports.DEBT_KINDS)}"
    )
    health = _read(repo_root, "skills/ea-health/SKILL.md")
    for kind in reports.DEBT_KINDS:
        assert kind in health, f"ea-health does not say what to do about the debt kind `{kind}`"

    # The overlap kinds additionally carry structured JSON fields, and a machine-readable
    # contract belongs in the CLI reference.
    assert set(reports.OVERLAP_KINDS) <= set(reports.DEBT_KINDS)
    cli = _read(repo_root, "docs/CLI.md")
    for kind in reports.OVERLAP_KINDS:
        assert kind in cli, f"docs/CLI.md does not document the JSON shape of `{kind}`"


NUMBER_WORDS = {
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15
}


def test_documented_schema_count_matches_the_registry(repo_root):
    """"All eleven are freshness-tested" went stale the moment a twelfth was added, and
    nothing failed -- the freshness test iterates the registry, so it grew silently while
    the sentence promising the coverage did not. A count in prose that no test checks is
    the defect this repository keeps rediscovering; this is the check for that one."""
    from easkills import genschema

    expected = len(genschema.SCHEMAS)
    pattern = re.compile(r"all (\w+)(?:\s+are freshness-tested|, from one registry)")
    found = 0
    for relative in ("CONTRIBUTING.md", "docs/CLI.md"):
        for word in pattern.findall(_read(repo_root, relative)):
            assert word in NUMBER_WORDS, f"{relative} spells a schema count this test cannot read: {word!r}"
            assert NUMBER_WORDS[word] == expected, (
                f"{relative} claims {word} schemas, genschema.SCHEMAS holds {expected}"
            )
            found += 1
    assert found == 2, "both schema-count sentences must stay findable, or this test stops checking them"


def test_contributing_pre_push_gate_mirrors_ci(repo_root):
    """"CI runs exactly this" has to be true, or a green local gate means nothing."""
    contributing = _read(repo_root, "CONTRIBUTING.md")
    gate_section = contributing.split("## Run the full gate before pushing", 1)[1]
    gate_block = gate_section.split("```bash", 1)[1].split("```", 1)[0]
    documented = _easkills_invocations(gate_block)
    in_ci = _easkills_invocations(_read(repo_root, ".github/workflows/ci.yml"))
    assert in_ci, "no easkills invocations found in the workflow -- has it moved?"
    assert in_ci - documented == set(), (
        "CI runs commands the CONTRIBUTING gate block omits: " + ", ".join(sorted(in_ci - documented))
    )
    assert documented - in_ci == set(), (
        "the CONTRIBUTING gate block lists commands CI does not run: " + ", ".join(sorted(documented - in_ci))
    )


def _documented_flag_rows(repo_root) -> list[tuple[str, str]]:
    """(flag, commands-cell) pairs from the shared-flag table in docs/CLI.md."""
    section = _read(repo_root, "docs/CLI.md").split("## Shared flags", 1)[1].split("\n## ", 1)[0]
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        # Escaped pipes inside a cell (``approved\|staging``) are not column breaks.
        cells = [cell.strip() for cell in line.strip().strip("|").replace(r"\|", "\0").split("|")]
        if len(cells) != 3:
            continue
        flag = re.match(r"`(--[a-z-]+)", cells[0])
        if flag:
            rows.append((flag.group(1), cells[2]))
    return rows


def test_documented_flag_availability_matches_the_parser(repo_root):
    """Every flag the reference lists exists exactly where it says it does.

    Getting this wrong costs a reader an argparse exit 2 while the documentation looks
    authoritative, so the table is compared against the parser rather than trusted.
    """
    parsers = _subparsers()
    rows = _documented_flag_rows(repo_root)
    assert len(rows) >= 7, f"the shared-flag table in docs/CLI.md looks unparsed ({len(rows)} rows)"
    for flag, commands_cell in rows:
        named = {name for name in re.findall(r"`([a-z-]+)`", commands_cell) if name in parsers}
        documented = set(parsers) - named if commands_cell.startswith("all except") else named
        assert documented, f"no commands parsed out of the `{flag}` row"
        actual = {
            name
            for name, subparser in parsers.items()
            if any(flag in action.option_strings for action in subparser._actions)
        }
        assert documented == actual, (
            f"docs/CLI.md says `{flag}` is on {sorted(documented)}; the parser has it on {sorted(actual)}"
        )


def test_every_command_appears_in_the_cli_reference(repo_root):
    reference = _read(repo_root, "docs/CLI.md")
    missing = [name for name in _subparsers() if f"`{name}" not in reference]
    assert not missing, f"undocumented commands in docs/CLI.md: {missing}"


# Commands that maintain *this* repository rather than an architecture one. The
# walkthrough is written for someone running an architecture repository, so these are
# the only ones it may omit -- and naming them here is what stops the list growing
# quietly into "everything we forgot to document".
MAINTAINER_COMMANDS = {
    "gen-schema",  # regenerates the authoring contract from the oracle
    "pin-oracle",  # re-pins vendored rule data after a reviewed upgrade
    "oracle-info",  # prints the oracle's version and checksums
    "score",  # the golden-set harness, which lives in this repository
}


def test_the_walkthrough_covers_every_command_an_operator_runs(repo_root):
    """`docs/CLI.md` lists commands; GETTING-STARTED is where someone *learns* them.

    Added after two additions to the walkthrough silently failed to apply (a patch
    matched on whitespace that had changed) and nothing noticed: the reference was
    complete, the tutorial had quietly stopped covering the tool.
    """
    walkthrough = _read(repo_root, "docs/GETTING-STARTED.md")
    expected = set(_subparsers()) - MAINTAINER_COMMANDS
    missing = sorted(name for name in expected if f"easkills {name} " not in walkthrough)
    assert not missing, f"commands absent from the walkthrough: {missing}"


def test_the_scaffolded_readme_lists_the_commands_a_new_repository_needs(repo_root):
    """`template/README.md` is the first thing a new architecture repository shows."""
    readme = _read(repo_root, "template/README.md")
    expected = set(_subparsers()) - MAINTAINER_COMMANDS - {"check"}  # check runs elsewhere
    missing = sorted(name for name in expected if f"easkills {name}" not in readme)
    assert not missing, f"commands absent from the scaffolded README: {missing}"


@pytest.mark.parametrize("relative", ["SECURITY.md"])
def test_paths_named_in_the_security_policy_exist(repo_root, relative):
    """A scope note that names a path pattern matching nothing is not a scope note."""
    text = _read(repo_root, relative)
    patterns = {
        token.rstrip("/")
        for token in re.findall(r"`([^`\s]+/[^`\s]*)`", text)
        if not token.startswith(("http", "-"))
    }
    assert patterns, f"no repository paths found in {relative}"
    for pattern in patterns:
        assert list(repo_root.glob(pattern)), f"{relative} names `{pattern}`, which matches nothing"


def test_every_literal_the_checks_compare_against_is_in_its_vocabulary():
    """A rule comparing against a value no schema allows is dead code, silently.

    `assessment.verdict == "non-conformant"` only fires if that exact string is in the
    compliance verdict enum; rename the enum value and COMP003 stops existing without a
    single test failing. Same for lifecycle/status literals and the ArchiMate type names
    the reports filter on -- a typo there just yields an empty report.
    """
    from easkills import genschema, oracle

    enum_of = {
        name: getattr(genschema, f"build_{name}_schema")()["properties"]
        for name in ("standard", "decision", "dispensation", "compliance", "service", "request")
    }

    def values(record: str, field: str) -> set[str]:
        return set(enum_of[record][field]["enum"])

    assert {"deprecated", "retired", "active"} <= values("standard", "lifecycle")
    assert "superseded" in values("decision", "status")
    assert "closed" in values("dispensation", "status")
    assert "non-conformant" in values("compliance", "verdict")
    assert {"active", "retired"} <= values("service", "lifecycle")
    assert {"open", "fulfilled", "declined"} <= values("request", "status")

    # Reports filter the model by these exact ArchiMate names.
    assert {"ApplicationComponent", "Capability"} <= set(oracle.element_types())
    assert "Realization" in oracle.relationship_types()

    # The overlap queries filter on these; a typo makes the register silently blind,
    # which reads exactly like a portfolio with no duplication in it.
    from easkills import reports

    assert set(reports.RATIONALIZATION_REALIZER_TYPES) <= set(oracle.element_types())
    assert set(reports.SERVICE_TYPES) <= set(oracle.element_types())
    assert set(reports.PROVIDING_RELATIONSHIPS) <= set(oracle.relationship_types())

    # The TIME vocabulary is shared by the schema, docgen and the KPI.
    from easkills import docgen

    assert tuple(docgen.TIME_ORDER) == tuple(genschema.TIME_DISPOSITIONS)
    model_schema = genschema.build_schema()
    time_enum = model_schema["$defs"]["element"]["properties"]["properties"]["properties"][
        "timeDisposition"
    ]["enum"]
    assert set(time_enum) == set(genschema.TIME_DISPOSITIONS)


def test_change_request_form_ships_where_its_fields_exist(repo_root):
    """The Phase-H form belongs to architecture repositories, so it ships in template/.

    Its fields reference `model/approved/`, `standards/` and `governance-log/decisions/`
    -- directories of a scaffolded architecture repository, not of this tooling one.
    """
    form = repo_root / "template" / ".github" / "ISSUE_TEMPLATE" / "change_request.md"
    assert form.is_file(), "the change-request form must ship with the template"
    text = form.read_text(encoding="utf-8")
    referenced = {token for token in re.findall(r"`([^`\s]+/)`", text)}
    assert referenced, "the form no longer references any repository directory"
    for relative in referenced:
        assert (repo_root / "template" / relative).is_dir(), (
            f"the form asks for ids from {relative}, which the template does not scaffold"
        )
