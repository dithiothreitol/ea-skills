"""Does the quote support the claim? An entailment judge, proven before it measures (D11).

The core proves a quote *exists* in its source (``PROV003``, ``FACT004``) and, since 0.22.0,
measures whether it *names* the thing the claim is about (``FACT012``, ``PROV010``). Neither
proves the quote supports the claim -- "the ERP runs in the cloud" citing "The ERP core
holds the master order records" passes both. That question is entailment, which is
judgement, and judgement never enters ``easkills/``. It is measured here, outside the
core, and reported as a diagnostic: never a gate.

A judge is itself a model and can be wrong, so it is calibrated before any number it
produces is reported:

* **Supported pairs** -- every fact in the golden set with its own quote. Gold was written
  by the skills' rules and every quote there is the sentence the statement was drawn from.
* **Unsupported pairs** -- every statement with the quote of a *different* fact from the
  same case, chosen deterministically so the two share no listed entity: the same document,
  the same vocabulary, a different claim -- the shape a fabricated-but-located citation has.

The judge must clear ``BAR`` on both classes, or this module reports that it failed
calibration and reports nothing else. Only then does it read the registers the scored
harness produced (``--workdir``) and report, per run, the share of facts none of whose
quotes supports the statement: the unsupported-claim rate.

**The judge reads each quote where it sits.** A register cites "the narrowest verbatim span
that carries" a claim, and resolves what the span refers to from the text around it and
the entity table: "by calling the front desk.", "The ERP pushes...", a flattened table row
whose column names are a line above. The first design (2026-11-11) showed the judge the
quote alone and failed calibration on exactly those -- it accepted 86% of the supported
pairs, ten of its eleven misses being referents outside the span. So each pair now carries
the source text around the quote (``CONTEXT_CHARS`` either side): the context may resolve
what the quote refers to; the claim itself must still be carried by the quote.

Same quarantine as the rest of the harness: the SDK is reached through ``common.client()``,
nothing here is imported by the core, and nothing runs without a key.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import DEFAULT_MODEL, REPO_ROOT, RefusalError, Usage, client as api_client  # noqa: E402

BAR = 0.90
BATCH = 10
MAX_TOKENS = 8000
CONTEXT_CHARS = 300
GOLD_ROOTS = sorted(p for p in (REPO_ROOT / "eval" / "golden").iterdir() if (p / "facts").is_dir()) + [
    REPO_ROOT / "eval" / "example"
]

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "supported": {"type": "boolean"}},
                "required": ["index", "supported"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

SYSTEM = """You judge evidence, pair by pair.

Each numbered pair has a STATEMENT -- a claim an analyst wrote -- and a QUOTE -- the
verbatim span of a source document the analyst cited for it, usually the narrowest span
that carries the claim. When the quote could be located, CONTEXT is the source text it
sits in. Decide whether the quote, read where it sits, supports the statement.

