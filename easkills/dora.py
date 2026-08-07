"""The DORA Register of Information, generated from the approved model (the REG family).

**This is a generator, not an attestation.** The structure follows the shape the ESAs'
implementing technical standards ask for -- ICT third-party service providers, the
contractual arrangements with them, the criticality of what they support, the functions
that depend on them. The *content* comes from the model and nowhere else, and whether a
filing is complete and correct is a lawyer's judgement, not a report's. Every generated
document opens with that paragraph, because a document that looks like a filing and is
not one is worse than no document.

What makes this worth generating at all is the last section: **the register names its own
gaps.** For every field the template wants that the model does not carry, the document
lists the element ids that are missing it. That is the first regulatory output in this
repository whose completeness is *tested* rather than asserted -- and it is the reason
the register is safe to hand to somebody: it tells them what it does not know.

Scope is the property ``regulatoryScope: dora`` on an element. A property rather than a
config list, because scope is a fact about an element that belongs next to it, is
greppable, moves with the element when it moves, and shows up in the diff of the commit
that changed it. A list in ``ea.config.yaml`` would be a second place to forget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import dsl, genschema, govern, ui
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

SCOPE_PROPERTY = "regulatoryScope"
SCOPE_DORA = "dora"
CRITICALITY_PROPERTY = "doraCriticality"
PROVIDER_PROPERTY = "provider"
CONTRACT_PROPERTY = "contractRef"

CRITICAL = "critical"
IMPORTANT = "important"
# Criticality in descending order: a provider's entry takes the highest criticality of
# anything it supports, which is the only safe direction to round.
CRITICALITY_ORDER = (CRITICAL, IMPORTANT, "standard")

# What counts as a "function" an in-scope element supports. Capability is included
# deliberately: DORA asks which business functions depend on an ICT service, and in an
# ArchiMate model that dependency is as often drawn to the capability as to the process.
FUNCTION_TYPES = frozenset({"BusinessProcess", "BusinessFunction", "BusinessService", "Capability"})

# Relationship types by which an ICT element supports a function.
SUPPORTING = frozenset({"Serving", "Realization", "Assignment"})

MISSING = "not recorded"


class DoraError(Exception):
    """Raised for a request the register cannot honour at all."""


@dataclass
class Entry:
    """One in-scope element, as the register sees it."""

    id: str
    name: str
    type: str
    criticality: str = ""
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
            "criticality": self.criticality,
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
    contracts: list[dict[str, Any]] = field(default_factory=list)
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
            "contracts": self.contracts,
            "functions": self.functions,
            "waivers": self.waivers,
            "gaps": self.gaps,
            "findings": [f.as_dict() for f in self.findings],
        }


def _rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _rank(criticality: str) -> int:
    try:
        return CRITICALITY_ORDER.index(criticality)
    except ValueError:
        return len(CRITICALITY_ORDER)


def build(root: Path, today: date | None = None) -> Register:
    """Derive the register. Deterministic given the approved model and ``today``."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    register = Register(root=root, as_of=today.isoformat())

    entries: list[Entry] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.properties.get(SCOPE_PROPERTY) != SCOPE_DORA:
            continue
        entries.append(
            Entry(
                id=element.id,
                name=element.name,
                type=element.type,
                criticality=str(element.properties.get(CRITICALITY_PROPERTY, "") or ""),
                provider=str(element.properties.get(PROVIDER_PROPERTY, "") or ""),
                contract=str(element.properties.get(CONTRACT_PROPERTY, "") or ""),
                file=_rel(root, element.source_path),
                locator=element.locator,
            )
        )
    register.entries = entries
    if not entries:
        # Nothing in scope is not an empty register -- it is *no* register. Producing an
        # empty document here would be the worst output this command could have: a page
        # that looks like a filing and says nothing.
        return register

    scoped = {entry.id: entry for entry in entries}
    _attach_functions(model, scoped)
    _attach_waivers(governance, scoped, today)

    register.providers = _providers(entries)
    register.contracts = _contracts(entries)
    register.functions = _functions(model, entries)
    register.waivers = _waivers(governance, entries, today)
    register.gaps = _gaps(entries)
    register.findings = _findings(root, model, entries, register)
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
            entry.provider, {"provider": entry.provider, "elements": [], "contracts": [], "criticality": ""}
        )
        row["elements"].append(entry.id)
        if entry.contract and entry.contract not in row["contracts"]:
            row["contracts"].append(entry.contract)
        # Highest criticality wins: a provider supporting one critical service is a
        # critical provider, whatever else it also runs.
        if _rank(entry.criticality) < _rank(row["criticality"]):
            row["criticality"] = entry.criticality
    for row in grouped.values():
        row["elements"].sort()
        row["contracts"].sort()
    return [grouped[key] for key in sorted(grouped)]


