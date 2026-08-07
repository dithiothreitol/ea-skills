"""Debt exposure, and what it costs when the operator has priced it.

The framing sentence, which the docs repeat verbatim because it *is* the feature:
**the tool computes the exposure, the operator priced it.** Nothing here invents a
number. Exposure is derived deterministically from the approved model and the
governance log -- element-days past the staleness threshold, dispensation-days open,
counts of end-of-life references, unrealized capabilities, surplus realizers. Turning
any of that into money requires unit rates in ``ea.config.yaml``; with none configured
this module still computes exposure, and `debt` prints exactly what it printed before.

Two honesty rules shape the output:

* **A total names what it left out.** An exposure with a quantity but no configured
  rate is listed as unpriced, next to the total, every time. A partial total that
  looks complete is worse than no total, because it is the number that reaches a
  slide.
* **What cannot be measured is not priced at zero.** An element that was never
  reviewed has no age, so it contributes no element-days -- and is named, so the
  reader knows the figure is short rather than assuming the backlog is clean.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from . import genschema

CONFIG_KEY = "costModel"


@dataclass(frozen=True)
class ExposureKind:
    """One measurable exposure and the rate key that prices it."""

    key: str
    unit: str  # "day" or "item" -- decides how the quantity reads in the report
    label: str
    basis: str  # the debt kind or rule family the quantity comes from


# Ordered as the report prints them: the two accruing exposures first (they grow while
# nothing is done, which is the point of pricing them), then the counted ones.
KINDS: tuple[ExposureKind, ...] = (
    ExposureKind(
        "staleElementDay",
        "day",
        "element-days past the staleness threshold",
        "stale-content",
    ),
    ExposureKind(
        "openDispensationDay",
        "day",
        "dispensation-days open since granted",
        "open dispensations (DISP)",
    ),
    ExposureKind(
        "eolElement",
        "item",
        "elements referencing a deprecated or retired standard",
        "dead-standard-reference",
    ),
    ExposureKind(
        "unsupportedCapability",
        "item",
        "capabilities nothing realizes",
        "unsupported-capability",
    ),
    ExposureKind(
        "duplicateRealization",
        "item",
        "realizers beyond the first on one capability",
        "rationalization-candidate",
    ),
)

BY_KEY = {kind.key: kind for kind in KINDS}


@dataclass
class Exposure:
    """One kind's measured quantity, with the items that produced it."""

    kind: ExposureKind
    quantity: int = 0
    items: list[dict[str, Any]] = field(default_factory=list)
    # Items that belong to this exposure but carry no measurable quantity. Never folded
    # into the total as zero: "we cannot tell" and "it costs nothing" are different
    # answers, and only one of them is honest.
    unmeasured: list[str] = field(default_factory=list)


def _days(value: str, today: date) -> int | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return max(0, (today - parsed).days)


def measure(
    model: Any,
    governance: Any,
    staleness_rows: list[dict[str, Any]],
    threshold: int,
    realizer_counts: dict[str, int],
    dead_standard_refs: list[tuple[str, str]],
    today: date,
) -> dict[str, Exposure]:
    """Derive every exposure quantity. Pure arithmetic over already-loaded state.

    Takes what `debt` has already computed rather than reloading the repository: the
    staleness rows, the realizer counts behind the rationalization query, and the
    (element, standard) pairs behind the end-of-life items. Two readers of the same
    facts that disagreed would be a defect nobody could see from the output.
    """
    result = {kind.key: Exposure(kind) for kind in KINDS}

    stale = result["staleElementDay"]
    for row in staleness_rows:
        if row["age"] is None:
            # Unreviewed, or a date the register could not parse. No age, no day count.
            stale.unmeasured.append(row["id"])
            continue
        over = row["age"] - threshold
        if over > 0:
            stale.quantity += over
            stale.items.append({"id": row["id"], "days": over})

    dispensations = result["openDispensationDay"]
    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        if not dispensation.is_open(today):
            continue
        open_days = _days(dispensation.granted, today)
        if open_days is None:
            dispensations.unmeasured.append(dispensation.id)
            continue
        dispensations.quantity += open_days
        dispensations.items.append({"id": dispensation.id, "days": open_days})

    eol = result["eolElement"]
    for element_id, standard_id in dead_standard_refs:
        eol.quantity += 1
        eol.items.append({"id": element_id, "standard": standard_id})

    realized = {
        r.target for r in model.relationships.values() if r.type == "Realization" and r.target in model.elements
    }
    unsupported = result["unsupportedCapability"]
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.type == "Capability" and element.id not in realized:
            unsupported.quantity += 1
            unsupported.items.append({"id": element.id})

    duplicates = result["duplicateRealization"]
    for capability_id, count in sorted(realizer_counts.items()):
        if count > 1:
            duplicates.quantity += count - 1
            duplicates.items.append({"id": capability_id, "surplus": count - 1})

    return result