- supported: the quote says what the statement claims, or the statement is a faithful
  restatement of it -- shorter, reworded, or with what the quote refers to (a pronoun, "the
  ERP", the subject of a sentence fragment, a table column) resolved from the context.
- not supported: the quote is about something else, says less than the statement claims,
  or contradicts it. The claim itself must be carried by the quote: context may tell you
  what the quote refers to, never supply a claim the quote does not make. A quote that
  merely shares words or a topic with the statement does not support it.

Judge only the pair you are given, never the world: a true statement with a quote that
does not say it is not supported. Answer with one verdict per pair, by its number."""


@dataclass
class Pair:
    case: str
    fact: str
    statement: str
    quote: str
    expected: bool | None = None  # None for a candidate pair: nobody knows the answer
    context: str = ""  # the source text the quote sits in; empty when it cannot be located


def around(text: str, quote: str, reach: int = CONTEXT_CHARS) -> str:
    """The source text a quote sits in, whitespace collapsed and widened to whole words."""
    from easkills import textfold  # local, like every core import here

    flat, needle = " ".join(text.split()), " ".join(quote.split())
    for haystack, wanted in ((flat, needle), (textfold.fold(flat), textfold.fold(needle))):
        at = haystack.find(wanted) if wanted else -1
        if at < 0:
            continue
        start, end = max(0, at - reach), min(len(haystack), at + len(wanted) + reach)
        while start > 0 and not haystack[start - 1].isspace():
            start -= 1
        while end < len(haystack) and not haystack[end].isspace():
            end += 1
        return ("... " if start else "") + haystack[start:end] + (" ..." if end < len(haystack) else "")
    return ""


def _facts(root: Path) -> list[dict[str, Any]]:
    from easkills import facts as facts_mod  # local: the harness reads the core, never the reverse

    register, _docs, _entities = facts_mod.load(root)
    sources: dict[str, str] = {}

    def context(file: str, quote: str) -> str:
        if file not in sources:
            try:
                sources[file] = (root / file).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                sources[file] = ""
        return around(sources[file], quote)

    return [
        {
            "id": fact.id,
            "statement": fact.statement,
            "quotes": [(p.quote, context(p.file, p.quote)) for p in fact.provenance if p.quote],
            "entities": set(fact.entities),
        }
        for fact in sorted(register.facts.values(), key=lambda f: f.id)
    ]


def gold_pairs() -> list[Pair]:
    pairs: list[Pair] = []
    for root in GOLD_ROOTS:
        for fact in _facts(root):
            for quote, context in fact["quotes"]:
                pairs.append(Pair(root.name, fact["id"], fact["statement"], quote, True, context))
    return pairs


def shuffled_pairs() -> list[Pair]:
    """Each statement with the first quote of the nearest later fact sharing no entity.

    Only facts that list entities take part, on either side: "shares no entity" is what
    keeps an unsupported pair unsupported, and a fact with no entities shares none with
    anything -- including the neighbouring sentence about the same system.
    """
    pairs: list[Pair] = []
    for root in GOLD_ROOTS:
        facts = [f for f in _facts(root) if f["quotes"] and f["entities"]]
        count = len(facts)
        for index, fact in enumerate(facts):
            own = {quote for quote, _context in fact["quotes"]}
            for step in range(1, count):
                other = facts[(index + step) % count]
                quote, context = other["quotes"][0]
                if fact["entities"] & other["entities"] or quote in own:
                    continue
                pairs.append(Pair(root.name, fact["id"], fact["statement"], quote, False, context))
                break
    return pairs


def _prompt(batch: list[Pair]) -> str:
    lines = ["Judge each pair.", ""]
    for number, pair in enumerate(batch, start=1):
        lines += [f"PAIR {number}", f"STATEMENT: {pair.statement}", f"QUOTE: {' '.join(pair.quote.split())}"]
        if pair.context:
            lines.append(f"CONTEXT: {pair.context}")
        lines.append("")
    return "\n".join(lines)


def judge(client: Any, model: str, pairs: list[Pair], usage: Usage, batch_size: int = BATCH) -> list[bool]:
    """One verdict per pair, in order. A batch whose verdicts do not cover it is a failure."""
    verdicts: list[bool] = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
            messages=[{"role": "user", "content": _prompt(batch)}],
        )
        usage.add(response)
        if response.stop_reason == "refusal":
            raise RefusalError("the judge declined a batch")
        if response.stop_reason == "max_tokens":
            raise ValueError(f"the judge's reply to a batch was cut off at {MAX_TOKENS} tokens")
        text = "".join(block.text for block in response.content if block.type == "text")
        by_index = {item["index"]: bool(item["supported"]) for item in json.loads(text)["verdicts"]}
        missing = [n for n in range(1, len(batch) + 1) if n not in by_index]
        if missing:
            raise ValueError(f"the judge left pair(s) {missing} of a batch without a verdict")
        verdicts += [by_index[n] for n in range(1, len(batch) + 1)]
    return verdicts


def calibrate(verdicts: list[bool], pairs: list[Pair]) -> dict[str, Any]:
    supported = [v for v, p in zip(verdicts, pairs) if p.expected is True]
    unsupported = [v for v, p in zip(verdicts, pairs) if p.expected is False]
    recall = sum(supported) / len(supported) if supported else 0.0
    specificity = sum(1 for v in unsupported if not v) / len(unsupported) if unsupported else 0.0
    misjudged = [asdict(p) | {"verdict": v} for v, p in zip(verdicts, pairs) if v != p.expected]
    return {
        "supportedPairs": len(supported),
        "unsupportedPairs": len(unsupported),
        "acceptsSupported": round(recall, 4),
        "rejectsUnsupported": round(specificity, 4),
        "bar": BAR,
        "passed": recall >= BAR and specificity >= BAR,
        "misjudged": misjudged,
    }


def candidate_pairs(workdir: Path) -> list[Pair]:
    """Every (statement, quote) of every register the scored harness produced.

    Only a run's case directories count: `--candidates` leaves `<case>-candidateN` copies of
    the same register beside each one, which would bill the judge and the report several
    times for one register. The workdir should be one invocation's -- an earlier, longer
    invocation's `runN` directories would be read too.
    """
    cases = {root.name for root in GOLD_ROOTS}
    pairs: list[Pair] = []
    for run in sorted(p for p in workdir.glob("run*") if p.is_dir()):
        for case in sorted(p for p in run.iterdir() if p.name in cases and (p / "facts" / "register").is_dir()):
            for fact in _facts(case):
                for quote, context in fact["quotes"]:
                    pairs.append(Pair(f"{run.name}/{case.name}", fact["id"], fact["statement"], quote, None, context))
    return pairs


def unsupported_rates(pairs: list[Pair], verdicts: list[bool]) -> dict[str, Any]:
    """Per run and case: the share of facts none of whose quotes supports the statement."""
    supported_by_fact: dict[tuple[str, str], bool] = {}
    for pair, verdict in zip(pairs, verdicts):
        key = (pair.case, pair.fact)
        supported_by_fact[key] = supported_by_fact.get(key, False) or verdict
    per_case: dict[str, dict[str, Any]] = {}
    for (case, fact), supported in sorted(supported_by_fact.items()):
        entry = per_case.setdefault(case, {"facts": 0, "unsupported": [], "rate": 0.0})
        entry["facts"] += 1
        if not supported:
            entry["unsupported"].append(fact)
    for entry in per_case.values():
        entry["rate"] = round(len(entry["unsupported"]) / entry["facts"], 4) if entry["facts"] else 0.0
    return per_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate the entailment judge, then measure the harness's registers")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--workdir", type=Path, help="the scored harness's --workdir; omitted, only calibration runs")
    parser.add_argument("--out", type=Path, required=True, help="the JSON report")
    args = parser.parse_args(argv)

    client = api_client()
    usage = Usage()
    calibration_pairs = gold_pairs() + shuffled_pairs()
    located = sum(1 for pair in calibration_pairs if pair.context)
    report: dict[str, Any] = {
        "model": args.model,
        "design": f"quote read in its source context ({CONTEXT_CHARS} characters either side)",
        "quotesLocated": f"{located}/{len(calibration_pairs)}",
    }
    try:
        report["calibration"] = calibrate(judge(client, args.model, calibration_pairs, usage), calibration_pairs)
        if not report["calibration"]["passed"]:
            report["measurement"] = "not reported: the judge did not clear the bar on the labelled pairs"
        elif args.workdir:
            pairs = candidate_pairs(args.workdir)
            report["measurement"] = unsupported_rates(pairs, judge(client, args.model, pairs, usage))
    except (RefusalError, ValueError) as exc:  # a failed batch is a failed run, reported with what it cost
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["usage"] = usage.as_dict()
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if "error" in report:
        print(f"the judge stopped: {report['error']} -- what it cost is in {args.out}")
        return 1
    calibration = report["calibration"]
    print(
        f"calibration: accepts {calibration['acceptsSupported']:.0%} of {calibration['supportedPairs']} supported, "
        f"rejects {calibration['rejectsUnsupported']:.0%} of {calibration['unsupportedPairs']} unsupported "
        f"(bar {BAR:.0%}) -- {'passed' if calibration['passed'] else 'FAILED'}"
    )
    if isinstance(report.get("measurement"), dict):
        for case, entry in report["measurement"].items():
            print(f"  {case}: {len(entry['unsupported'])}/{entry['facts']} facts unsupported ({entry['rate']:.0%})")
    return 0 if calibration["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
