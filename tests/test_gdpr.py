"""Phase 8.4: the GDPR record, the DORA ITS worksheets, Polish output, and the FRIA skeleton.

The registers follow one pattern (D7), so the tests do too: every rule fires on its case in
the broken fixture, the clean fixture passes under --strict, nothing in scope produces no
document, the notice sits above the tables, and the gap section names what the model does
not carry. The language tests hold the catalogue to three properties -- complete, same
placeholders, English unchanged -- because a translation that silently fell back to English
for one key would look finished.
"""

from __future__ import annotations

import csv
import io
import shutil
from datetime import date
from pathlib import Path

import pytest

from easkills import cli, correspond, docgen, dora, dora_its, dsl, gdpr, i18n, propose, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
FINCO = REPO_ROOT / "eval" / "fixtures" / "finco"
FINCO_BROKEN = REPO_ROOT / "eval" / "fixtures" / "finco-broken"
AICO = REPO_ROOT / "eval" / "fixtures" / "aico"
AS_OF = date(2026, 7, 30)


# ------------------------------------------------------------------------- GDPR record


def test_the_clean_fixture_records_its_processing_without_a_finding():
    register = gdpr.build(FINCO, today=AS_OF)
    assert [e.id for e in register.entries] == ["app-crm", "app-kyc-screening"]
    assert register.ok and not register.warnings and not register.gaps
    assert register.entries[1].obligations == ["req-customer-data-need-to-know"], "derived, never written"


@pytest.mark.parametrize(
    ("code", "concept", "severity"),
    [
        ("GDR001", "gdpr-no-purpose", "warning"),
        ("GDR002", "gdpr-special-no-basis", "error"),
        ("GDR003", "gdpr-no-purpose", "warning"),
        ("GDR004", "gdpr-ungoverned", "warning"),
        ("GDR005", "gdpr-waived", "info"),
    ],
)
def test_every_gdr_rule_fires_on_its_case(code, concept, severity):
    findings = [f for f in gdpr.build(FINCO_BROKEN, today=AS_OF).findings if f.code == code]
    assert [(f.concept, f.severity) for f in findings] == [(concept, severity)]


def test_the_art_9_condition_is_named_as_a_gap_on_every_special_category_row():
    """The model never carries it, so a record that left the column blank would read as
    'none needed' -- the gap section says it is the controller's to record instead."""
    gaps = {g["field"]: g["elements"] for g in gdpr.build(FINCO_BROKEN, today=AS_OF).gaps}
    assert gaps["art-9-condition"] == ["gdpr-special-no-basis"]


def test_nothing_in_scope_is_no_document(example_root):
    register = gdpr.build(example_root, today=AS_OF)
    assert not register.in_scope
    with pytest.raises(gdpr.GdprError):
        gdpr.markdown(register)


def test_the_notice_comes_before_the_tables_in_both_languages():
    register = gdpr.build(FINCO, today=AS_OF)
    for lang in i18n.LANGUAGES:
        text = gdpr.markdown(register, lang)
        notice = i18n.CATALOG["gdpr.notice"][lang]
        assert text.index(notice) < text.index("| ")
    assert "Rejestr czynności przetwarzania" in gdpr.markdown(register, "pl")
    assert "umowa (art. 6 ust. 1 lit. b)" in gdpr.markdown(register, "pl")


