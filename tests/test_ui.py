"""Colour is display, never data: styled under FORCE_COLOR, byte-identical plain
text everywhere else, and gates must not change their exit codes either way."""

import pytest

from easkills import cli, ui


@pytest.fixture()
def forced(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)


@pytest.fixture()
def plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")


def test_disabled_by_default_under_capture():
    """pytest's capture is not a TTY, so all helpers must pass text through."""
    assert ui.bold("x") == "x"
    assert ui.red("x") == "x"
    assert ui.severity("ERROR  ") == "ERROR  "


def test_force_color_wraps_with_ansi(forced):
    assert ui.bold("x") == "\033[1mx\033[0m"
    assert ui.red("x").startswith("\033[31m")


def test_no_color_wins_over_force(forced, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert ui.bold("x") == "x"


def test_severity_palette(forced):
    assert "\033[31m" in ui.severity("ERROR")
    assert "\033[33m" in ui.severity("WARNING")
    assert "\033[36m" in ui.severity("INFO")


def test_status_palette(forced):
    assert "\033[32m" in ui.status("PASS")
    assert "\033[31m" in ui.status("FAIL")
    assert "\033[35m" in ui.status("GAP")


def test_verdict_line_keeps_the_contract_words(plain):
    assert "PASS" in ui.verdict(True, 0, 0)
    assert "FAIL" in ui.verdict(False, 2, 1)


def test_symbols_fall_back_when_console_cannot_encode(monkeypatch):
    class AsciiStream:
        encoding = "ascii"

    monkeypatch.setattr("sys.stdout", AsciiStream())
    assert ui.sym("✓", "OK") == "OK"


def test_no_artifact_generator_imports_the_terminal_styling():
    """Committed artifacts must not be able to vary with the console.

    `ui` styling depends on TTY detection and `sys.stdout.encoding` (symbols fall back
    to ASCII). Any of that leaking into a *written file* would make the generated
    schemas, SVGs, exchange file or architecture description environment-dependent --
    and the CI freshness check would then pass or fail depending on the runner. Today
    that separation holds by discipline; this test makes it structural.
    """
    import ast
    from pathlib import Path

    package = Path(__file__).resolve().parents[1] / "easkills"
    for module in ("docgen", "render", "aoef", "contextpack", "genschema"):
        source = (package / f"{module}.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[-1] for alias in node.names)
        assert "ui" not in imported, f"{module}.py writes artifacts and must not import ui"


def test_styled_report_keeps_exit_codes(forced, example_root, broken_root, capsys):
    assert cli.main(["validate", "--root", str(example_root)]) == 0
    out = capsys.readouterr().out
    assert "\033[" in out, "styling should be active under FORCE_COLOR"
    assert "PASS" in out
    assert cli.main(["validate", "--root", str(broken_root)]) == 1
    capsys.readouterr()
