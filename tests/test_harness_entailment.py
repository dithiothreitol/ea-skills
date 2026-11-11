"""The entailment judge's logic, in the default gate, without a key (D11).

The judge costs tokens and is never run here; what is tested is everything around it that
could make its number wrong without anybody noticing: the labelled pairs, the batching and
its refusal of an incomplete batch, the calibration arithmetic, and the rule that a judge
which fails calibration reports nothing else.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HARNESS = Path(__file__).resolve().parents[1] / "eval" / "harness"


@pytest.fixture(scope="module")
def entailment():
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("ea_entailment", HARNESS / "entailment.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ea_entailment"] = module
    spec.loader.exec_module(module)
    return module


def test_every_gold_fact_is_a_supported_pair_and_none_is_paired_with_its_own_quote(entailment):
    supported = entailment.gold_pairs()
    unsupported = entailment.shuffled_pairs()
    assert len(supported) > 70 and len(unsupported) > 60
    own = {(p.case, p.fact, p.quote) for p in supported}
    assert not [p for p in unsupported if (p.case, p.fact, p.quote) in own]
    assert entailment.shuffled_pairs() == unsupported, "the unsupported pairs are deterministic"


def test_every_gold_quote_is_read_where_it_sits(entailment):
    """The judge's first design read quotes alone and failed calibration on fragments whose
    referent sits outside the span; a quote it cannot locate would bring that back silently."""
    from easkills import textfold

    pairs = entailment.gold_pairs() + entailment.shuffled_pairs()
    assert not [(p.case, p.fact) for p in pairs if not p.context]
    for pair in pairs:  # in folded form: a quote with typographic dashes is located by its folding
        assert textfold.fold(" ".join(pair.quote.split())) in textfold.fold(pair.context), (pair.case, pair.fact)


def test_around_widens_to_whole_words_and_says_where_it_cut(entailment):
    text = "Alpha beta gamma.\nPatients book appointments\nby calling the front desk. Delta epsilon zeta."
    shown = entailment.around(text, "by calling the front\n desk.", reach=12)
    assert shown.startswith("... ") and shown.endswith(" ...")
    assert "appointments by calling the front desk. Delta" in shown
    assert entailment.around(text, "not in the text") == ""
    assert entailment.around("the “ERP” pushes orders", 'the "ERP" pushes') == 'the "ERP" pushes orders'


def test_the_prompt_carries_the_context_only_when_there_is_one(entailment):
    with_context = entailment.Pair("c", "f", "S.", "q", None, "before q after")
    without = entailment.Pair("c", "g", "T.", "r")
    prompt = entailment._prompt([with_context, without])
    assert prompt.count("CONTEXT:") == 1 and "CONTEXT: before q after" in prompt


def _fake_client(answer):
    def create(**request):
        prompt = request["messages"][0]["content"]
        count = prompt.count("PAIR ")
        verdicts = [{"index": n, "supported": answer(n)} for n in range(1, count + 1)]
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps({"verdicts": verdicts}))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0),
            model="fake",
        )

    return SimpleNamespace(messages=SimpleNamespace(create=create))


def test_the_judge_batches_and_keeps_order(entailment):
    pairs = [entailment.Pair("c", f"f{i}", "s", "q", None) for i in range(23)]
    usage = entailment.Usage()
    verdicts = entailment.judge(_fake_client(lambda n: n % 2 == 0), "m", pairs, usage, batch_size=10)
    assert len(verdicts) == 23 and usage.calls == 3
    assert verdicts[:4] == [False, True, False, True]


def test_an_incomplete_batch_is_a_failure_not_a_guess(entailment):
    def create(**_request):
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps({"verdicts": [{"index": 1, "supported": True}]}))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0),
            model="fake",
        )

    pairs = [entailment.Pair("c", "a", "s", "q"), entailment.Pair("c", "b", "s", "q")]
    with pytest.raises(ValueError, match="without a verdict"):
        entailment.judge(SimpleNamespace(messages=SimpleNamespace(create=create)), "m", pairs, entailment.Usage())


def test_calibration_needs_both_classes_above_the_bar(entailment):
    pairs = [entailment.Pair("c", f"s{i}", "s", "q", True) for i in range(10)]
    pairs += [entailment.Pair("c", f"u{i}", "s", "q", False) for i in range(10)]
    always_yes = entailment.calibrate([True] * 20, pairs)
    assert always_yes["acceptsSupported"] == 1.0 and always_yes["rejectsUnsupported"] == 0.0
    assert not always_yes["passed"], "a judge that says yes to everything must not be believed"
    honest = entailment.calibrate([True] * 10 + [False] * 9 + [True], pairs)
    assert honest["passed"] and len(honest["misjudged"]) == 1


def test_a_fact_is_unsupported_only_when_no_quote_supports_it(entailment):
    pairs = [
        entailment.Pair("run1/clinic", "fact-a", "s", "q1"),
        entailment.Pair("run1/clinic", "fact-a", "s", "q2"),
        entailment.Pair("run1/clinic", "fact-b", "s", "q3"),
    ]
    rates = entailment.unsupported_rates(pairs, [False, True, False])
    assert rates["run1/clinic"] == {"facts": 2, "unsupported": ["fact-b"], "rate": 0.5}


def test_the_judge_reaches_the_sdk_only_through_common(entailment):
    source = (HARNESS / "entailment.py").read_text(encoding="utf-8")
    assert "import anthropic" not in source
    assert "client as api_client" in source
