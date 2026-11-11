"""Scale, asserted as operation counts -- never as seconds.

A timing test fails on a slow runner and passes on a fast one, and either way it says
nothing about the code. What made ``validate`` superlinear (66.9 s at 3000 elements,
2026-11-10) was an operation repeated per quote that should happen per source, so that is
what these tests count: how often a source is normalized, how many windows a missing quote
costs, and whether the faster YAML loader reads every committed file exactly as the
reference loader does. The timings themselves live in docs/CLI.md, dated, as a
measurement rather than a claim.
"""

from __future__ import annotations

import difflib
import importlib.util
from pathlib import Path

import pytest
import yaml

from easkills import dsl, facts as facts_mod, textfold, validate as validate_mod

REPO_ROOT = Path(__file__).resolve().parents[1]


def _synth():
    spec = importlib.util.spec_from_file_location("synth_repo", REPO_ROOT / "tools" / "synth_repo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def normalized_texts(monkeypatch):
    """Every string the matcher normalizes, in order."""
    seen: list[str] = []
    real = textfold.normalize

    def counting(text: str) -> str:
        seen.append(text)
        return real(text)

    monkeypatch.setattr(textfold, "normalize", counting)
    return seen


def test_the_model_gate_normalizes_a_source_once_however_many_quotes_cite_it(tmp_path, normalized_texts):
    synth = _synth()
    root = synth.build(tmp_path / "repo", 60)
    source = (root / synth.SOURCE).read_text(encoding="utf-8")
    report = validate_mod.validate(root)
    assert report.ok, [f.render() for f in report.errors]
    # 60 elements and 120 relationships quote it -- 180 citations, one normalization.
    assert normalized_texts.count(source) == 1


def test_the_evidence_gate_normalizes_a_source_once_however_many_facts_cite_it(repo_root, normalized_texts):
    example = repo_root / "eval" / "example"
    register, _docs, _entities = facts_mod.load(example)
    interview = example / "facts" / "sources" / "interview-operations-2026-07-15.md"
    citing = sum(
        1 for fact in register.facts.values() for p in fact.provenance if p.file.endswith(interview.name)
    )
    assert citing > 5, "the example should cite its interview many times, or this proves nothing"
    assert facts_mod.validate_facts(example).ok
    assert normalized_texts.count(interview.read_text(encoding="utf-8")) == 1


def test_a_missing_quote_costs_one_pass_over_the_source(monkeypatch):
    """The approximate search slides a window of the quote's length in quarter steps, and
    a quote that is not there must cost exactly that pass -- linear in the source -- not
    a pass per anything else. Measured 0.3-1.9 s per missing quote against 1 MB."""
    windows: list[int] = []

    class Counting(difflib.SequenceMatcher):
        def set_seq1(self, a):
            windows.append(len(a))
            super().set_seq1(a)

    monkeypatch.setattr(validate_mod.difflib, "SequenceMatcher", Counting)
    haystack = validate_mod._normalize("alpha beta gamma delta epsilon " * 4000)
    quote = validate_mod._normalize("this sentence appears nowhere in the source text at all")
    assert validate_mod._quote_match(haystack, quote, 0.9) == "missing"
    step = max(1, len(quote) // 4)
    assert len(windows) <= len(haystack) // step + 2


def _yaml_files() -> list[Path]:
    bases = ("eval", "template", "references", "evals")
    return sorted(
        path
        for base in bases
        for path in (REPO_ROOT / base).rglob("*")
        if path.is_file() and path.suffix in {".yaml", ".yml"}
    )


@pytest.mark.skipif(not hasattr(yaml, "CSafeLoader"), reason="this PyYAML was built without libyaml")
def test_the_c_loader_reads_every_committed_yaml_file_exactly_as_the_python_loader():
    files = _yaml_files()
    assert len(files) > 100, "the fixture set looks unreadable from here"
    differences: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            expected: tuple = ("ok", yaml.load(text, Loader=yaml.SafeLoader))
        except dsl.YAML_ERRORS:
            expected = ("error",)
        try:
            actual: tuple = ("ok", yaml.load(text, Loader=yaml.CSafeLoader))
        except dsl.YAML_ERRORS:
            actual = ("error",)
        if actual != expected:
            differences.append(str(path.relative_to(REPO_ROOT)))
    assert not differences, f"the loaders disagree on: {differences}"


@pytest.mark.parametrize("text", ["a: b: c\n", "key: [unclosed\n", "\tindented: tab\n", "k: v\n- x\n", "{unclosed: 1\n"])
def test_a_parse_error_reads_the_same_whichever_loader_is_installed(text):
    """libyaml words errors differently and drops the snippet showing where; the report a
    gate prints must not depend on how PyYAML was built, so the reference loader states it."""
    with pytest.raises(dsl.YAML_ERRORS) as reference:
        yaml.load(text, Loader=yaml.SafeLoader)
    with pytest.raises(dsl.YAML_ERRORS) as shared:
        dsl.load_yaml(text)
    assert str(shared.value) == str(reference.value)


def test_the_shared_loader_is_the_safe_one():
    """Whichever implementation is installed, it must be a *safe* loader: repository
    content is data, and a tag that constructs a Python object is refused."""
    with pytest.raises(dsl.YAML_ERRORS):
        dsl.load_yaml("!!python/object/apply:os.system ['echo unsafe']")
    assert dsl.load_yaml("lastReviewed: 2026-06-30")["lastReviewed"].isoformat() == "2026-06-30"
    with pytest.raises(dsl.YAML_ERRORS):
        dsl.load_yaml("lastReviewed: 2026-06-31")  # the resolver's ValueError, kept
