"""Measure quote anchoring before it becomes a rule (D10).

A located quote proves the text exists; it does not prove the text is about the claim.
The cheapest deterministic proxy is *anchoring*: the quote names the thing the claim is
about, through the entity alias table. It will misfire -- "it runs on one server" names
nothing -- so it is measured over every repository that carries a register before any
rule fires on it, and the false positives are counted and written down.

Two checks, exactly as `easkills/anchors.py` implements them (this script only runs them
and prints what they find):

* **fact**: a fact lists entities, and none of its quotes names any of them.
* **element**: an element cites facts that list entities, and none of those entities
  answers to the element by name, nor does any cited quote name the element.

Usage::

    python tools/anchor_report.py eval/golden/clinic eval/example ...

Standard library plus the tooling itself; read-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from easkills import anchors, dsl, facts as facts_mod  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("roots", nargs="+", type=Path, help="architecture repositories to measure")
    args = parser.parse_args(argv)
    totals = {"facts": 0, "fact findings": 0, "elements": 0, "element findings": 0}
    for root in args.roots:
        register, _docs, _entities = facts_mod.load(root)
        model, _mdocs, _config = dsl.load(root, "approved")
        fact_findings = anchors.unanchored_facts(register)
        element_findings = anchors.unanchored_elements(model, register)
        listed = sum(1 for f in register.facts.values() if f.entities)
        citing = sum(1 for e in model.elements.values() if any(p.fact for p in e.provenance))
        totals["facts"] += listed
        totals["fact findings"] += len(fact_findings)
        totals["elements"] += citing
        totals["element findings"] += len(element_findings)
        print(f"== {root}  ({listed} facts listing entities, {citing} elements citing facts)")
        for finding in fact_findings + element_findings:
            print(f"   {finding.code} [{finding.concept}] {finding.message}")
    print(
        f"TOTAL facts {totals['fact findings']}/{totals['facts']}, "
        f"elements {totals['element findings']}/{totals['elements']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
