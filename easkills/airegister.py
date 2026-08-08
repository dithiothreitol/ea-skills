"""The EU AI Act system inventory, generated from the approved model (the AIR family).

**This is a generator, not an attestation.** The structure follows the concepts the AI
Act reasons in -- systems with a risk classification (Art. 5, Art. 6, Art. 50), the
operator role the organisation holds for each (Art. 3), the human-oversight arrangement
high risk demands (Art. 14), the upstream provider where the system is someone else's.
The *content* comes from the model and nowhere else; whether a system is correctly
classified, whether an Art. 49 registration is due, and whether oversight is adequate
are a lawyer's and an accountable human's judgements, not a report's. Every generated
document opens with that paragraph, because a document that looks like a compliance
record and is not one is worse than no document.

What makes this worth generating is the same section that justifies ``dora-register``:
**the inventory names its own gaps.** For every field the Act's questions want that the
model does not carry, the document lists the element ids missing it -- so its
completeness is tested rather than asserted, and the reader learns what it does not
know before trusting what it does.

Scope is the property ``regulatoryScope: ai-act`` on an element -- declared, never
inferred from a type or a name. An element can be in more than one register's scope
(``regulatoryScope: ai-act dora``); membership is read through the one shared splitter
in ``genschema`` so the two registers cannot disagree about what a value means.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import dsl, genschema, govern, ui
from .dora import CONTRACT_PROPERTY, FUNCTION_TYPES, MISSING, PROVIDER_PROPERTY, SUPPORTING, _rel
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

SCOPE_PROPERTY = "regulatoryScope"
SCOPE_AI_ACT = "ai-act"
RISK_PROPERTY = "aiRiskClass"
ROLE_PROPERTY = "aiRole"
OVERSIGHT_PROPERTY = "aiOversight"

PROHIBITED = "prohibited"
HIGH = "high"
LIMITED = "limited"
# Risk in descending order: a provider's entry takes the highest risk of anything it
# supplies, which is the only safe direction to round.
RISK_ORDER = (PROHIBITED, HIGH, LIMITED, "minimal")

# Roles that imply an upstream provider: someone else made the system, so the register
# wants to know who. A 'provider'-role system is this organisation's own product.
SOURCED_ROLES = frozenset({"deployer", "importer", "distributor"})


class AiActError(Exception):
    """Raised for a request the inventory cannot honour at all."""


@dataclass
class Entry:
    """One in-scope AI system, as the inventory sees it."""

    id: str
    name: str
    type: str
    risk: str = ""
    role: str = ""
    oversight: str = ""
    provider: str = ""
    contract: str = ""
    functions: list[str] = field(default_factory=list)
    dispensations: list[str] = field(default_factory=list)
    file: str = ""
    locator: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "aiRiskClass": self.risk,
            "aiRole": self.role,
            "aiOversight": self.oversight,
            "provider": self.provider,
            "contractRef": self.contract,
            "functions": list(self.functions),
            "dispensations": list(self.dispensations),
        }


@dataclass
class Register:
    root: Path
    as_of: str
    entries: list[Entry] = field(default_factory=list)
    providers: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    waivers: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def in_scope(self) -> bool:
        return bool(self.entries)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_INFO]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "asOf": self.as_of,
            "inScope": len(self.entries),
            "ok": self.ok,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": len(self.infos),
            },
            "entries": [entry.as_dict() for entry in self.entries],
            "providers": self.providers,
            "functions": self.functions,
            "waivers": self.waivers,
            "gaps": self.gaps,
            "findings": [f.as_dict() for f in self.findings],
        }


def _rank(risk: str) -> int:
    try:
        return RISK_ORDER.index(risk)
    except ValueError:
        return len(RISK_ORDER)


def build(root: Path, today: date | None = None) -> Register:
    """Derive the inventory. Deterministic given the approved model and ``today``."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    register = Register(root=root, as_of=today.isoformat())

    entries: list[Entry] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if SCOPE_AI_ACT not in genschema.split_regulatory_scopes(element.properties.get(SCOPE_PROPERTY)):
            continue
        entries.append(
            Entry(
                id=element.id,
                name=element.name,
                type=element.type,
                risk=str(element.properties.get(RISK_PROPERTY, "") or ""),
                role=str(element.properties.get(ROLE_PROPERTY, "") or ""),
                oversight=str(element.properties.get(OVERSIGHT_PROPERTY, "") or ""),
                provider=str(element.properties.get(PROVIDER_PROPERTY, "") or ""),
                contract=str(element.properties.get(CONTRACT_PROPERTY, "") or ""),
                file=_rel(root, element.source_path),
                locator=element.locator,
            )
        )
    register.entries = entries
    if not entries:
        # Nothing in scope is not an empty inventory -- it is *no* inventory. An empty
        # page that looks like a compliance record is the worst output this command
        # could produce.
        return register

    scoped = {entry.id: entry for entry in entries}
    _attach_functions(model, scoped)
    _attach_waivers(governance, scoped, today)

    register.providers = _providers(entries)
    register.functions = _functions(model, entries)
    register.waivers = _waivers(governance, entries, today)
    register.gaps = _gaps(entries)
    register.findings = _findings(entries, register)
    return register


