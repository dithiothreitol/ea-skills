"""The lifecycle simulation, in the gate: every step behaves the way the script expects.

`tools/simulate.py` is an instrument -- it writes a full artifact set for a person to read --
but every step of it is deterministic: no network, no tokens. So the property it exists for
(each command, hook and check behaves as expected, in order, with state carried from one
step to the next) is held here, where a regression in how the commands work *together*
fails before a release instead of in front of an adopter. The paid instruments taught that
lesson on 2026-11-11: a deterministic step that only ever runs inside a paid run fails
there first.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def simulate():
    spec = importlib.util.spec_from_file_location("ea_simulate", REPO_ROOT / "tools" / "simulate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ea_simulate"] = module
    spec.loader.exec_module(module)
    return module


def test_the_simulation_deletes_only_what_it_wrote(simulate, tmp_path):
    """It replaces its output directory -- so it must never be handed one that matters."""
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "notes.md").write_text("not the simulation's\n", encoding="utf-8")
    assert simulate.main([str(precious)]) == 2 and (precious / "notes.md").is_file()
    assert simulate.main([str(REPO_ROOT)]) == 2, "the checkout itself"
    assert simulate.main([str(REPO_ROOT.parent)]) == 2, "a directory holding the checkout"
    assert simulate.main([str(REPO_ROOT / "simulation-out")]) == 2 and not (REPO_ROOT / "simulation-out").exists()


def test_the_whole_lifecycle_behaves_as_expected(simulate, tmp_path):
    pytest.importorskip("pypdf")  # round one converts a PDF
    out = tmp_path / "simulation"
    exit_code = simulate.main([str(out)])
    steps = json.loads((out / "steps.json").read_text(encoding="utf-8"))
    unexpected = [f"{s['part']} / {s['step']}: {s.get('verdict') or s['exit']} (expected {s['expected']})"
                  for s in steps if not s["ok"]]
    assert exit_code == 0 and not unexpected, unexpected
    kinds = {s["kind"] for s in steps}
    assert kinds == {"command", "hook", "act", "check", "mcp"}, "a kind of step went missing"
    assert len(steps) >= 120, "the story got shorter -- a removed step should be a decision, not a drift"
    assert (out / "INDEX.md").is_file()
    assert simulate._refuse_target(out) is None, "an earlier simulation's output is the one directory it may replace"
