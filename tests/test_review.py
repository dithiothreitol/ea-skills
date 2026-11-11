"""The review sheet (D5): every staged claim beside its evidence, weakest first.

The sheet is what a person reads before signing a promotion, so the properties tested are
the ones a signer relies on: the weakest claims come first, every exact quote carries the
line a reader can open, disputed evidence says what it disputes, a deletion is shown as a
deletion, and the same repository always yields the same bytes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from easkills import cli, review


def _staged_copy(tmp_path: Path, source: Path, files: list[str]) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(source, root, ignore=shutil.ignore_patterns("docs", "build"))
    staging = root / "model" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    for name in files:
        shutil.copy(root / "model" / "approved" / name, staging / name)
    return root


def test_the_weakest_claims_come_first_and_quotes_carry_their_lines(tmp_path, example_root):
    root = _staged_copy(tmp_path, example_root, ["strategy.yaml", "application.yaml"])
    sheet = review.review(root)
    strengths = [claim.strength for claim in sheet.claims]
    assert strengths == sorted(strengths, key=review.STRENGTHS.index)
    assert strengths[0] == "assumed", "the example's assumed goal is the weakest claim staged"
    text = review.markdown(sheet)
    assert text.index("No evidence -- declared assumptions") < text.index("Verbatim evidence")
    assert "`facts/sources/interview-operations-2026-07-15.md` lines 25-26" in text
    assert "**Assumed:**" in text


def test_disputed_evidence_says_what_it_disputes(tmp_path, repo_root):
    root = _staged_copy(tmp_path, repo_root / "eval" / "golden" / "contested", ["courier.yaml"])
    text = review.markdown(review.review(root))
    assert "## Evidence the sources dispute" in text
    assert "(contested: disputes `" in text


def test_a_replacement_that_drops_a_concept_shows_the_deletion(tmp_path, example_root):
    root = _staged_copy(tmp_path, example_root, ["technology.yaml"])
    staged = root / "model" / "staging" / "technology.yaml"
    text = staged.read_text(encoding="utf-8")
    cut = text.index("  - id: sysswt-postgresql")
    staged.write_text(text[:cut], encoding="utf-8")
    sheet = review.review(root)
    assert sheet.moves == [("model/staging/technology.yaml", "model/approved/technology.yaml", True)]
    assert "sysswt-postgresql" in sheet.removed
    assert "**Deleted from the approved zone**" in review.markdown(sheet)


def test_the_sheet_is_byte_stable(tmp_path, example_root):
    root = _staged_copy(tmp_path, example_root, ["application.yaml"])
    assert review.markdown(review.review(root)) == review.markdown(review.review(root))


def test_nothing_staged_is_a_refusal_not_an_empty_sheet(tmp_path, example_root):
    root = tmp_path / "repo"
    shutil.copytree(example_root, root)
    with pytest.raises(review.ReviewError, match="nothing to promote"):
        review.review(root)
    assert cli.main(["review", "--root", str(root)]) == 1


def test_the_cli_writes_the_sheet_where_asked(tmp_path, example_root):
    root = _staged_copy(tmp_path, example_root, ["application.yaml"])
    out = tmp_path / "sheet.md"
    assert cli.main(["review", "--root", str(root), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Review sheet")