def _attach_functions(model: dsl.Model, scoped: dict[str, Entry]) -> None:
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if relationship.type not in SUPPORTING:
            continue
        entry = scoped.get(relationship.source)
        target = model.elements.get(relationship.target)
        if entry is None or target is None or target.type not in FUNCTION_TYPES:
            continue
        if target.id not in entry.functions:
            entry.functions.append(target.id)
    for entry in scoped.values():
        entry.functions.sort()


def _attach_waivers(governance: Any, scoped: dict[str, Entry], today: date) -> None:
    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        if not dispensation.is_open(today):
            continue
        for element_id in dispensation.applies_to:
            entry = scoped.get(element_id)
            if entry is not None and dispensation.id not in entry.dispensations:
                entry.dispensations.append(dispensation.id)


def _providers(entries: list[Entry]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not entry.provider:
            continue
        row = grouped.setdefault(
            entry.provider, {"provider": entry.provider, "elements": [], "contracts": [], "risk": ""}
        )
        row["elements"].append(entry.id)
        if entry.contract and entry.contract not in row["contracts"]:
            row["contracts"].append(entry.contract)
        # Highest risk wins: a provider supplying one high-risk system is a high-risk
        # provider, whatever else it also supplies.
        if _rank(entry.risk) < _rank(row["risk"]):
            row["risk"] = entry.risk
    for row in grouped.values():
        row["elements"].sort()
        row["contracts"].sort()
    return [grouped[key] for key in sorted(grouped)]


def _functions(model: dsl.Model, entries: list[Entry]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        for function_id in entry.functions:
            function = model.elements.get(function_id)
            row = grouped.setdefault(
                function_id,
                {
                    "id": function_id,
                    "name": function.name if function else function_id,
                    "type": function.type if function else "",
                    "supportedBy": [],
                    "risk": "",
                },
            )
            row["supportedBy"].append(entry.id)
            if _rank(entry.risk) < _rank(row["risk"]):
                row["risk"] = entry.risk
    for row in grouped.values():
        row["supportedBy"].sort()
    return [grouped[key] for key in sorted(grouped)]


def _waivers(governance: Any, entries: list[Entry], today: date) -> list[dict[str, Any]]:
    by_element = {entry.id: entry for entry in entries}
    rows: list[dict[str, Any]] = []
    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        if not dispensation.is_open(today):
            continue
        affected = sorted(e for e in dispensation.applies_to if e in by_element)
        if not affected:
            continue
        rows.append(
            {
                "id": dispensation.id,
                "waives": dispensation.waives_standard or dispensation.waives_rule,
                "expires": dispensation.expires,
                "elements": affected,
                "risk": min((by_element[e].risk for e in affected), key=_rank),
            }
        )
    return rows


def _gaps(entries: list[Entry]) -> list[dict[str, Any]]:
    """What the Act's questions want that the model does not carry, per field.

    Same contract as the DORA register's gap section: a document that quietly omitted
    the fields it could not fill would be indistinguishable from a complete one.
    Oversight is asked of high-risk systems only (Art. 14 attaches there), and a
    provider is asked only of systems someone else made -- a gap list padded with
    fields the Act does not want for that row would train people to ignore it.
    """
    gaps: list[dict[str, Any]] = []
    wanted = (
        (RISK_PROPERTY, "the risk classification the Act's obligations attach to", entries, lambda e: e.risk),
        (ROLE_PROPERTY, "the operator role this organisation holds (Art. 3)", entries, lambda e: e.role),
        (
            OVERSIGHT_PROPERTY,
            "the human-oversight arrangement for a high-risk system (Art. 14)",
            [e for e in entries if e.risk == HIGH],
            lambda e: e.oversight,
        ),
        (
            PROVIDER_PROPERTY,
            "the upstream provider of a system this organisation deploys but did not make",
            [e for e in entries if e.role in SOURCED_ROLES],
            lambda e: e.provider,
        ),
    )
    for field_name, wants, population, value in wanted:
        missing = sorted(entry.id for entry in population if not value(entry))
        if missing:
            gaps.append({"field": field_name, "wants": wants, "elements": missing})
    no_function = sorted(entry.id for entry in entries if not entry.functions)
    if no_function:
        gaps.append(
            {
                "field": "functions supported",
                "wants": "the business function(s) this AI system serves",
                "elements": no_function,
            }
        )
    return gaps


def _findings(entries: list[Entry], register: Register) -> list[Finding]:
    findings: list[Finding] = []
    for entry in entries:
        if not entry.risk:
            findings.append(
                Finding(
                    "AIR001",
                    SEVERITY_WARNING,
                    f"in scope for the AI Act but carries no '{RISK_PROPERTY}' -- the inventory "
                    "cannot say which obligations attach",
                    file=entry.file,
                    locator=entry.locator,
                    concept=entry.id,
                )
            )
        if entry.risk == HIGH:
            absent = [
                name
                for name, value in ((ROLE_PROPERTY, entry.role), (OVERSIGHT_PROPERTY, entry.oversight))
                if not value
            ]
            if absent:
                findings.append(
                    Finding(
                        "AIR002",
                        SEVERITY_ERROR,
                        f"high-risk, but the inventory has no {' and no '.join(absent)} for it -- "
                        "the obligations differ by role, and Art. 14 asks who oversees the system",
                        file=entry.file,
                        locator=entry.locator,
                        concept=entry.id,
                    )
                )
        if entry.risk == PROHIBITED:
            findings.append(
                Finding(
                    "AIR005",
                    SEVERITY_ERROR,
                    "classified as a prohibited AI practice (Art. 5) in the approved model -- "
                    "not a row to file but a decision the board must see: retire the practice "
                    "or correct the classification, and record whichever happened",
                    file=entry.file,
                    locator=entry.locator,
                    concept=entry.id,
                )
            )
        for dispensation_id in entry.dispensations:
            if entry.risk not in {HIGH, LIMITED}:
                continue
            findings.append(
                Finding(
                    "AIR003",
                    SEVERITY_INFO,
                    f"{entry.risk}-risk and covered by open dispensation '{dispensation_id}' -- "
                    "accepted AI risk to disclose, not a violation to fix",
                    file=entry.file,
                    locator=entry.locator,
                    concept=entry.id,
                )
            )

    # AIR004: a section the inventory expects, empty while there is in-scope content to
    # fill it. The provider section is only expected once some in-scope system was made
    # by someone else -- an estate that builds everything it runs legitimately has no
    # third-party AI providers, and warning about that would train people to ignore
    # the code.
    expected_sections = [("functions supported", register.functions)]
    if any(entry.role in SOURCED_ROLES for entry in entries):
        expected_sections.append(("third-party AI providers", register.providers))
    for section, rows in sorted(expected_sections):
        if not rows:
            findings.append(
                Finding(
                    "AIR004",
                    SEVERITY_WARNING,
                    f"the '{section}' section is empty while {len(entries)} system(s) are in scope -- "
                    "an empty section reads as 'nothing to report'",
                    # No file: the defect is the inventory's, spread across every in-scope
                    # element rather than living in one of them.
                    locator=section,
                )
            )
    findings.sort(key=lambda f: (f.code, f.concept, f.locator, f.message))
    return findings


# --------------------------------------------------------------------------- output


HEADER_NOTICE = (
    "**This document is generated, and it is not a compliance record.** Its structure "
    "follows the concepts the EU AI Act reasons in -- risk classes, the Art. 3 operator "
    "roles, Art. 14 human oversight; its content comes from this repository's approved "
    "architecture model and from nowhere else. No legal review has taken place here, no "
    "completeness against the Act's registration or documentation duties is claimed, and "
    "nothing below has been checked against the systems it names. Whether a system is "
    "correctly classified and its obligations met is a decision for the people "
    "accountable for it. What this document does do is state, in its last section, "
    "exactly which fields the model could not fill -- read that section first."
)


def markdown(register: Register) -> str:
    """The inventory as a document. Deterministic; ``--as-of`` fixes every date in it."""
    if not register.in_scope:
        raise AiActError(
            f"no element carries '{SCOPE_PROPERTY}: {SCOPE_AI_ACT}' in {register.root} -- "
            "nothing to inventory. Tag the AI systems in scope first; an empty inventory "
            "is not a smaller inventory, it is a document that says nothing while looking "
            "like a compliance record."
        )
    lines = [
        "# AI system inventory (EU AI Act)",
        "",
        f"*Generated by `ea-skills` from the approved model, as of {register.as_of}.*",
        "",
        HEADER_NOTICE,
        "",
        f"In scope: **{len(register.entries)}** AI system(s) carrying "
        f"`{SCOPE_PROPERTY}: {SCOPE_AI_ACT}`.",
        "",
        "## AI systems in scope",
        "",
    ]
    lines += _table(
        ("Element", "Name", "Risk class", "Role", "Oversight", "Provider", "Contract"),
        [
            (
                entry.id,
                entry.name,
                entry.risk or MISSING,
                entry.role or MISSING,
                entry.oversight or MISSING,
                entry.provider or MISSING,
                entry.contract or MISSING,
            )
            for entry in register.entries
        ],
    )
    lines += ["", "## Third-party AI providers", ""]
    lines += _table(
        ("Provider", "Highest risk", "Contract(s)", "Systems"),
        [
            (
                row["provider"],
                row["risk"] or MISSING,
                ", ".join(row["contracts"]) or MISSING,
                ", ".join(row["elements"]),
            )
            for row in register.providers
        ],
    )
    lines += ["", "## Functions supported", ""]
    lines += _table(
        ("Function", "Name", "Highest risk", "Supported by"),
        [
            (
                row["id"],
                row["name"],
                row["risk"] or MISSING,
                ", ".join(row["supportedBy"]),
            )
            for row in register.functions
        ],
    )
    lines += ["", "## Open dispensations affecting in-scope systems", ""]
    if register.waivers:
        lines += [
            "A waiver on a high-risk or transparency-risk system is a register event, not "
            "an internal note: it is accepted AI risk that exists on the date this "
            "document is read.",
            "",
        ]
    lines += _table(
        ("Dispensation", "Waives", "Expires", "Risk", "Systems"),
        [
            (
                row["id"],
                row["waives"] or MISSING,
                row["expires"] or MISSING,
                row["risk"] or MISSING,
                ", ".join(row["elements"]),
            )
            for row in register.waivers
        ],
    )
    lines += ["", "## What this inventory could not fill", ""]
    if not register.gaps:
        lines += ["Every field this document asks of the model is present for every system in scope."]
    else:
        lines += [
            "Each row is a field the inventory wants and the model does not carry, with "
            "the systems missing it. These are the gaps to close before anyone treats "
            "this document as complete.",
            "",
        ]
        lines += _table(
            ("Field", "What it is", "Missing on"),
            [(gap["field"], gap["wants"], ", ".join(gap["elements"])) for gap in register.gaps],
        )
    lines += ["", "---", "", f"Findings: {len(register.errors)} error(s), {len(register.warnings)} warning(s), "
              f"{len(register.infos)} info. Run `python -m easkills ai-act-register --strict` to gate on them."]
    return "\n".join(lines) + "\n"


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    if not rows:
        return ["*Nothing recorded. See “What this inventory could not fill” below.*"]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_escape(cell) for cell in row) + " |")
    return out


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(register: Register) -> str:
    """The terminal view: the findings and the shape, not the document."""
    lines = [
        ui.bold(f"EU AI Act system inventory -- as of {register.as_of} at {register.root}"),
    ]
    if not register.in_scope:
        lines += [
            "",
            ui.dim(
                f"No element carries '{SCOPE_PROPERTY}: {SCOPE_AI_ACT}'. Nothing is in scope, so no "
                "inventory is generated -- which is the correct output for an organisation "
                "running no AI systems the Act reaches, and the wrong one for an organisation "
                "that has not tagged its AI systems yet."
            ),
            "",
            ui.verdict(True, 0, 0),
        ]
        return "\n".join(lines)
    lines += [
        ui.dim(
            f"{len(register.entries)} system(s) in scope; "
            f"{len(register.providers)} provider(s), {len(register.functions)} function(s), "
            f"{len(register.waivers)} open waiver(s)"
        ),
        "",
    ]
    for finding in register.findings:
        lines.append(finding.render())
    if register.findings:
        lines.append("")
    if register.gaps:
        lines.append(ui.bold("Fields the model does not carry"))
        for gap in register.gaps:
            lines.append(
                f"  {ui.yellow('{:<20}'.format(gap['field']))} {ui.dim('missing on: ' + ', '.join(gap['elements']))}"
            )
        lines.append("")
    lines += [
        ui.dim(
            "A generator, not an attestation: the structure follows the Act's concepts, "
            "the content comes from the model, and the legal judgement is a human's."
        ),
        "",
        ui.verdict(register.ok, len(register.errors), len(register.warnings)),
    ]
    return "\n".join(lines)


def documented_vocabulary() -> dict[str, tuple[str, ...]]:
    """The enums this module reads, from the schema's single definition."""
    return {
        SCOPE_PROPERTY: genschema.REGULATORY_SCOPES,
        RISK_PROPERTY: genschema.AI_RISK_CLASSES,
        ROLE_PROPERTY: genschema.AI_ROLES,
    }