def _contracts(entries: list[Entry]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not entry.contract:
            continue
        row = grouped.setdefault(
            entry.contract, {"contractRef": entry.contract, "provider": "", "elements": [], "criticality": ""}
        )
        row["elements"].append(entry.id)
        if entry.provider and not row["provider"]:
            row["provider"] = entry.provider
        if _rank(entry.criticality) < _rank(row["criticality"]):
            row["criticality"] = entry.criticality
    for row in grouped.values():
        row["elements"].sort()
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
                    "criticality": "",
                    "providers": [],
                },
            )
            row["supportedBy"].append(entry.id)
            if entry.provider and entry.provider not in row["providers"]:
                row["providers"].append(entry.provider)
            if _rank(entry.criticality) < _rank(row["criticality"]):
                row["criticality"] = entry.criticality
    for row in grouped.values():
        row["supportedBy"].sort()
        row["providers"].sort()
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
                "criticality": min((by_element[e].criticality for e in affected), key=_rank),
            }
        )
    return rows


def _gaps(entries: list[Entry]) -> list[dict[str, Any]]:
    """What the template asks for that the model does not carry, per field.

    This section is the point of the whole command. A register that quietly omitted the
    fields it could not fill would be indistinguishable from a complete one, and the
    person filing it would find out from a supervisor rather than from us.
    """
    wanted = (
        (CRITICALITY_PROPERTY, "criticality of the function this element supports"),
        (PROVIDER_PROPERTY, "ICT third-party service provider"),
        (CONTRACT_PROPERTY, "reference to the contractual arrangement"),
    )
    values = {
        CRITICALITY_PROPERTY: lambda e: e.criticality,
        PROVIDER_PROPERTY: lambda e: e.provider,
        CONTRACT_PROPERTY: lambda e: e.contract,
    }
    gaps: list[dict[str, Any]] = []
    for field_name, wants in wanted:
        missing = sorted(entry.id for entry in entries if not values[field_name](entry))
        if missing:
            gaps.append({"field": field_name, "wants": wants, "elements": missing})
    no_function = sorted(entry.id for entry in entries if not entry.functions)
    if no_function:
        gaps.append(
            {
                "field": "functions supported",
                "wants": "the business function(s) depending on this ICT service",
                "elements": no_function,
            }
        )
    return gaps


def _findings(root: Path, model: dsl.Model, entries: list[Entry], register: Register) -> list[Finding]:
    findings: list[Finding] = []
    for entry in entries:
        if not entry.criticality:
            findings.append(
                Finding(
                    "REG001",
                    SEVERITY_WARNING,
                    f"in scope for DORA but carries no '{CRITICALITY_PROPERTY}' -- the register "
                    "cannot say how much depends on it",
                    file=entry.file,
                    locator=entry.locator,
                    concept=entry.id,
                )
            )
        if entry.criticality == CRITICAL:
            absent = [
                name
                for name, value in ((PROVIDER_PROPERTY, entry.provider), (CONTRACT_PROPERTY, entry.contract))
                if not value
            ]
            if absent:
                findings.append(
                    Finding(
                        "REG002",
                        SEVERITY_ERROR,
                        f"critical, but the register has no {' and no '.join(absent)} for it -- "
                        "these are the fields a supervisor asks for first",
                        file=entry.file,
                        locator=entry.locator,
                        concept=entry.id,
                    )
                )
        for dispensation_id in entry.dispensations:
            if entry.criticality not in {CRITICAL, IMPORTANT}:
                continue
            findings.append(
                Finding(
                    "REG003",
                    SEVERITY_INFO,
                    f"{entry.criticality} and covered by open dispensation '{dispensation_id}' -- "
                    "exposure to disclose, not a violation to fix",
                    file=entry.file,
                    locator=entry.locator,
                    concept=entry.id,
                )
            )

    # REG004: a section the template expects, empty while there is in-scope content to
    # fill it. Silence in a register reads as "nothing to report", which is a different
    # statement from "we did not record it".
    for section, rows in (
        ("ICT third-party service providers", register.providers),
        ("contractual arrangements", register.contracts),
        ("functions supported", register.functions),
    ):
        if not rows:
            findings.append(
                Finding(
                    "REG004",
                    SEVERITY_WARNING,
                    f"the '{section}' section is empty while {len(entries)} element(s) are in scope -- "
                    "an empty section reads as 'nothing to report'",
                    # No file: the defect is the register's, spread across every in-scope
                    # element rather than living in one of them. Pointing at an arbitrary
                    # file would send the reader to a page with nothing wrong on it.
                    locator=section,
                )
            )
    findings.sort(key=lambda f: (f.code, f.concept, f.locator, f.message))
    return findings


# --------------------------------------------------------------------------- output


HEADER_NOTICE = (
    "**This document is generated, and it is not a filing.** Its structure follows the "
    "shape the ESAs' implementing technical standards ask a Register of Information to "
    "have; its content comes from this repository's approved architecture model and from "
    "nowhere else. No legal review has taken place here, no completeness against the "
    "official templates is claimed, and nothing below has been checked against the "
    "contracts it names. Whether a register satisfies DORA is a decision for the people "
    "accountable for the filing. What this document does do is state, in its last "
    "section, exactly which fields the model could not fill -- read that section first."
)


