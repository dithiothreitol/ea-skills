"""Reference alignment: every ALN rule fires, and the two asymmetries hold.

The rules are the easy half. What this module spends most of its length on is the
behaviour that makes the report trustworthy rather than merely present:

* a pack whose pins do not verify produces **no coverage at all** -- not a lower number;
* every ambiguity resolves towards *gap*, because under-reporting a gap is the failure
  mode that matters here;
* an out-of-scope decision inherits down a branch, a coverage claim never does;
* nothing in scope means coverage is ``None``, not a vacuous 100%.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest

from easkills import alignment, cli, reference


@pytest.fixture(scope="module")
def example_report(example_root):
    return alignment.align(example_root)


@pytest.fixture(scope="module")
def broken_report(broken_root):
    return alignment.align(broken_root)


@pytest.fixture(scope="module")
def broken_codes(broken_report):
    return {f.code for f in broken_report.findings}


def _pack(report, name):
    return next(pack for pack in report.packs if pack.name == name)


def _node(pack, node_id):
    return next(node for node in pack.nodes if node.id == node_id)


# --------------------------------------------------------------------------- positive


def test_the_worked_example_is_clean_under_strict(example_report):
    assert example_report.ok, "\n".join(f.render() for f in example_report.errors)
    assert not example_report.warnings, "\n".join(f.render() for f in example_report.warnings)


def test_the_example_pack_is_read_and_scored(example_report):
    pack = _pack(example_report, "wholesale-core")
    assert len(pack.nodes) == 15
    assert pack.counts() == {"covered": 4, "partial": 3, "gap": 0, "out-of-scope": 4}
    # 4 covered + 3 half credits over 7 in-scope leaves.
    assert pack.in_scope == 7
    assert pack.credit == pytest.approx(5.5)
    assert pack.ratio == pytest.approx(5.5 / 7)


def test_out_of_scope_inherits_down_a_branch_and_coverage_does_not(example_report):
    """The asymmetry, on the example that demonstrates it.

    One recorded decision at `wc-corporate` accounts for both its children -- that is
    what makes excluding an area a decision rather than nine copies of a rationale. The
    reverse would be a claim about leaves nobody looked at, so it is not offered.
    """
    pack = _pack(example_report, "wholesale-core")
    for child in ("wc-financial-accounting", "wc-human-resources"):
        node = _node(pack, child)
        assert node.status == alignment.STATUS_OUT_OF_SCOPE
        assert node.inherited_from == "wc-corporate"
        assert node.rationale, "an inherited exclusion still shows the rationale it inherited"
    covering = _node(pack, "wc-order-capture")
    assert covering.status == alignment.STATUS_COVERED and not covering.inherited_from


def test_a_branch_is_not_a_gap(example_report):
    """A taxonomy heading is not something an application realizes.

    Calling an unmapped branch a gap would invent findings for the shape of the
    taxonomy rather than the state of the architecture -- and would have made the
    worked example impossible to keep clean for the wrong reason.
    """
    pack = _pack(example_report, "wholesale-core")
    assert _node(pack, "wc-order-to-cash").status == alignment.STATUS_BRANCH
    assert not any(node.status == alignment.STATUS_GAP for node in pack.nodes)


def test_branch_rollups_report_their_subtree(example_report):
    pack = _pack(example_report, "wholesale-core")
    rollups = {branch.id: branch for branch in pack.branches}
    assert set(rollups) == {"wc-customer", "wc-order-to-cash", "wc-logistics", "wc-corporate"}
    assert rollups["wc-order-to-cash"].ratio == pytest.approx(3 / 4)  # 2 covered + 2 partial
    assert rollups["wc-customer"].out_of_scope == 1
    # A wholly excluded branch has nothing to be a percentage of, and says so.
    assert rollups["wc-corporate"].in_scope == 0
    assert rollups["wc-corporate"].ratio is None


def test_partial_mappings_carry_the_note_that_makes_them_readable(example_report):
    pack = _pack(example_report, "wholesale-core")
    for node_id in ("wc-invoicing", "wc-pricing", "wc-inventory"):
        node = _node(pack, node_id)
        assert node.status == alignment.STATUS_PARTIAL
        assert len(node.note) > 40, f"{node_id}: a partial without a note is a shrug in YAML"


def test_prose_fields_are_whitespace_collapsed(example_report):
    """Folded YAML scalars are layout of the source file, not content.

    Left in, the authors' line breaks and trailing newlines put blank lines through the
    middle of every rendered report and into the JSON.
    """
    pack = _pack(example_report, "wholesale-core")
    for node in pack.nodes:
        assert "\n" not in node.note and "\n" not in node.rationale
        assert node.note == node.note.strip()


def test_the_report_is_byte_stable(example_root):
    first = alignment.align(example_root)
    second = alignment.align(example_root)
    assert first.render() == second.render()
    assert first.as_dict() == second.as_dict()


def test_the_example_pack_verifies_its_pins(example_root):
    directory = reference.reference_dir(example_root) / "wholesale-core"
    assert reference.failed_checksums(directory) == []
    pack = reference.load_pack(example_root, "wholesale-core")
    assert pack.refused == ""


def test_the_shipped_open_library_verifies_its_pins(repo_root):
    """`references/` is shipped content: a pack whose pins are stale would be refused
    by the first adopter who copied it, which is a worse way to find out."""
    library = repo_root / "references"
    packs = sorted(p for p in library.iterdir() if p.is_dir())
    assert packs, "the open reference library is empty"
    for directory in packs:
        assert (directory / "NOTICE.md").is_file(), f"{directory.name} ships no NOTICE"
        assert reference.failed_checksums(directory) == [], f"{directory.name}: run pin-reference"


def test_the_shipped_library_is_openly_licensed(repo_root):
    """D2: only public-domain or public-law content ships here.

    The check is deliberately crude -- it cannot read a licence -- but it does catch the
    realistic failure, which is a pack landing with a NOTICE that says nothing about
    whether redistribution was permitted.
    """
    for directory in sorted(p for p in (repo_root / "references").iterdir() if p.is_dir()):
        notice = (directory / "NOTICE.md").read_text(encoding="utf-8").lower()
        assert "public domain" in notice or "public law" in notice, (
            f"{directory.name}: the NOTICE must state the open status that lets it ship here"
        )


UNVERIFIED_MARKER = "structure not yet verified"


def test_the_verification_state_of_every_shipped_pack_is_stated_in_both_places(repo_root):
    """A shipped taxonomy has no mechanical provenance check, so it gets a written one.

    Nothing here can read NIST CSWP 29 and confirm a Category name, which means a pack
    written from working knowledge and a pack read off the source look identical to
    `align` and to every adopter. The state is therefore declared per pack — in its NOTICE
    and in the library table — and this test keeps the two from drifting, because an
    unverified pack quietly losing its caveat is how a draft yardstick becomes an
    authority.
    """
    table = (repo_root / "references" / "README.md").read_text(encoding="utf-8")
    for directory in sorted(p for p in (repo_root / "references").iterdir() if p.is_dir()):
        notice = (directory / "NOTICE.md").read_text(encoding="utf-8").lower()
        row = next(
            (line for line in table.splitlines() if f"`{directory.name}/`" in line),
            None,
        )
        assert row, f"{directory.name} is not listed in references/README.md"
        if UNVERIFIED_MARKER in notice:
            assert UNVERIFIED_MARKER in row.lower(), (
                f"{directory.name}: the NOTICE says the structure is unverified and the "
                "library table does not -- the caveat must reach the page adopters read first"
            )
        else:
            assert UNVERIFIED_MARKER not in row.lower(), (
                f"{directory.name}: the table calls the structure unverified but the NOTICE "
                "no longer does -- one of them was updated and the other was not"
            )


ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def test_a_pack_that_claims_verification_says_when(repo_root):
    """A verification is against one edition of one document on one day.

    Undated, "verified" is unfalsifiable: nobody downstream can tell a reading done
    against the cited edition from one done against an edition since superseded, and the
    caveat this pack shed cannot be re-earned by a reader who suspects it should be. So a
    pack that no longer carries the unverified marker must carry a date instead -- in the
    NOTICE that argues it and in the table adopters read first.
    """
    table = (repo_root / "references" / "README.md").read_text(encoding="utf-8")
    for directory in sorted(p for p in (repo_root / "references").iterdir() if p.is_dir()):
        notice = (directory / "NOTICE.md").read_text(encoding="utf-8")
        if UNVERIFIED_MARKER in notice.lower():
            continue
        row = next(line for line in table.splitlines() if f"`{directory.name}/`" in line)
        assert ISO_DATE.search(notice), (
            f"{directory.name}: the NOTICE claims a verified structure without saying when "
            "it was read -- an undated verification cannot be found stale"
        )
        assert ISO_DATE.search(row), (
            f"{directory.name}: the library table calls the pack verified without a date, so "
            "an adopter cannot see which edition the reading was against"
        )


def test_a_repository_with_no_reference_pack_passes(tmp_path):
    report = alignment.align(tmp_path)
    assert report.ok and not report.findings
    assert report.packs == []
    assert report.ratio is None, "no pack means coverage is undefined, never 100%"


# --------------------------------------------------------------------------- negative

EXPECTED_ERROR_CODES = [
    "ALN000",  # unparsable taxonomy, structural defects, a coverage claim with no elements
    "ALN001",  # pins do not verify -- the pack is refused
    "ALN002",  # mapping targets a node the reference does not hold
    "ALN003",  # mapping names an element the zone does not hold
    "ALN005",  # out-of-scope with no rationale
    "ALN006",  # two entries for one node
    "ALN008",  # a pack with no nodes
]

EXPECTED_WARNING_CODES = [
    "ALN004",  # the gap: unmapped and not declared out-of-scope
    "ALN007",  # coverage claimed by a staging-only element while reading approved
]


@pytest.mark.parametrize("code", EXPECTED_ERROR_CODES)
def test_error_rule_fires(broken_report, code):
    matches = [f for f in broken_report.errors if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


@pytest.mark.parametrize("code", EXPECTED_WARNING_CODES)
def test_warning_rule_fires(broken_report, code):
    matches = [f for f in broken_report.warnings if f.code == code]
    assert matches, f"{code} did not fire on the negative fixture"


def test_broken_reference_fixture_fails_overall(broken_report):
    assert not broken_report.ok


def test_a_tampered_pack_is_refused_rather_than_scored(broken_report):
    """The oracle discipline, applied to the second class of pinned data.

    The failure to avoid is a *plausible* report: a taxonomy somebody edited would
    produce coverage numbers that look exactly like real ones. So the pack contributes
    no node, no gap and no percentage -- only the refusal.
    """
    pack = _pack(broken_report, "tampered")
    assert pack.refused
    assert pack.nodes == [] and pack.in_scope == 0 and pack.ratio is None
    codes = {f.code for f in broken_report.findings if f.concept == "tampered"}
    assert codes == {"ALN001"}


def test_an_unreadable_taxonomy_does_not_also_report_as_empty(broken_report):
    """ALN008 says "declares no nodes", which is a false diagnosis of a file that
    never parsed -- so it stays silent and ALN000 carries it alone."""
    findings = [f for f in broken_report.findings if "unreadable" in f.file or f.concept == "unreadable"]
    assert {f.code for f in findings} == {"ALN000"}


def test_a_silent_exclusion_excludes_nothing(broken_report):
    """ALN005 fails closed: without a rationale the node is a gap, not out of scope."""
    pack = _pack(broken_report, "mixed")
    assert _node(pack, "x-silent-exclusion").status == alignment.STATUS_GAP


def test_a_staging_only_claim_leaves_the_node_a_gap(broken_report):
    pack = _pack(broken_report, "mixed")
    assert _node(pack, "x-staging-only").status == alignment.STATUS_GAP


def test_a_diagnosed_gap_is_not_reported_twice(broken_report):
    """The node table keeps every gap; the finding list keeps the specific diagnosis.

    Three nodes of the `mixed` pack are gaps *for a stated reason* (ALN003, ALN005,
    ALN007). Adding ALN004 on top would say the same thing in a vaguer way, and a
    finding list that repeats itself trains people to skim it.
    """
    gaps = {f.concept for f in broken_report.warnings if f.code == "ALN004"}
    assert "x-unmapped" in gaps
    assert gaps.isdisjoint({"x-unknown-element", "x-silent-exclusion", "x-staging-only"})


def test_the_first_of_two_mappings_wins(broken_report):
    """ALN006 reports the second entry; the first is what the report uses. Picking the
    *last* would mean a report changing meaning when someone appends a line."""
    pack = _pack(broken_report, "mixed")
    assert _node(pack, "x-twice").status == alignment.STATUS_PARTIAL


# ----------------------------------------------------------- pins, zones, thresholds


def _pack_dir(tmp_path, name="p", nodes: str = "", mappings: str | None = None):
    directory = tmp_path / "reference" / name
    directory.mkdir(parents=True)
    (directory / "model.yaml").write_text(
        f"name: A pack\nnodes:\n{nodes}", encoding="utf-8", newline="\n"
    )
    (directory / "NOTICE.md").write_text("# NOTICE\n\nAuthored in a test.\n", encoding="utf-8", newline="\n")
    if mappings is not None:
        (directory / "mappings.yaml").write_text(mappings, encoding="utf-8", newline="\n")
    reference.write_pins(directory)
    return directory


ONE_NODE = "  - id: n1\n    name: A capability\n    kind: capability\n"


def test_a_pack_with_no_pin_file_is_refused(tmp_path):
    """Unverifiable is not a softer state than mismatched -- the oracle raises here too."""
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "SHA256SUMS").unlink()
    report = alignment.align(tmp_path)
    assert [f.code for f in report.errors] == ["ALN001"]
    assert report.packs[0].nodes == []


def test_a_pin_file_that_omits_the_notice_is_refused(tmp_path):
    """A pack whose provenance can be swapped silently is a licence problem."""
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    lines = [
        line
        for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if "NOTICE" not in line
    ]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    assert "ALN001" in {f.code for f in alignment.align(tmp_path).errors}


def test_a_pin_escaping_the_pack_is_refused_not_read(tmp_path):
    """Same rule as PROV008: verification must not reach outside what a reviewer sees."""
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "SHA256SUMS").write_text(
        f"{'0' * 64}  ../../elsewhere.txt\n", encoding="utf-8", newline="\n"
    )
    report = alignment.align(tmp_path)
    assert "ALN001" in {f.code for f in report.errors}


def test_a_gitignored_taxonomy_is_refused_loudly_not_skipped(tmp_path):
    """`template/reference/README.md` tells adopters they may gitignore a licensed
    `model.yaml` and keep the mappings, notice and pins committed. On such a checkout the
    pack must fail loudly: a report that quietly omitted a reference nobody could load
    would read as a reference with no gaps.
    """
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "model.yaml").unlink()
    report = alignment.align(tmp_path)
    assert [f.code for f in report.errors] == ["ALN001"]
    assert "missing file" in report.errors[0].message


def test_editing_a_pinned_taxonomy_refuses_until_re_pinned(tmp_path):
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "model.yaml").write_text(
        f"name: A pack\nnodes:\n{ONE_NODE}  - id: n2\n    name: Added later\n    kind: capability\n",
        encoding="utf-8",
        newline="\n",
    )
    assert "ALN001" in {f.code for f in alignment.align(tmp_path).errors}
    reference.write_pins(directory)  # the deliberate, reviewed act
    codes = {f.code for f in alignment.align(tmp_path).findings}
    assert codes == {"ALN004"}, "re-pinned, so the nodes are read -- and unmapped, so they are gaps"


def test_unanchored_local_elements_are_information_not_findings(tmp_path):
    """A business does things its blueprint never heard of.

    Reported so an architect can notice the reference is the wrong one; never as a
    finding, because a tool that called it a defect would teach people to model the
    blueprint instead of the business.
    """
    _pack_dir(
        tmp_path,
        nodes=ONE_NODE,
        mappings="mappings:\n  - ref: n1\n    status: covered\n    elements: [cap-mapped]\n",
    )
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "strategy.yaml").write_text(
        "elements:\n"
        "  - id: cap-mapped\n    type: Capability\n    name: Mapped Capability\n"
        "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n"
        "    assumed: true\n    rationale: A fixture element, not evidence.\n"
        "  - id: cap-local\n    type: Capability\n    name: Local Speciality\n"
        "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n"
        "    assumed: true\n    rationale: A fixture element, not evidence.\n"
        "  - id: node-server\n    type: Node\n    name: A Server\n"
        "    owner: ea@example.test\n    lastReviewed: 2026-08-01\n"
        "    assumed: true\n    rationale: A fixture element, not evidence.\n",
        encoding="utf-8",
        newline="\n",
    )
    report = alignment.align(tmp_path)
    assert report.ok and not report.findings
    unanchored = {item[0] for item in report.packs[0].unanchored}
    # The Node is not anchorable by a capability taxonomy, so it is not reported at all:
    # a list that included every element of every layer would be noise, not information.
    assert unanchored == {"cap-local"}


def test_staging_zone_shows_what_promotion_would_close(broken_root, tmp_path):
    """`--zone staging` is the honest way to ask about a proposal, and the only one:
    in `approved` the same mapping is ALN007 and the node stays a gap."""
    repo = tmp_path / "repo"
    shutil.copytree(broken_root, repo)
    approved = alignment.align(repo, zone="approved")
    staging = alignment.align(repo, zone="staging")
    assert _node(_pack(approved, "mixed"), "x-staging-only").status == alignment.STATUS_GAP
    assert _node(_pack(staging, "mixed"), "x-staging-only").status == alignment.STATUS_COVERED
    assert "ALN007" not in {f.code for f in staging.findings}


def test_an_unknown_reference_name_is_refused(example_root):
    """A typo in --reference must not read as "that reference has no gaps"."""
    with pytest.raises(alignment.AlignmentError):
        alignment.align(example_root, references=["wholesale-cor"])


def test_selecting_one_pack_reports_only_that_pack(broken_root):
    report = alignment.align(broken_root, references=["mixed"])
    assert [pack.name for pack in report.packs] == ["mixed"]


# ------------------------------------------------------------------------------- CLI


def test_cli_align_exit_codes(example_root, broken_root, capsys):
    assert cli.main(["align", "--root", str(example_root)]) == 0
    assert cli.main(["align", "--root", str(example_root), "--strict"]) == 0
    assert cli.main(["align", "--root", str(broken_root)]) == 1
    capsys.readouterr()


def test_cli_align_strict_fails_on_a_gap(tmp_path, capsys):
    _pack_dir(tmp_path, nodes=ONE_NODE)
    assert cli.main(["align", "--root", str(tmp_path)]) == 0
    assert cli.main(["align", "--root", str(tmp_path), "--strict"]) == 1
    capsys.readouterr()


def test_cli_align_min_coverage_gate(example_root, capsys):
    assert cli.main(["align", "--root", str(example_root), "--min-coverage", "78"]) == 0
    assert cli.main(["align", "--root", str(example_root), "--min-coverage", "80"]) == 1
    assert "below the required" in capsys.readouterr().out


def test_cli_align_min_coverage_refuses_to_pass_vacuously(tmp_path, capsys):
    """With nothing in scope there is no coverage to compare.

    Passing here would let a repository with no reference pack -- or one whose every node
    is excluded -- satisfy a completeness gate by having measured nothing. That is the
    shape of the "100% of an empty set" defect this repository has already paid for once.
    """
    assert cli.main(["align", "--root", str(tmp_path), "--min-coverage", "100"]) == 1
    assert "cannot be measured" in capsys.readouterr().out
    assert cli.main(["align", "--root", str(tmp_path)]) == 0
    capsys.readouterr()


def test_cli_align_writes_json(example_root, tmp_path, capsys):
    out = tmp_path / "align.json"
    assert cli.main(["align", "--root", str(example_root), "--json", str(out)]) == 0
    capsys.readouterr()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["zone"] == "approved"
    pack = payload["packs"][0]
    assert pack["name"] == "wholesale-core"
    assert pack["coverage"] == pytest.approx(round(5.5 / 7, 4))
    assert {"id", "status", "elements", "inheritedFrom"} <= set(pack["nodes"][0])


def test_cli_align_unknown_reference_exits_one(example_root, capsys):
    assert cli.main(["align", "--root", str(example_root), "--reference", "nope"]) == 1
    assert "no reference pack named" in capsys.readouterr().out


def test_cli_pin_reference_round_trips(tmp_path, capsys):
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "SHA256SUMS").unlink()
    assert cli.main(["pin-reference", "--root", str(tmp_path), "--reference", "p"]) == 0
    assert "never to silence" in capsys.readouterr().out
    assert reference.failed_checksums(directory) == []


def test_cli_pin_reference_needs_exactly_one_target(tmp_path, capsys):
    assert cli.main(["pin-reference", "--root", str(tmp_path)]) == 1
    assert "exactly one" in capsys.readouterr().out


def test_cli_pin_reference_refuses_a_pack_without_a_notice(tmp_path, capsys):
    directory = _pack_dir(tmp_path, nodes=ONE_NODE)
    (directory / "NOTICE.md").unlink()
    assert cli.main(["pin-reference", "--root", str(tmp_path), "--reference", "p"]) == 1
    assert "NOTICE.md" in capsys.readouterr().out


# ------------------------------------------------------------------------ vocabulary


def test_every_node_kind_can_anchor_something_local():
    """A kind with no local types would drop silently out of the unanchored report.

    Same failure as `timeDisposition: tolerate`: the value validates, the code that
    reads it does not recognise it, and the report quietly omits what it covers.
    """
    from easkills import genschema, oracle

    assert set(alignment.KIND_LOCAL_TYPES) == set(genschema.REFERENCE_NODE_KINDS)
    for kind, types in alignment.KIND_LOCAL_TYPES.items():
        assert types, kind
        for element_type in types:
            assert element_type in oracle.element_types(), f"{kind}: {element_type}"


def test_the_mapping_statuses_the_code_compares_against_are_in_the_schema():
    from easkills import genschema

    statuses = set(genschema.REFERENCE_MAPPING_STATUSES)
    assert {alignment.STATUS_COVERED, alignment.STATUS_PARTIAL, alignment.STATUS_OUT_OF_SCOPE} <= statuses
    # `gap` and `branch` are computed verdicts, never authored -- so they must NOT be
    # values a mapping may claim, or an author could declare a node covered by writing
    # "gap" somewhere else.
    assert alignment.STATUS_GAP not in statuses
    assert alignment.STATUS_BRANCH not in statuses
