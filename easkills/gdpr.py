"""The GDPR Art. 30 record of processing activities, generated from the model (GDR family).

The third register, on the pattern the first two set (D7): scope is a property on the
element (`regulatoryScope` including `gdpr`), the generated document says in its own header
that it is not a compliance record, its last section names every field the model could not
fill with the element ids missing it, and with nothing in scope no document is produced.

What the record holds per processing activity follows Art. 30(1): the purposes, the
categories of data subjects and of personal data, the categories of recipients, transfers
to third countries, the envisaged time limits for erasure, and a general description of the
technical and organisational security measures. The lawful basis (Art. 6) is commonly kept
alongside and is recorded here too. Two things the model never carries, and the document
says so rather than leaving a blank that reads as "none": the controller's own name and
contact details (Art. 30(1)(a)), which belong to the organisation and not to a system, and
the Art. 9(2) condition that permits processing special-category data.

The **security measures column is derived, not written**: the obligations that bind the
element and the standards it claims -- the one definition of "governed" Phase 8.3 gave the
security rules. A processing activity nothing governs is `GDR004`, because an empty
measures column in a record of processing is a statement about the organisation, not about
the record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import dsl, genschema, govern, i18n, security, ui
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

SCOPE_PROPERTY = "regulatoryScope"
SCOPE_GDPR = "gdpr"
PURPOSE = "gdprPurpose"
BASIS = "gdprLawfulBasis"
SUBJECTS = "gdprDataSubjects"
CATEGORIES = "gdprDataCategories"
RECIPIENTS = "gdprRecipients"
TRANSFER = "gdprTransfer"
RETENTION = "gdprRetention"
PERSONAL = "personalData"
SPECIAL = "special-category"


class GdprError(Exception):
    """Raised for a request the record cannot honour at all."""


@dataclass
class Entry:
    id: str
    name: str
    type: str
    personal: str = ""
    purpose: str = ""
    basis: str = ""
    subjects: str = ""
    categories: str = ""
    recipients: str = ""
    transfer: str = ""
    retention: str = ""
    obligations: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    dispensations: list[str] = field(default_factory=list)
    file: str = ""
    locator: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "personalData": self.personal,
            "purpose": self.purpose,
            "lawfulBasis": self.basis,
            "dataSubjects": self.subjects,
            "dataCategories": self.categories,
            "recipients": self.recipients,
            "transfer": self.transfer,
            "retention": self.retention,
            "obligations": self.obligations,
            "standards": self.standards,
            "dispensations": self.dispensations,
        }


@dataclass
class Register:
    root: Path
    as_of: str
    entries: list[Entry] = field(default_factory=list)
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
            "summary": {"errors": len(self.errors), "warnings": len(self.warnings), "info": len(self.infos)},
            "entries": [entry.as_dict() for entry in self.entries],
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


def build(root: Path, today: date | None = None) -> Register:
    """Derive the record. Deterministic given the approved model and ``today``."""
    today = today or date.today()
    model, _documents, _config = dsl.load(root, "approved")
    governance = govern.load(root)
    register = Register(root=root, as_of=today.isoformat())
    bound = security.obligations(model)
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if SCOPE_GDPR not in genschema.split_regulatory_scopes(element.properties.get(SCOPE_PROPERTY)):
            continue
        p = element.properties
        register.entries.append(
            Entry(
                id=element.id,
                name=element.name,
                type=element.type,
                personal=str(p.get(PERSONAL, "") or ""),
                purpose=str(p.get(PURPOSE, "") or ""),
                basis=str(p.get(BASIS, "") or ""),
                subjects=str(p.get(SUBJECTS, "") or ""),
                categories=str(p.get(CATEGORIES, "") or ""),
                recipients=str(p.get(RECIPIENTS, "") or ""),
                transfer=str(p.get(TRANSFER, "") or ""),
                retention=str(p.get(RETENTION, "") or ""),
                obligations=sorted(bound.get(element.id, [])),
                standards=sorted(element.standards),
                file=_rel(root, element.source_path),
                locator=element.locator,
            )
        )
    if not register.entries:
        return register
    scoped = {entry.id: entry for entry in register.entries}
    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        if not dispensation.is_open(today):
            continue
        affected = sorted(e for e in dispensation.applies_to if e in scoped)
        for element_id in affected:
            scoped[element_id].dispensations.append(dispensation.id)
        if affected:
            register.waivers.append(
                {
                    "id": dispensation.id,
                    "waives": dispensation.waives_standard or dispensation.waives_rule,
                    "expires": dispensation.expires,
                    "elements": affected,
                }
            )
    register.gaps = _gaps(register.entries)
    register.findings = _findings(register.entries)
    return register


# Each field the record asks for, the element value it reads, and which elements it is
# asked of. The Art. 9(2) condition is asked of special-category elements only, and is
# always missing: the model has no field for it, and the record says so on every such row.
WANTED = (
    (PURPOSE, lambda e: e.purpose, None),
    (BASIS, lambda e: e.basis, None),
    (SUBJECTS, lambda e: e.subjects, None),
    (CATEGORIES, lambda e: e.categories or e.personal, None),
    (RECIPIENTS, lambda e: e.recipients, None),
    (TRANSFER, lambda e: e.transfer, None),
    (RETENTION, lambda e: e.retention, None),
    ("security measures", lambda e: e.obligations or e.standards, None),
    ("art-9-condition", lambda e: "", SPECIAL),
)


def _gaps(entries: list[Entry]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for field_name, value, only in WANTED:
        population = [e for e in entries if only is None or e.personal == only]
        missing = sorted(e.id for e in population if not value(e))
        if missing:
            gaps.append({"field": field_name, "elements": missing})
    return gaps


def _findings(entries: list[Entry]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in entries:

        def finding(code: str, severity: str, message: str) -> Finding:
            return Finding(code, severity, message, file=entry.file, locator=entry.locator, concept=entry.id)

        if not entry.purpose:
            findings.append(
                finding(
                    "GDR001",
                    SEVERITY_WARNING,
                    f"in the GDPR scope with no '{PURPOSE}' -- the purpose is the first thing a "
                    "record of processing states, and every other field is read against it",
                )
            )
        if entry.personal == SPECIAL and not entry.basis:
            findings.append(
                finding(
                    "GDR002",
                    SEVERITY_ERROR,
                    f"holds special-category data with no '{BASIS}' -- processing special-category "
                    "data without a recorded lawful basis is not a partial row, it is the row a "
                    "supervisor reads first",
                )
            )
        if not entry.retention:
            findings.append(
                finding(
                    "GDR003",
                    SEVERITY_WARNING,
                    f"in the GDPR scope with no '{RETENTION}' -- storage limitation needs an "
                    "envisaged time limit, and 'we keep it' is not one",
                )
            )
        if not entry.obligations and not entry.standards:
            findings.append(
                finding(
                    "GDR004",
                    SEVERITY_WARNING,
                    "nothing governs it -- no requirement, constraint or principle binds it and it "
                    "claims no standard, so the record's security-measures column (Art. 30(1)(g)) "
                    "is empty for it",
                )
            )
        for dispensation_id in entry.dispensations:
            findings.append(
                finding(
                    "GDR005",
                    SEVERITY_INFO,
                    f"covered by open dispensation '{dispensation_id}' -- an exception on a "
                    "processing activity is disclosed, not a violation to fix",
                )
            )
    findings.sort(key=lambda f: (f.code, f.concept, f.message))
    return findings


# --------------------------------------------------------------------------- output


def markdown(register: Register, lang: str = "en") -> str:
    """The record as a document, in ``lang``. Deterministic; ``--as-of`` fixes the date."""
    t = i18n.translator(lang)
    if not register.in_scope:
        raise GdprError(
            f"no element carries '{SCOPE_PROPERTY}' including '{SCOPE_GDPR}' in {register.root} -- "
            "nothing to record. Tag the processing activities in scope first; an empty record "
            "is a document that says nothing while looking like one."
        )
    missing = t("common.missing")
    lines = [
        t("gdpr.title"),
        "",
        t("common.generated", as_of=register.as_of),
        "",
        t("gdpr.notice"),
        "",
        t("gdpr.in_scope", count=len(register.entries)),
        "",
        t("gdpr.h.activities"),
        "",
    ]
    lines += _table(
        t,
        tuple(t(f"gdpr.col.{key}") for key in (
            "element", "name", "purpose", "basis", "subjects", "data", "recipients", "transfer", "retention",
        )),
        [
            (
                e.id,
                e.name,
                e.purpose or missing,
                t(f"gdpr.basis.{e.basis}") if e.basis else missing,
                e.subjects or missing,
                ", ".join(v for v in (t(f"gdpr.personal.{e.personal}") if e.personal else "", e.categories) if v)
                or missing,
                e.recipients or missing,
                e.transfer or missing,
                e.retention or missing,
            )
            for e in register.entries
        ],
    )
    lines += ["", t("gdpr.h.measures"), "", t("gdpr.measures.lead"), ""]
    lines += _table(
        t,
        (t("gdpr.col.element"), t("gdpr.col.obligations"), t("gdpr.col.standards")),
        [(e.id, ", ".join(e.obligations) or missing, ", ".join(e.standards) or missing) for e in register.entries],
    )
    special = [e for e in register.entries if e.personal == SPECIAL]
    if special:
        lines += ["", t("gdpr.h.special"), "", t("gdpr.special.lead"), ""]
        lines += _table(
            t,
            (t("gdpr.col.element"), t("gdpr.col.name"), t("gdpr.col.basis")),
            [(e.id, e.name, t(f"gdpr.basis.{e.basis}") if e.basis else missing) for e in special],
        )
    lines += ["", t("gdpr.h.waivers"), ""]
    lines += _table(
        t,
        (t("gdpr.col.dispensation"), t("gdpr.col.waives"), t("gdpr.col.expires"), t("gdpr.col.elements")),
        [(w["id"], w["waives"] or missing, w["expires"] or missing, ", ".join(w["elements"])) for w in register.waivers],
    )
    lines += ["", t("gdpr.h.gaps"), ""]
    if not register.gaps:
        lines.append(t("gdpr.gaps.none"))
    else:
        lines += [t("gdpr.gaps.lead"), ""]
        lines += _table(
            t,
            (t("common.col.field"), t("common.col.what"), t("common.col.missing_on")),
            [(gap["field"], t(f"gdpr.wants.{gap['field']}"), ", ".join(gap["elements"])) for gap in register.gaps],
        )
    lines += [
        "",
        "---",
        "",
        t(
            "common.findings",
            errors=len(register.errors),
            warnings=len(register.warnings),
            infos=len(register.infos),
            command="gdpr-register",
        ),
    ]
    return "\n".join(lines) + "\n"


def _table(t, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    if not rows:
        return [t("gdpr.nothing")]
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in row) + " |")
    return out


def render(register: Register) -> str:
    """The terminal view: findings and shape, not the document. English, like every report."""
    lines = [ui.bold(f"GDPR record of processing activities -- as of {register.as_of} at {register.root}")]
    if not register.in_scope:
        lines += [
            "",
            ui.dim(
                f"No element carries '{SCOPE_PROPERTY}' including '{SCOPE_GDPR}'. Nothing is in scope, so "
                "no record is generated -- the right output for a model holding no personal data, and "
                "the wrong one for a model that has not tagged its processing activities yet."
            ),
            "",
            ui.verdict(True, 0, 0),
        ]
        return "\n".join(lines)
    special = sum(1 for e in register.entries if e.personal == SPECIAL)
    lines += [
        ui.dim(
            f"{len(register.entries)} processing activit(y/ies) in scope; {special} with special-category "
            f"data; {len(register.waivers)} open waiver(s)"
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
            lines.append(f"  {ui.yellow('{:<20}'.format(gap['field']))} {ui.dim('missing on: ' + ', '.join(gap['elements']))}")
        lines.append("")
    lines += [
        ui.dim(
            "A generator, not a compliance record: the structure follows Art. 30(1), the content comes "
            "from the model, and the controller's details and the legal judgement are a human's."
        ),
        "",
        ui.verdict(register.ok, len(register.errors), len(register.warnings)),
    ]
    return "\n".join(lines)
