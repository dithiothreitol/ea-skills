"""The CLI is what skills and CI call; its exit codes are the contract."""

import json

from easkills import cli, genschema, oracle


def test_validate_exit_zero_on_clean_model(example_root, capsys):
    assert cli.main(["validate", "--root", str(example_root)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_validate_exit_one_on_broken_model(broken_root, capsys):
    assert cli.main(["validate", "--root", str(broken_root)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_strict_mode_fails_on_warnings(broken_root, capsys):
    assert cli.main(["validate", "--root", str(broken_root), "--strict"]) == 1
    capsys.readouterr()


def test_validate_writes_json_report(example_root, tmp_path, capsys):
    report_path = tmp_path / "report.json"
    assert cli.main(["validate", "--root", str(example_root), "--json", str(report_path)]) == 0
    capsys.readouterr()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["zone"] == "approved"


def test_compile_writes_exchange_file(example_root, tmp_path, capsys):
    out = tmp_path / "model.xml"
    assert cli.main(["compile", "--root", str(example_root), "--out", str(out)]) == 0
    assert "XSD validation passed" in capsys.readouterr().out
    assert out.exists()


def test_compile_refuses_invalid_model(broken_root, tmp_path, capsys):
    out = tmp_path / "model.xml"
    assert cli.main(["compile", "--root", str(broken_root), "--out", str(out)]) == 1
    assert "Refusing to compile" in capsys.readouterr().out
    assert not out.exists()


def test_oracle_info(capsys):
    assert cli.main(["oracle-info"]) == 0
    out = capsys.readouterr().out
    assert "3.2" in out
    assert "FAIL" not in out


def test_generated_schema_is_committed_and_current(capsys):
    """A stale committed schema would silently accept concepts the oracle rejects."""
    on_disk = genschema.load_schema(genschema.SCHEMA_PATH)
    assert on_disk == genschema.build_schema(), "run 'python -m easkills gen-schema'"


def test_schema_enumerates_every_oracle_concept():
    schema = genschema.load_schema(genschema.SCHEMA_PATH)
    assert set(schema["$defs"]["element"]["properties"]["type"]["enum"]) == set(oracle.element_types())
    assert set(schema["$defs"]["relationship"]["properties"]["type"]["enum"]) == set(oracle.relationship_types())