def rates(config: dict[str, Any]) -> tuple[str, dict[str, Decimal], list[str]]:
    """Read ``costModel`` from the config. Returns ``(currency, rates, problems)``.

    Never raises and never guesses: an unusable rate is dropped and named, so the
    exposure it belongs to is reported as *unpriced* rather than quietly priced at
    whatever the value coerced to. The schema rejects unknown keys and negative
    numbers; this is the runtime half, because a report must survive a config the
    gate has already objected to.
    """
    raw = config.get(CONFIG_KEY)
    if not isinstance(raw, dict):
        return "", {}, []
    currency = str(raw.get("currency", "") or "").strip()
    problems: list[str] = []
    if not currency:
        problems.append("costModel.currency is missing -- amounts would carry no unit")
    parsed: dict[str, Decimal] = {}
    for key, value in sorted(raw.items()):
        if key == "currency":
            continue
        if key not in BY_KEY:
            problems.append(f"costModel.{key} is not a rate this tool knows how to apply")
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"costModel.{key}: expected a number, got {value!r}")
            continue
        # str() first: Decimal(0.1) is not 0.1, and money that does not add up is the
        # one arithmetic error nobody forgives in a board pack.
        rate = Decimal(str(value))
        if rate < 0:
            problems.append(f"costModel.{key}: a negative rate ({value}) cannot be a cost")
            continue
        parsed[key] = rate
    if not currency:
        return "", {}, problems
    return currency, parsed, problems


def price(exposures: dict[str, Exposure], config: dict[str, Any]) -> dict[str, Any] | None:
    """The costed view, or ``None`` when no usable cost model is configured.

    ``None`` is what keeps the promise that an unpriced repository sees byte-identical
    `debt` output: the caller omits the whole section rather than printing an empty one.
    """
    currency, rate_map, problems = rates(config)
    if not currency:
        return None

    lines: list[dict[str, Any]] = []
    total = Decimal(0)
    for kind in KINDS:
        exposure = exposures[kind.key]
        rate = rate_map.get(kind.key)
        line: dict[str, Any] = {
            "key": kind.key,
            "unit": kind.unit,
            "label": kind.label,
            "basis": kind.basis,
            "quantity": exposure.quantity,
            "unmeasured": list(exposure.unmeasured),
            "items": list(exposure.items),
        }
        if rate is None:
            line["rate"] = None
            line["cost"] = None
        else:
            amount = rate * exposure.quantity
            line["rate"] = str(rate)
            line["cost"] = str(amount)
            total += amount
        lines.append(line)

    # Only exposures that actually exist are worth naming as unpriced: "no rate for an
    # exposure of zero" is noise, and a list of five reads as a broken configuration.
    unpriced = [line["key"] for line in lines if line["rate"] is None and line["quantity"] > 0]
    unmeasured = sorted({item for line in lines for item in line["unmeasured"]})
    return {
        "currency": currency,
        "lines": lines,
        "total": str(total),
        "unpriced": unpriced,
        "unmeasured": unmeasured,
        "problems": problems,
        "complete": not unpriced and not unmeasured and not problems,
    }


def render(costed: dict[str, Any]) -> list[str]:
    """The cost section of the debt register, as lines. Callers own the surrounding
    blank lines, so this composes into `render_debt` without owning its layout."""
    from . import ui

    currency = costed["currency"]
    lines = [
        ui.bold(f"Cost of exposure ({currency})"),
        ui.dim("  the tool computed the exposure, the operator priced it"),
    ]
    # One column layout for the priced lines and the total, so the amounts stack. The
    # widths are literals rather than measured: a table whose columns move with the
    # data produces a whole-file diff every run, and these reports get diffed.
    for line in costed["lines"]:
        if line["quantity"] == 0 and line["rate"] is None:
            continue
        label = "{:<22}".format(line["key"])
        unit = line["unit"] + ("s" if line["quantity"] != 1 else "")
        quantity = "{:>12}".format(f"{line['quantity']:,} {unit}")
        if line["rate"] is None:
            tail = ui.yellow("no rate configured -- not priced")
        else:
            amount = "{:>14}".format(f"{Decimal(line['cost']):,.2f}")
            tail = f"x {'{:<10}'.format(line['rate'])} = {amount} {currency}"
        lines.append(f"  {ui.bold(label)} {quantity}  {tail}")
    total = "{:>14}".format(f"{Decimal(costed['total']):,.2f}")
    lines.append(f"  {ui.bold('{:<22}'.format('total'))} {'':>12}  {'':<12} = {ui.bold(total)} {currency}")

    # The total's own caveats, printed with it rather than in a footnote. A number that
    # travels into a slide travels alone; whatever qualifies it has to be adjacent.
    if costed["unpriced"]:
        lines.append(
            ui.yellow(f"  Not priced: {', '.join(costed['unpriced'])} -- a total is only as complete as its rates.")
        )
    if costed["unmeasured"]:
        shown = ", ".join(costed["unmeasured"][:5])
        more = f" (+{len(costed['unmeasured']) - 5} more)" if len(costed["unmeasured"]) > 5 else ""
        lines.append(
            ui.yellow(f"  Not measurable: {shown}{more} -- no review date, so these carry no element-days.")
        )
    for problem in costed["problems"]:
        lines.append(ui.red(f"  {problem}"))
    return lines


def documented_rate_keys() -> tuple[str, ...]:
    """The rate keys the schema accepts. One definition, read by the tests."""
    return tuple(key for key, _description in genschema.COST_RATE_KEYS)
