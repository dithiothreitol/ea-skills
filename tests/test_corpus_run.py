"""The external corpus run's offline half: what makes its numbers repeatable and its files its own.

The run itself fetches from the network and is never in the gate. What is held here is what
would make a rerun disagree with a recorded one without anything having changed in the
tooling: a source read at a moving branch, and two files with one name overwriting each
other's artifacts.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def corpus():
    spec = importlib.util.spec_from_file_location("ea_corpus_run", REPO_ROOT / "tools" / "corpus_run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ea_corpus_run"] = module
    spec.loader.exec_module(module)
    return module


def test_every_source_is_read_at_a_pinned_commit(corpus):
    """`master` moves; a corpus number recorded against it cannot be reproduced."""
    for repo, commit, licence, _paths in corpus.MANIFEST:
        assert re.fullmatch(r"[0-9a-f]{12,40}", commit), f"{repo} is read at {commit!r}, not a commit"
        assert licence in {"MIT", "Apache-2.0"}, f"{repo}: {licence}"


def test_two_files_with_one_name_keep_their_own_artifacts(corpus, tmp_path):
    export = REPO_ROOT / "eval" / "fixtures" / "adoption" / "meridian-export.xml"
    sources = []
    for folder in ("first__repo/models", "second__repo/models"):
        target = tmp_path / "files" / folder / "model.xml"
        target.parent.mkdir(parents=True)
        shutil.copy(export, target)
        sources.append(target)
    entries = [corpus.run_one(tmp_path, source) for source in sources]
    roots = sorted(p for p in (tmp_path / "repos").iterdir())
    assert len(roots) == 2, "one file's scratch repository replaced the other's"
    for entry in entries:
        assert entry["importExit"] == 0 and entry["elements"] and "codes" in entry, entry
        assert entry["validateExit"] == 1 and entry["codes"].get("REL001") == 1, "the fixture's one illegal edge"
