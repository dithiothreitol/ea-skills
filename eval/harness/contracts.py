"""Contract checks for the governance skills: does the prose produce a valid record?

The golden-set harness measures *similarity to gold*, which works for extraction and
modelling because there is a right answer to compare against. Governance records have no
such gold: two architects write different ADRs for one decision and both can be right. What
they cannot do is write one that fails its own rules -- a waiver with no expiry, a decision
bound to no element, a supersession that leaves the old record governing the model.

So these are **contracts**, not scores. A scenario goes in with the skill's prose; a record
comes out; deterministic checks say whether it holds. Every check is a property the
repository's own tooling or the skill's own text already states, and each one names the rule
it comes from, so a failure is a defect in the prose rather than a disagreement about taste.

Usage::

    python eval/harness/contracts.py --runs 3
    python eval/harness/contracts.py --contract supersede --runs 1 --keep

Never part of the default gate: it costs tokens and calls a model.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml

from common import (  # noqa: E402
    DEFAULT_MODEL,
    MAX_REPAIRS,
    OUTPUT_CONTRACT,
    REPO_ROOT,
    Session,
    Usage,
    client as api_client,
    easkills,
    extract_files,
    skill,
    write_files,
)

# The scenario repository is the worked example: a governance record only makes sense
# against a model that already has elements, standards and a decision log. Copying it is not
# an answer leak -- nothing here is scored against the records it contains, and a real
# adopter's repository looks exactly like this on the day they file their second ADR.
FIXTURE = REPO_ROOT / "eval" / "example"
TODAY = date(2026, 8, 6)  # fixed: a contract that drifts with the wall clock is not a contract


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ContractResult:
    contract: str
    model: str
    ok: bool = False
    gate: int | None = None
    repairs: int = 0
    checks: list[CheckResult] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""
    seconds: float = 0.0

    @property
    def failed(self) -> list[str]:
        return [check.name for check in self.checks if not check.passed]

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "model": self.model,
            "ok": self.ok,
            "gate": self.gate,
            "repairs": self.repairs,
            "checks": [check.__dict__ for check in self.checks],
            "usage": self.usage,
            "error": self.error,
            "seconds": self.seconds,
        }


@dataclass(frozen=True)
class Contract:
    """One scenario, the skills it measures, and the properties its output must hold."""

    name: str
    skills: tuple[str, ...]
    scenario: str
    gate: tuple[str, ...]  # the deterministic command that must pass first
    checks: Callable[[Path], list[CheckResult]]
    prepare: Callable[[Path], None] | None = None


# --------------------------------------------------------------------------- helpers


def load_records(root: Path, kind: str) -> dict[str, dict[str, Any]]:
    """Every YAML record of one kind, keyed by id -- read as data, never interpreted."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "governance-log" / kind).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("id"):
            out[str(data["id"])] = data
    return out


def model_ids(root: Path) -> set[str]:
    from easkills import dsl  # local: the harness reads the core, never the reverse

    model, _documents, _config = dsl.load(root, "approved")
    return set(model.elements)