def test_gdpr_register_cli_gates_like_the_other_registers(tmp_path, capsys):
    assert cli.main(["gdpr-register", "--root", str(FINCO), "--as-of", "2026-07-30", "--strict"]) == 0
    assert cli.main(["gdpr-register", "--root", str(FINCO_BROKEN), "--as-of", "2026-07-30"]) == 1
    out = tmp_path / "ropa.md"
    assert cli.main(["gdpr-register", "--root", str(FINCO), "--as-of", "2026-07-30", "--out", str(out), "--lang", "pl"]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Rejestr czynności przetwarzania")


def test_dual_scope_elements_appear_in_both_registers():
    dora_ids = {e.id for e in dora.build(FINCO, today=AS_OF).entries}
    gdpr_ids = {e.id for e in gdpr.build(FINCO, today=AS_OF).entries}
    assert {"app-crm", "app-kyc-screening"} <= dora_ids & gdpr_ids


# --------------------------------------------------------------------- DORA ITS export


def test_its_export_writes_one_csv_per_template_and_names_every_empty_column(tmp_path):
    register = dora.build(FINCO, today=AS_OF)
    written = dora_its.export(register, tmp_path, {})
    assert sorted(p.name for p in written) == ["B_02.01.csv", "B_02.02.csv", "B_05.01.csv", "B_06.01.csv", "README.md"]
    providers = list(csv.reader(io.StringIO((tmp_path / "B_05.01.csv").read_text(encoding="utf-8"))))
    assert providers[0][0].startswith("B_05.01.0010 ")
    names = {row[4] for row in providers[1:]}
    assert "PaySwitch AG" in names and len(providers) - 1 == len(register.providers)
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert dora.HEADER_NOTICE in readme and "springlex.eu" in readme
    assert "B_05.01.0010 Identification code of ICT third-party service provider" in readme, "an unfilled column is named"
    assert "B_07.01" in readme, "templates nothing feeds are listed as not exported"


def test_a_provider_lei_fills_the_code_columns_and_a_conflict_does_not(tmp_path):
    register = dora.build(FINCO, today=AS_OF)
    lei = "529900T8BM49AURSDO55"
    dora_its.export(register, tmp_path / "one", {"app-card-processing": lei, "service-payment-initiation": lei})
    rows = list(csv.DictReader(io.StringIO((tmp_path / "one" / "B_05.01.csv").read_text(encoding="utf-8"))))
    payswitch = next(r for r in rows if r[next(k for k in r if k.startswith("B_05.01.0050"))] == "PaySwitch AG")
    assert payswitch[next(k for k in payswitch if k.startswith("B_05.01.0010"))] == lei
    dora_its.export(register, tmp_path / "two", {"app-card-processing": lei, "service-payment-initiation": "529900ABCDEFGHIJKL01"})
    rows = list(csv.DictReader(io.StringIO((tmp_path / "two" / "B_05.01.csv").read_text(encoding="utf-8"))))
    payswitch = next(r for r in rows if r[next(k for k in r if k.startswith("B_05.01.0050"))] == "PaySwitch AG")
    assert payswitch[next(k for k in payswitch if k.startswith("B_05.01.0010"))] == "", "two LEIs for one name is a conflict"


def test_its_csv_needs_a_directory_and_is_byte_stable(tmp_path):
    assert cli.main(["dora-register", "--root", str(FINCO), "--as-of", "2026-07-30", "--format", "its-csv"]) == 1
    for name in ("a", "b"):
        assert cli.main([
            "dora-register", "--root", str(FINCO), "--as-of", "2026-07-30", "--format", "its-csv", "--out", str(tmp_path / name)
        ]) == 0
    for file in (tmp_path / "a").iterdir():
        assert file.read_bytes() == (tmp_path / "b" / file.name).read_bytes()


# ------------------------------------------------------------------------- language


def test_every_catalogue_key_exists_in_every_language_with_the_same_placeholders():
    for key, texts in i18n.CATALOG.items():
        assert set(texts) == set(i18n.LANGUAGES), key
        if key in i18n.ENGLISH_FROM_SOURCE:
            assert texts["en"] == "" and texts["pl"], key
            continue
        assert all(texts[lang] for lang in i18n.LANGUAGES), f"{key} is empty in some language"
        placeholders = {lang: i18n.placeholders(texts[lang]) for lang in i18n.LANGUAGES}
        assert len({frozenset(p) for p in placeholders.values()}) == 1, f"{key}: {placeholders}"


def test_the_correspondence_rules_have_a_translation_each_and_english_matches_the_source():
    kinds = {rule.kind for rule in correspond.RULES}
    assert {key.split(".")[1] for key in i18n.ENGLISH_FROM_SOURCE} == kinds
    for rule in correspond.RULES:
        assert i18n.CATALOG[f"corr.{rule.kind}.relates"]["en"] == f"{rule.source_kind} → {rule.target_kind}"


def test_every_gap_field_a_register_can_emit_has_wording(example_root):
    for prefix, fields in (
        ("dora.wants.", ("doraCriticality", "provider", "contractRef", "functions supported")),
        ("ai.wants.", ("aiRiskClass", "aiRole", "aiOversight", "provider", "functions supported")),
        ("gdpr.wants.", tuple(field for field, _value, _only in gdpr.WANTED)),
    ):
        for field in fields:
            assert prefix + field in i18n.CATALOG, prefix + field


def test_english_is_the_default_and_polish_is_a_different_document(example_root):
    model, _documents, _config = dsl.load(example_root, "approved")
    english = docgen.build_markdown(model)
    assert english == docgen.build_markdown(model, "en")
    polish = docgen.build_markdown(model, "pl")
    assert polish != english
    assert "## 1. Interesariusze i ich zagadnienia" in polish
    assert "Architecture Description" not in polish
    assert polish == docgen.build_markdown(model, "pl"), "byte-stable in every language"
    with pytest.raises(ValueError):
        docgen.build_markdown(model, "de")


def test_the_committed_polish_description_is_fresh(example_root):
    model, _documents, _config = dsl.load(example_root, "approved")
    committed = (example_root / "docs" / "architecture-description.pl.md").read_text(encoding="utf-8")
    assert committed == docgen.build_markdown(model, "pl")


# ------------------------------------------------------------------------------ FRIA


def test_propose_from_ai_act_writes_a_fria_skeleton_for_a_deployers_high_risk_system(tmp_path):
    shutil.copytree(AICO, tmp_path / "repo")
    root = tmp_path / "repo"
    report = propose.propose(root, source="ai-act", as_of=date(2026, 10, 25))
    [proposal] = report.proposals
    assert proposal.id == "asm-fria-app-credit-scoring" and proposal.type == "Assessment"
    assert proposal.applies_to == ["app-credit-scoring"]
    assert "Art. 27" in proposal.documentation and proposal.documentation.startswith(propose.PLACEHOLDER)
    assert validate.validate(root, zone="staging").ok
    again = propose.propose(root, source="ai-act", as_of=date(2026, 10, 26), out=tmp_path / "x.yaml")
    assert not again.proposals, "the skeleton exists in staging, so the finding is skipped by name"