def markdown(register: Register) -> str:
    """The register as a document. Deterministic; ``--as-of`` fixes every date in it."""
    if not register.in_scope:
        raise DoraError(
            f"no element carries '{SCOPE_PROPERTY}: {SCOPE_DORA}' in {register.root} -- "
            "nothing to register. Tag the ICT services in scope first; an empty register "
            "is not a smaller register, it is a document that says nothing while looking "
            "like a filing."
        )
    lines = [
        "# Register of Information (DORA)",
        "",
        f"*Generated by `ea-skills` from the approved model, as of {register.as_of}.*",
        "",
        HEADER_NOTICE,
        "",
        f"In scope: **{len(register.entries)}** ICT element(s) carrying "
        f"`{SCOPE_PROPERTY}: {SCOPE_DORA}`.",
        "",
        "## ICT third-party service providers",
        "",
    ]
    lines += _table(
        ("Provider", "Highest criticality", "Contract(s)", "Elements"),
        [
            (
                row["provider"],
                row["criticality"] or MISSING,
                ", ".join(row["contracts"]) or MISSING,
                ", ".join(row["elements"]),
            )
            for row in register.providers
        ],
    )
    lines += ["", "## Contractual arrangements", ""]
    lines += _table(
        ("Contract", "Provider", "Criticality", "Elements"),
        [
            (
                row["contractRef"],
                row["provider"] or MISSING,
                row["criticality"] or MISSING,
                ", ".join(row["elements"]),
            )
            for row in register.contracts
        ],
    )
    lines += ["", "## ICT services in scope", ""]
    lines += _table(
        ("Element", "Name", "Type", "Criticality", "Provider", "Contract"),
        [
            (
                entry.id,
                entry.name,
                entry.type,
                entry.criticality or MISSING,
                entry.provider or MISSING,
                entry.contract or MISSING,
            )
            for entry in register.entries
        ],
    )
    lines += ["", "## Functions supported", ""]
    lines += _table(
        ("Function", "Name", "Criticality", "Supported by", "Provider(s)"),
        [
            (
                row["id"],
                row["name"],
                row["criticality"] or MISSING,
                ", ".join(row["supportedBy"]),
                ", ".join(row["providers"]) or MISSING,
            )
            for row in register.functions
        ],
    )
    lines += ["", "## Open dispensations affecting in-scope elements", ""]
    if register.waivers:
        lines += [
            "A waiver on an element supporting a critical function is a register event, not "
            "an internal note: it is exposure that exists on the date this document is read.",
            "",
        ]
    lines += _table(
        ("Dispensation", "Waives", "Expires", "Criticality", "Elements"),
        [
            (
                row["id"],
                row["waives"] or MISSING,
                row["expires"] or MISSING,
                row["criticality"] or MISSING,
                ", ".join(row["elements"]),
            )
            for row in register.waivers
        ],
    )
    lines += ["", "## What this register could not fill", ""]
    if not register.gaps:
        lines += ["Every field this document asks of the model is present for every element in scope."]
    else:
        lines += [
            "Each row is a field the register wants and the model does not carry, with the "
            "elements missing it. These are the gaps to close before anyone treats this "
            "document as complete.",
            "",
        ]
        lines += _table(
            ("Field", "What it is", "Missing on"),
            [(gap["field"], gap["wants"], ", ".join(gap["elements"])) for gap in register.gaps],
        )
    lines += ["", "---", "", f"Findings: {len(register.errors)} error(s), {len(register.warnings)} warning(s), "
              f"{len(register.infos)} info. Run `python -m easkills dora-register --strict` to gate on them."]
    return "\n".join(lines) + "\n"


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    if not rows:
        return ["*Nothing recorded. See “What this register could not fill” below.*"]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_escape(cell) for cell in row) + " |")
    return out


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(register: Register) -> str:
    """The terminal view: the findings and the shape, not the document."""
    lines = [
        ui.bold(f"DORA Register of Information -- as of {register.as_of} at {register.root}"),
    ]
    if not register.in_scope:
        lines += [
            "",
            ui.dim(
                f"No element carries '{SCOPE_PROPERTY}: {SCOPE_DORA}'. Nothing is in scope, so no "
                "register is generated -- which is the correct output for an organisation DORA "
                "does not apply to, and the wrong one for an organisation that has not tagged "
                "its ICT services yet."
            ),
            "",
            ui.verdict(True, 0, 0),
        ]
        return "\n".join(lines)
    lines += [
        ui.dim(
            f"{len(register.entries)} element(s) in scope; "
            f"{len(register.providers)} provider(s), {len(register.contracts)} contract(s), "
            f"{len(register.functions)} function(s), {len(register.waivers)} open waiver(s)"
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
            "A generator, not an attestation: the structure follows the ITS template shape, "
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
        CRITICALITY_PROPERTY: genschema.CRITICALITIES,
    }
