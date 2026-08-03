"""Governance records: the standards information base and the governance log.

Layout (one record per file, so the git history of a waiver *is* its audit trail):

* ``standards/*.yaml``                     -- SIB entries (type + lifecycle)
* ``governance-log/decisions/*.yaml``      -- architecture decision records (MADR-shaped)
* ``governance-log/dispensations/*.yaml``  -- time-bounded waivers, expiry mandatory
* ``governance-log/compliance/*.yaml``     -- assessments with TOGAF's six-level verdict

The mechanics implemented here are the automatable heart of TOGAF governance:
lifecycle-aware standards references, dispensations that *expire loudly* (an expired
waiver is an error until a human closes or renews it), and assessments whose
non-conformant verdicts must lead somewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from . import dsl, genschema, ui
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

STANDARDS_DIR = Path("standards")
DECISIONS_DIR = Path("governance-log") / "decisions"
DISPENSATIONS_DIR = Path("governance-log") / "dispensations"
COMPLIANCE_DIR = Path("governance-log") / "compliance"

EXPIRY_WARNING_DAYS = 30


@dataclass
class Standard:
    id: str
    name: str
    type: str = ""
    lifecycle: str = ""
    description: str = ""
    owner: str = ""
    successor: str = ""
    source_path: Path | None = None


@dataclass
class Decision:
    id: str
    title: str
    status: str = ""
    date: str = ""
    decision: str = ""
    rationale: str = ""
    context: str = ""
    superseded_by: str = ""
    related_elements: list[str] = field(default_factory=list)
    source_path: Path | None = None


@dataclass
class Dispensation:
    id: str
    waives_standard: str = ""
    waives_rule: str = ""
    applies_to: list[str] = field(default_factory=list)
    rationale: str = ""
    granted_by: str = ""
    granted: str = ""
    expires: str = ""
    status: str = "open"
    source_path: Path | None = None

    def is_open(self, today: date) -> bool:
        if self.status == "closed":
            return False
        try:
            return datetime.strptime(self.expires, "%Y-%m-%d").date() >= today
        except ValueError:
            return False


@dataclass
class ComplianceAssessment:
    id: str
    subject: str = ""
    date: str = ""
    assessor: str = ""
    verdict: str = ""
    findings: list[str] = field(default_factory=list)
    follow_up: dict[str, str] = field(default_factory=dict)
    related_elements: list[str] = field(default_factory=list)
    source_path: Path | None = None


@dataclass
class Governance:
    root: Path
    standards: dict[str, Standard] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    dispensations: dict[str, Dispensation] = field(default_factory=dict)
    assessments: dict[str, ComplianceAssessment] = field(default_factory=dict)
    documents: list[tuple[str, dsl.Document]] = field(default_factory=list)  # (kind, doc)
    duplicates: list[tuple[str, str, Path]] = field(default_factory=list)  # (kind, id, second file)

    def covered_pairs(self, today: date) -> set[tuple[str, str]]:
        """(element id, standard id) pairs covered by an open, unexpired dispensation."""
        pairs: set[tuple[str, str]] = set()
        for dispensation in self.dispensations.values():
            if not dispensation.waives_standard or not dispensation.is_open(today):
                continue
            for element_id in dispensation.applies_to:
                pairs.add((element_id, dispensation.waives_standard))
        return pairs

    def covering(self, element_id: str, standard_id: str, today: date) -> Dispensation | None:
        for dispensation in sorted(self.dispensations.values(), key=lambda d: d.id):
            if (
                dispensation.waives_standard == standard_id
                and element_id in dispensation.applies_to
                and dispensation.is_open(today)
            ):
                return dispensation
        return None


@dataclass
class GovReport:
    root: Path
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "ok": self.ok,
            "counts": self.counts,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": sum(1 for f in self.findings if f.severity == SEVERITY_INFO),
            },
            "findings": [f.as_dict() for f in self.findings],
        }

    def render(self) -> str:
        lines = [
            ui.bold(f"Governance validation at {self.root}"),
            ui.dim(
                f"{self.counts.get('standards', 0)} standards, "
                f"{self.counts.get('decisions', 0)} decisions, "
                f"{self.counts.get('dispensations', 0)} dispensations, "
                f"{self.counts.get('assessments', 0)} assessments"
            ),
            "",
        ]
        if not self.findings:
            lines.append(ui.dim("No findings."))
        else:
            for finding in self.findings:
                lines.append(finding.render())
        lines += ["", ui.verdict(self.ok, len(self.errors), len(self.warnings))]
        return "\n".join(lines)


def _rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_record_files(root: Path, directory: Path) -> list[dsl.Document]:
    base = root / directory
    documents: list[dsl.Document] = []
    if not base.is_dir():
        return documents
    for path in sorted(p for p in base.rglob("*") if p.suffix in {".yaml", ".yml"}):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            documents.append(dsl.Document(path=path, data=None, parse_error=str(exc)))
            continue
        if not isinstance(data, dict) or not data:
            documents.append(
                dsl.Document(path=path, data=None, parse_error="a governance record file holds one mapping")
            )
            continue
        documents.append(dsl.Document(path=path, data=dsl._normalize_scalars(data)))
    return documents


def _str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, (str, int))]


def load(root: Path) -> Governance:
    governance = Governance(root=root)

    def register(kind: str, bucket: dict, record_id: str, record: Any, path: Path) -> bool:
        if record_id in bucket:
            governance.duplicates.append((kind, record_id, path))
            return False
        bucket[record_id] = record
        return True

    for doc in _read_record_files(root, STANDARDS_DIR):
        governance.documents.append(("SIB", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        register(
            "SIB",
            governance.standards,
            str(data["id"]),
            Standard(
                id=str(data["id"]),
                name=str(data.get("name", "") or ""),
                type=str(data.get("type", "") or ""),
                lifecycle=str(data.get("lifecycle", "") or ""),
                description=str(data.get("description", "") or ""),
                owner=str(data.get("owner", "") or ""),
                successor=str(data.get("successor", "") or ""),
                source_path=doc.path,
            ),
            doc.path,
        )

    for doc in _read_record_files(root, DECISIONS_DIR):
        governance.documents.append(("DEC", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        register(
            "DEC",
            governance.decisions,
            str(data["id"]),
            Decision(
                id=str(data["id"]),
                title=str(data.get("title", "") or ""),
                status=str(data.get("status", "") or ""),
                date=str(data.get("date", "") or ""),
                decision=str(data.get("decision", "") or ""),
                rationale=str(data.get("rationale", "") or ""),
                context=str(data.get("context", "") or ""),
                superseded_by=str(data.get("supersededBy", "") or ""),
                related_elements=_str_list(data.get("relatedElements")),
                source_path=doc.path,
            ),
            doc.path,
        )

    for doc in _read_record_files(root, DISPENSATIONS_DIR):
        governance.documents.append(("DISP", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        waives = data.get("waives") if isinstance(data.get("waives"), dict) else {}
        register(
            "DISP",
            governance.dispensations,
            str(data["id"]),
            Dispensation(
                id=str(data["id"]),
                waives_standard=str(waives.get("standard", "") or ""),
                waives_rule=str(waives.get("rule", "") or ""),
                applies_to=_str_list(data.get("appliesTo")),
                rationale=str(data.get("rationale", "") or ""),
                granted_by=str(data.get("grantedBy", "") or ""),
                granted=str(data.get("granted", "") or ""),
                expires=str(data.get("expires", "") or ""),
                status=str(data.get("status", "open") or "open"),
                source_path=doc.path,
            ),
            doc.path,
        )

    for doc in _read_record_files(root, COMPLIANCE_DIR):
        governance.documents.append(("COMP", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        follow_up = data.get("followUp") if isinstance(data.get("followUp"), dict) else {}
        register(
            "COMP",
            governance.assessments,
            str(data["id"]),
            ComplianceAssessment(
                id=str(data["id"]),
                subject=str(data.get("subject", "") or ""),
                date=str(data.get("date", "") or ""),
                assessor=str(data.get("assessor", "") or ""),
                verdict=str(data.get("verdict", "") or ""),
                findings=_str_list(data.get("findings")),
                follow_up={str(k): str(v) for k, v in follow_up.items()},
                related_elements=_str_list(data.get("relatedElements")),
                source_path=doc.path,
            ),
            doc.path,
        )

    return governance


# ------------------------------------------------------------------------ validation

_SCHEMAS = {
    "SIB": genschema.load_standard_schema,
    "DEC": genschema.load_decision_schema,
    "DISP": genschema.load_dispensation_schema,
    "COMP": genschema.load_compliance_schema,
}


def _check_schemas(governance: Governance) -> list[Finding]:
    findings: list[Finding] = []
    validators = {kind: Draft202012Validator(loader()) for kind, loader in _SCHEMAS.items()}
    for kind, doc in governance.documents:
        rel = _rel(governance.root, doc.path)
        if doc.parse_error:
            findings.append(Finding(f"{kind}000", SEVERITY_ERROR, f"cannot read file: {doc.parse_error}", file=rel))
            continue
        if doc.data is None:
            continue
        for error in sorted(validators[kind].iter_errors(doc.data), key=lambda e: list(e.absolute_path)):
            locator = "/".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(Finding(f"{kind}001", SEVERITY_ERROR, error.message, file=rel, locator=locator))
    for kind, record_id, path in governance.duplicates:
        findings.append(
            Finding(
                f"{kind}002",
                SEVERITY_ERROR,
                f"duplicate {kind.lower()} record id '{record_id}'",
                file=_rel(governance.root, path),
                concept=record_id,
            )
        )
    return findings


def _check_standards(governance: Governance) -> list[Finding]:
    findings: list[Finding] = []
    for standard in sorted(governance.standards.values(), key=lambda s: s.id):
        if standard.successor and standard.successor not in governance.standards:
            findings.append(
                Finding(
                    "SIB003",
                    SEVERITY_ERROR,
                    f"successor '{standard.successor}' is not a standard in the SIB",
                    file=_rel(governance.root, standard.source_path),
                    concept=standard.id,
                )
            )
        if standard.lifecycle in {"deprecated", "retired"} and not standard.successor:
            findings.append(
                Finding(
                    "SIB004",
                    SEVERITY_WARNING,
                    f"{standard.lifecycle} standard names no successor -- teams being moved off "
                    "a standard need to know what to move to",
                    file=_rel(governance.root, standard.source_path),
                    concept=standard.id,
                )
            )
    return findings


def _check_dispensations(governance: Governance, elements: set[str], today: date) -> list[Finding]:
    findings: list[Finding] = []
    for dispensation in sorted(governance.dispensations.values(), key=lambda d: d.id):
        rel_file = _rel(governance.root, dispensation.source_path)
        try:
            expires = datetime.strptime(dispensation.expires, "%Y-%m-%d").date()
            granted = datetime.strptime(dispensation.granted, "%Y-%m-%d").date()
        except ValueError:
            continue  # schema already rejected the format
        if expires < granted:
            findings.append(
                Finding(
                    "DISP007",
                    SEVERITY_ERROR,
                    f"expires ({dispensation.expires}) before granted ({dispensation.granted})",
                    file=rel_file,
                    concept=dispensation.id,
                )
            )
        if dispensation.status != "closed" and expires < today:
            findings.append(
                Finding(
                    "DISP003",
                    SEVERITY_ERROR,
                    f"expired {dispensation.expires} and is still open -- expiry re-triggers review: "
                    "renew it with a new record or set 'status: closed'",
                    file=rel_file,
                    concept=dispensation.id,
                )
            )
        elif dispensation.status != "closed" and expires <= today + timedelta(days=EXPIRY_WARNING_DAYS):
            findings.append(
                Finding(
                    "DISP006",
                    SEVERITY_WARNING,
                    f"expires {dispensation.expires} (within {EXPIRY_WARNING_DAYS} days) -- schedule the review now",
                    file=rel_file,
                    concept=dispensation.id,
                )
            )
        for element_id in dispensation.applies_to:
            if element_id not in elements:
                findings.append(
                    Finding(
                        "DISP004",
                        SEVERITY_ERROR,
                        f"applies to '{element_id}' which is not an element in the approved model",
                        file=rel_file,
                        concept=dispensation.id,
                    )
                )
        if dispensation.waives_standard and dispensation.waives_standard not in governance.standards:
            findings.append(
                Finding(
                    "DISP005",
                    SEVERITY_ERROR,
                    f"waives unknown standard '{dispensation.waives_standard}'",
                    file=rel_file,
                    concept=dispensation.id,
                )
            )
    return findings


def _check_decisions(governance: Governance, elements: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for decision in sorted(governance.decisions.values(), key=lambda d: d.id):
        rel_file = _rel(governance.root, decision.source_path)
        if decision.superseded_by and decision.superseded_by not in governance.decisions:
            findings.append(
                Finding(
                    "DEC003",
                    SEVERITY_ERROR,
                    f"supersededBy '{decision.superseded_by}' is not a decision record",
                    file=rel_file,
                    concept=decision.id,
                )
            )
        if decision.status == "superseded" and not decision.superseded_by:
            findings.append(
                Finding(
                    "DEC004",
                    SEVERITY_WARNING,
                    "status is 'superseded' but no supersededBy record is named",
                    file=rel_file,
                    concept=decision.id,
                )
            )
        for element_id in decision.related_elements:
            if element_id not in elements:
                findings.append(
                    Finding(
                        "DEC005",
                        SEVERITY_ERROR,
                        f"relatedElements names '{element_id}' which is not in the approved model",
                        file=rel_file,
                        concept=decision.id,
                    )
                )
    return findings


def _check_assessments(governance: Governance, elements: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for assessment in sorted(governance.assessments.values(), key=lambda a: a.id):
        rel_file = _rel(governance.root, assessment.source_path)
        if assessment.verdict == "non-conformant" and not assessment.follow_up:
            findings.append(
                Finding(
                    "COMP003",
                    SEVERITY_WARNING,
                    "non-conformant with no followUp -- a failed assessment must lead to a "
                    "dispensation, a decision, or documented remediation",
                    file=rel_file,
                    concept=assessment.id,
                )
            )
        for key, bucket in (("dispensation", governance.dispensations), ("decision", governance.decisions)):
            ref = assessment.follow_up.get(key, "")
            if ref and ref not in bucket:
                findings.append(
                    Finding(
                        "COMP004",
                        SEVERITY_ERROR,
                        f"followUp {key} '{ref}' does not exist",
                        file=rel_file,
                        concept=assessment.id,
                    )
                )
        for element_id in assessment.related_elements:
            if element_id not in elements:
                findings.append(
                    Finding(
                        "COMP005",
                        SEVERITY_ERROR,
                        f"relatedElements names '{element_id}' which is not in the approved model",
                        file=rel_file,
                        concept=assessment.id,
                    )
                )
    return findings


def validate_governance(root: Path, today: date | None = None) -> GovReport:
    today = today or date.today()
    governance = load(root)
    model, _documents, _config = dsl.load(root, "approved")
    elements = set(model.elements)

    findings: list[Finding] = []
    findings += _check_schemas(governance)
    findings += _check_standards(governance)
    findings += _check_dispensations(governance, elements, today)
    findings += _check_decisions(governance, elements)
    findings += _check_assessments(governance, elements)

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.concept))

    report = GovReport(root=root, findings=findings)
    report.counts = {
        "standards": len(governance.standards),
        "decisions": len(governance.decisions),
        "dispensations": len(governance.dispensations),
        "assessments": len(governance.assessments),
    }
    return report
