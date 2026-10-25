"""Phase 8.3: security architecture in the existing homes.

Every rule here reads a vocabulary a repository opts into, so the first property tested is
silence: the worked example uses none of it and must stay clean. Then each rule is proved
on its case *and* on the negative half beside it, the reach table is held to the oracle the
way `impact.PROPAGATION` is, and the generators are proved to produce output the gate
accepts.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from easkills import alignment, check, dsl, genschema, govern, oracle, propose, security, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SECCO = REPO_ROOT / "eval" / "fixtures" / "secco"
AS_OF = date(2026, 10, 25)


# ------------------------------------------------------------------------ vocabulary


def test_the_reach_table_covers_exactly_the_oracles_relationship_types():
    """A relationship type with no declared reach would drop out of the exposure report
    silently -- the timeDisposition failure in a new place."""
    assert set(security.REACH) == set(oracle.relationship_types())
    for name, (direction, reason) in security.REACH.items():
        assert direction in {security.FORWARD, security.BACKWARD, security.BOTH, security.NONE}, name
        assert reason, f"{name} has no stated reason"


def test_reach_runs_opposite_to_change_impact_for_serving():
    """The reason REACH exists instead of reusing impact.PROPAGATION."""
    from easkills import impact

    assert security.REACH["Serving"][0] == security.BACKWARD
    assert impact.PROPAGATION["Serving"][0] == impact.FORWARD
    assert security.REACH["Association"][0] == security.NONE


def test_the_vocabulary_is_closed_in_the_schema():
    properties = genschema.build_schema()["$defs"]["element"]["properties"]["properties"]["properties"]
    assert properties["dataClassification"]["enum"] == list(genschema.DATA_CLASSIFICATIONS)
    assert properties["personalData"]["enum"] == list(genschema.PERSONAL_DATA)
    assert properties["exposure"]["enum"] == list(genschema.EXPOSURES)
    for key in genschema.SECURITY_RATING_KEYS:
        assert properties[key]["enum"] == list(genschema.SECURITY_LEVELS)
    assert "gdpr" in genschema.regulatory_scope_values()
    assert "ai-act dora gdpr" in genschema.regulatory_scope_values()


# ----------------------------------------------------------------------------- rules


def test_the_worked_example_uses_none_of_it_and_is_silent(example_root):
    report = validate.validate(example_root)
    assert not [f for f in report.findings if f.code.startswith("SEC")]


def test_the_security_fixture_is_clean_under_strict():
    report = validate.validate(SECCO)
    assert report.ok and not report.warnings, [f.render() for f in report.findings if f.severity != "info"]
    aligned = alignment.align(SECCO)
    assert aligned.ok and not aligned.warnings, [f.render() for f in aligned.findings]


@pytest.fixture(scope="module")
def broken_security(broken_root):
    return validate.validate(broken_root)


def test_each_sec_rule_names_exactly_its_case(broken_security):
    by_code = {}
    for finding in broken_security.findings:
        if finding.code.startswith("SEC"):
            by_code.setdefault(finding.code, set()).add(finding.concept)
    assert by_code == {
        "SEC001": {"app-public-unprotected"},
        "SEC002": {"rel-portal-reads-restricted"},
        "SEC003": {"data-restricted-records"},
    }, "the negative halves (governed ledger, profile in GDPR scope) must stay silent"


def test_sec001_sees_data_through_access_not_only_on_the_element(broken_security):
    """The portal carries no classification itself; it holds what it reads."""
    finding = next(f for f in broken_security.findings if f.code == "SEC001")
    assert "data-restricted-records" in finding.message and "restricted" in finding.message


def test_alnoo9_fires_for_the_unanchored_rating_and_not_through_a_mapped_requirement(broken_root):
    report = alignment.align(broken_root, references=["controls"])
    flagged = {f.concept for f in report.findings if f.code == "ALN009"}
    assert flagged == {"data-restricted-records"}, "the ledger is anchored through req-ledger-integrity"


def test_alnoo9_is_silent_for_a_pack_with_no_controls(example_root):
    report = alignment.align(example_root)
    assert not [f for f in report.findings if f.code == "ALN009"]


def test_an_assessment_does_not_govern():
    """`propose --from threats` writes Assessments bound to both ends. If that silenced
    SEC002, generating a skeleton would close the finding it was generated for."""
    model = dsl.Model(root=REPO_ROOT, zone="approved", config={})
    model.elements["a"] = dsl.Element(id="a", type="ApplicationComponent", name="A")
    model.elements["asm"] = dsl.Element(id="asm", type="Assessment", name="Asm", applies_to=["a"])
    model.elements["req"] = dsl.Element(id="req", type="Requirement", name="Req", applies_to=["b"])
    assert security.governed_ids(model) == {"b"}


# -------------------------------------------------------------------------- exposure


def test_exposure_walks_from_the_public_portal_to_the_restricted_record():
    report = security.exposure(SECCO)
    [surface] = report.surfaces
    reached = {item.id: item for item in surface.reached}
    assert reached["app-account-service"].via == "rel-accounts-serve-portal", "consumer reaches provider"
    assert reached["data-customer-account"].hops == 2
    assert surface.sensitive == ["data-customer-account"]
    assert surface.boundaries == ["rel-accounts-serve-portal"]
    assert surface.ungoverned == []


def test_exposure_respects_depth_and_is_byte_stable():
    shallow = security.exposure(SECCO, depth=1)
    assert {item.id for item in shallow.surfaces[0].reached} == {"app-customer-portal", "app-account-service"}
    assert security.exposure(SECCO).as_dict() == security.exposure(SECCO).as_dict()


def test_exposure_with_nothing_public_says_which_question_it_cannot_answer(example_root):
    report = security.exposure(example_root)
    assert report.surfaces == []
    assert "has not recorded it yet" in security.render_exposure(report)


# --------------------------------------------------------------------------- threats


def test_propose_from_threats_writes_assessments_the_gate_accepts(tmp_path):
    import shutil

    shutil.copytree(SECCO, tmp_path / "repo")
    root = tmp_path / "repo"
    report = propose.propose(root, source="threats", as_of=AS_OF)
    [proposal] = report.proposals
    assert proposal.type == "Assessment"
    assert proposal.id == "asm-threats-rel-accounts-serve-portal"
    assert proposal.applies_to == ["app-account-service", "app-customer-portal"]
    assert proposal.documentation.startswith(propose.PLACEHOLDER)
    assert all(category in proposal.documentation for category in propose.STRIDE)
    staged = validate.validate(root, zone="staging")
    assert staged.ok, [f.render() for f in staged.errors]


# ----------------------------------------------------------------- check: new inputs


def _standard(rule: dict) -> govern.Standard:
    return govern.Standard(id="std-x", name="X", lifecycle="active", detect=[rule])


def test_check_reads_pyproject_dependencies_and_poetry_tables(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["Psycopg2_Binary>=2.9; python_version > \'3.8\'"]\n'
        "[project.optional-dependencies]\nextra = [\"requests\"]\n"
        '[tool.poetry.dependencies]\npython = "^3.11"\nlxml = {version = "^5.0"}\n',
        encoding="utf-8",
    )
    found, findings, manifests = check.read_dependencies(tmp_path)
    assert manifests == 1 and not findings
    names = {d.name for d in found}
    assert names == {"Psycopg2_Binary", "requests", "lxml"}
    dependency = next(d for d in found if d.name == "Psycopg2_Binary")
    assert check._detects(_standard({"manifest": "pyproject.toml", "dependency": "psycopg2-binary"}), dependency)


def test_check_reads_cyclonedx_and_spdx_and_matches_by_purl(tmp_path):
    cyclonedx = tmp_path / "bom.cdx.json"
    cyclonedx.write_text(json.dumps({
        "bomFormat": "CycloneDX", "specVersion": "1.5",
        "components": [{"name": "pg", "version": "8.11.3", "purl": "pkg:npm/pg@8.11.3",
                        "components": [{"name": "core", "purl": "pkg:npm/%40angular/core@16.0.0"}]}],
    }), encoding="utf-8")
    spdx = tmp_path / "sbom.spdx.json"
    spdx.write_text(json.dumps({
        "spdxVersion": "SPDX-2.3",
        "packages": [{"name": "postgresql", "versionInfo": "42.7.1", "externalRefs": [
            {"referenceType": "purl", "referenceLocator": "pkg:maven/org.postgresql/postgresql@42.7.1"}]}],
    }), encoding="utf-8")
    found, findings, manifests = check.read_dependencies(tmp_path, [cyclonedx, spdx])
    assert manifests == 2 and not findings
    by_name = {d.name: d for d in found}
    assert set(by_name) == {"pkg:npm/pg@8.11.3", "pkg:npm/%40angular/core@16.0.0",
                            "pkg:maven/org.postgresql/postgresql@42.7.1"}
    rule = {"manifest": "sbom", "dependency": "pkg:npm/pg"}
    assert check._detects(_standard(rule), by_name["pkg:npm/pg@8.11.3"]), "the version is reported, not matched"
    assert not check._detects(_standard(rule), by_name["pkg:npm/%40angular/core@16.0.0"])
    maven = {"manifest": "sbom", "dependency": "pkg:maven/org.postgresql/postgresql"}
    assert check._detects(_standard(maven), by_name["pkg:maven/org.postgresql/postgresql@42.7.1"])


def test_an_unreadable_or_unknown_sbom_is_a_refusal_not_a_skip(tmp_path):
    other = tmp_path / "other.json"
    other.write_text('{"something": "else"}', encoding="utf-8")
    _found, findings, _manifests = check.read_dependencies(tmp_path, [other, tmp_path / "missing.json"])
    assert [f.code for f in findings] == ["CHK000", "CHK000"]


def test_the_check_and_schema_manifest_vocabularies_agree():
    assert tuple(check.MANIFEST_KINDS) == tuple(genschema.MANIFEST_KINDS)
    assert "sbom" not in check.MANIFEST_FILES, "an SBOM is passed, never guessed by file name"