def standard_ids(root: Path) -> set[str]:
    out = set()
    for path in sorted((root / "standards").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("id"):
            out.add(str(data["id"]))
    return out


def correspondence_violations(root: Path) -> list[str]:
    """§6.9 violations the repository derives for itself, as codes.

    Read through the core rather than by grepping the report: the rendered report prints
    each rule's `enforced by: CORR001, ...` line whether or not anything violates it, so a
    string search there would fail forever and look like a broken skill.
    """
    from easkills import correspond, dsl, govern

    model, _documents, _config = dsl.load(root, "approved")
    findings = correspond.findings(correspond.derive(model, govern.load(root), TODAY))
    return [f"{finding.code} {finding.concept}" for finding in findings]


def check(name: str, condition: bool, detail: str = "") -> CheckResult:
    return CheckResult(name=name, passed=bool(condition), detail=detail)


def as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------- contracts

DECISION_SCENARIO = """
The architecture board met on 2026-08-06. The warehouse management system's cloud move has
no approved budget for the coming year, and peak season starts in October, so the board
decided that the WMS stays on-premise through 2027 and the question returns in the 2028
planning round. The alternatives discussed were a phased lift-and-shift during Q1 and
replacing the WMS outright with a SaaS product.

File this as an architecture decision record in this repository.
"""


def decision_checks(root: Path) -> list[CheckResult]:
    """Properties `ea-adr` states about a record worth having."""
    records = load_records(root, "decisions")
    new = {rid: data for rid, data in records.items() if rid != "decision-order-api-single-integration"}
    results = [check("one new decision record", len(new) == 1, f"found {sorted(new)}")]
    if len(new) != 1:
        return results
    record = next(iter(new.values()))
    mandatory = ("id", "title", "status", "date", "context", "decision", "rationale", "consequences")
    missing = [key for key in mandatory if not record.get(key)]
    results.append(check("MADR fields present", not missing, f"missing {missing}"))
    results.append(
        check(
            "status is proposed or accepted",
            record.get("status") in {"proposed", "accepted"},
            str(record.get("status")),
        )
    )
    options = record.get("options") or []
    results.append(
        check(
            "the rejected options are recorded with pros and cons",
            len(options) >= 2 and all(item.get("pros") and item.get("cons") for item in options),
            f"{len(options)} option(s)",
        )
    )
    related = record.get("relatedElements") or []
    ids = model_ids(root)
    results.append(
        check(
            "bound to real model elements",
            bool(related) and set(related) <= ids,
            f"{related} vs model ({len(ids)} elements)",
        )
    )
    results.append(
        check(
            "scoped, not blanket",
            len(related) < len(ids),
            f"{len(related)} of {len(ids)} elements",
        )
    )
    return results


DISPENSATION_SCENARIO = """
The order portal is hosted in managed cloud, which the cloud-hosting standard permits, but
the PostgreSQL 16 standard (std-postgresql-16) is not met by the ERP core's database: it
runs an older major version and the upgrade window is blocked until the finance year-end
freeze lifts in February 2027. The architecture board is willing to accept the risk in the
meantime; the board's address in this repository is architecture-board@aurorafoods.example.

File the waiver in this repository, dated 2026-08-06.
"""


def dispensation_checks(root: Path) -> list[CheckResult]:
    """Properties `ea-dispensation` states about real governance."""
    records = load_records(root, "dispensations")
    new = {rid: data for rid, data in records.items() if rid != "disp-onprem-legacy"}
    results = [check("one new dispensation record", len(new) == 1, f"found {sorted(new)}")]
    if len(new) != 1:
        return results
    record = next(iter(new.values()))
    granted = as_date(record.get("granted"))
    expires = as_date(record.get("expires"))
    results.append(check("expiry is present and a date", expires is not None, str(record.get("expires"))))
    if granted and expires:
        window = (expires - granted).days
        results.append(
            check(
                "the window is bounded and defensible",
                0 < window <= 550,
                f"{window} day(s) from {granted} to {expires}",
            )
        )
    results.append(check("status is open", record.get("status") == "open", str(record.get("status"))))
    waives = (record.get("waives") or {}).get("standard")
    results.append(
        check(
            "waives a standard that exists",
            waives in standard_ids(root),
            f"{waives} vs {sorted(standard_ids(root))}",
        )
    )
    applies = record.get("appliesTo") or []
    ids = model_ids(root)
    results.append(
        check(
            "scoped to real elements, not to everything",
            bool(applies) and set(applies) <= ids and len(applies) < len(ids),
            f"{applies}",
        )
    )
    results.append(
        check(
            "granted by a named authority, not the author",
            "@" in str(record.get("grantedBy", "")),
            str(record.get("grantedBy")),
        )
    )
    results.append(check("rationale present", bool(record.get("rationale"))))
    return results


SUPERSEDE_SCENARIO = """
The board reversed decision-order-api-single-integration on 2026-08-06: the portal will get
a second, event-based channel for stock levels, because the single synchronous API made the
portal unavailable whenever the ERP was down and that outage class is what the board
decided to remove. The order API remains for order submission.

Record the reversal in this repository, and leave the governance log in a state where the
superseded record no longer governs anything.
"""


def supersede_checks(root: Path) -> list[CheckResult]:
    """The hardest paragraph in `ea-adr`, which exists because of `CORR001`.

    Superseding is three moves, not one: the new record, the old record's status *and*
    pointer, and the elements carried over. Miss the third and the model still realises a
    decision that no longer stands -- which is exactly what the correspondence rule reports.
    """
    records = load_records(root, "decisions")
    old = records.get("decision-order-api-single-integration")
    new = {rid: data for rid, data in records.items() if rid != "decision-order-api-single-integration"}
    results = [
        check("the old record still exists", old is not None, "records are amended, never rewritten"),
        check("a successor record was written", len(new) == 1, f"found {sorted(new)}"),
    ]
    if old is None or len(new) != 1:
        return results
    successor_id = next(iter(new))
    results.append(check("the old record is superseded", old.get("status") == "superseded", str(old.get("status"))))
    results.append(
        check(
            "supersededBy points at the successor",
            old.get("supersededBy") == successor_id,
            f"{old.get('supersededBy')} vs {successor_id}",
        )
    )
    results.append(
        check(
            "the superseded record governs nothing",
            not (old.get("relatedElements") or []),
            f"still bound to {old.get('relatedElements')}",
        )
    )
    results.append(
        check(
            "the successor carries the elements",
            bool(next(iter(new.values())).get("relatedElements")),
        )
    )
    # And the mechanical judge of all of the above: the correspondence rule itself.
    results.append(check("no CORR001 correspondence violation", not correspondence_violations(root)))
    return results


CONTRACTS: tuple[Contract, ...] = (
    Contract(
        name="decision",
        skills=("ea-adr",),
        scenario=DECISION_SCENARIO,
        gate=("validate-gov",),
        checks=decision_checks,
    ),
    Contract(
        name="dispensation",
        skills=("ea-dispensation",),
        scenario=DISPENSATION_SCENARIO,
        gate=("validate-gov",),
        checks=dispensation_checks,
    ),
    Contract(
        name="supersede",
        skills=("ea-adr",),
        scenario=SUPERSEDE_SCENARIO,
        gate=("validate-gov",),
        checks=supersede_checks,
    ),
)

CONTRACT_BY_NAME = {contract.name: contract for contract in CONTRACTS}


# ------------------------------------------------------------------------------- run


def repository_context(root: Path) -> str:
    """What an agent working in this repository would already have read."""
    parts = []
    for relative in ("standards", "governance-log/decisions", "governance-log/dispensations"):
        for path in sorted((root / relative).glob("*.yaml")):
            parts.append(f"=== {path.relative_to(root).as_posix()} ===\n{path.read_text(encoding='utf-8')}")
    from easkills import dsl

    model, _documents, _config = dsl.load(root, "approved")
    elements = "\n".join(
        f"  {element.id}  {element.type}  {element.name}"
        for element in sorted(model.elements.values(), key=lambda e: e.id)
    )
    return f"Approved model elements:\n{elements}\n\n" + "\n\n".join(parts)


def run_contract(client: Any, contract: Contract, model: str, workdir: Path) -> ContractResult:
    started = time.monotonic()
    usage = Usage()
    result = ContractResult(contract=contract.name, model=model)
    root = workdir / contract.name
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(FIXTURE, root)
    if contract.prepare:
        contract.prepare(root)
    transcript = root / "_harness-transcript.md"

    def record(label: str, text: str) -> None:
        with transcript.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\n\n## {label}\n\n{text}\n")

    try:
        session = Session(
            client,
            model,
            "\n\n".join([skill(name) for name in contract.skills] + [OUTPUT_CONTRACT]),
            usage,
        )
        reply = session.ask(
            contract.scenario.strip()
            + "\n\nToday is "
            + TODAY.isoformat()
            + ". Write only the file(s) the record needs; reply with every file you change "
            "in full, including any existing record you amend.\n\n"
            + repository_context(root)
        )
        record(contract.name, reply)
        files = extract_files(reply)
        if not files:
            raise ValueError("no parseable file in the reply")
        write_files(root, files)

        while result.repairs < MAX_REPAIRS:
            gate = list(contract.gate) + ["--root", str(root), "--as-of", TODAY.isoformat()]
            checked = easkills(*gate)
            result.gate = checked.returncode
            if checked.returncode == 0:
                break
            result.repairs += 1
            reply = session.ask(
                "The governance gate refused this. Repair it and reply with the corrected "
                "files in the same format.\n\n" + checked.stdout
            )
            record(f"{contract.name} repair {result.repairs}", reply)
            files = extract_files(reply)
            if not files:
                raise ValueError("no parseable file in the repair")
            write_files(root, files)
        result.checks = contract.checks(root)
        result.ok = result.gate == 0 and not result.failed
    except Exception as exc:  # noqa: BLE001 - a failed run is data, not a crash
        result.error = f"{type(exc).__name__}: {exc}"
    result.usage = usage.as_dict()
    result.seconds = round(time.monotonic() - started, 1)
    return result


def render(results: list[ContractResult]) -> str:
    lines = ["Governance contract harness", ""]
    for name in sorted({result.contract for result in results}):
        of_contract = [result for result in results if result.contract == name]
        held = sum(1 for result in of_contract if result.ok)
        lines.append(f"{name}: {held}/{len(of_contract)} run(s) held every contract")
        counts: dict[str, list[bool]] = {}
        for result in of_contract:
            for item in result.checks:
                counts.setdefault(item.name, []).append(item.passed)
            if result.error:
                lines.append(f"  failed: {result.error}")
        for label, values in counts.items():
            verdict = "ok" if all(values) else f"FAILED {values.count(False)}/{len(values)}"
            lines.append(f"  {label:<48} {verdict}")
        details = [
            f"  detail: {item.name}: {item.detail}"
            for result in of_contract
            for item in result.checks
            if not item.passed and item.detail
        ]
        lines += details
        lines.append(
            f"  repairs: {[result.repairs for result in of_contract]}  tokens in/out: "
            f"{sum(r.usage.get('inputTokens', 0) for r in of_contract)}/"
            f"{sum(r.usage.get('outputTokens', 0) for r in of_contract)}"
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contract checks for the governance skills")
    parser.add_argument("--contract", choices=sorted(CONTRACT_BY_NAME), help="one contract (default: all)")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, help="write the raw records here")
    parser.add_argument("--workdir", type=Path, help="scratch directory (kept for inspection)")
    args = parser.parse_args(argv)

    chosen = [CONTRACT_BY_NAME[args.contract]] if args.contract else list(CONTRACTS)
    client = api_client()
    workdir = args.workdir or Path(os.environ.get("TEMP", "/tmp")) / "ea-contracts"
    workdir.mkdir(parents=True, exist_ok=True)

    results: list[ContractResult] = []
    for contract in chosen:
        for index in range(args.runs):
            print(f"[{contract.name} {index + 1}/{args.runs}] running...", flush=True)
            result = run_contract(client, contract, args.model, workdir / f"run{index + 1}")
            verdict = "held" if result.ok else f"BROKE {result.failed or result.error}"
            print(f"[{contract.name} {index + 1}/{args.runs}] {verdict} in {result.seconds}s", flush=True)
            results.append(result)

    print()
    print(render(results))
    if args.out:
        args.out.write_text(
            json.dumps([result.as_dict() for result in results], indent=2, default=str) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
