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
SERVICES_DIR = Path("services")
REQUESTS_DIR = Path("governance-log") / "requests"

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
    # How a consuming repository evidences this standard (AD-09, `ea-check`): declared
    # by the standard itself, never inferred -- a SIB entry with no rules is simply not
    # checkable in code and stays silent about it.
    detect: list[dict[str, str]] = field(default_factory=list)
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
        expires = _parse_date(self.expires)
        # An unreadable expiry never covers anything: a waiver must fail closed, and
        # DISP008 reports the date itself.
        return expires is not None and expires >= today


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
class Service:
    """An architecture-service offering (AD-10): a promise with an owner and an SLA."""

    id: str
    name: str = ""
    description: str = ""
    fulfilled_by: str = ""
    owner: str = ""
    sla_days: int = 0
    lifecycle: str = ""
    self_service: bool = False
    source_path: Path | None = None


@dataclass
class Request:
    """One entry in the demand ledger: who asked which offering for what."""

    id: str
    service: str = ""
    requested_by: str = ""
    requested: str = ""
    scope: list[str] = field(default_factory=list)
    status: str = "open"
    fulfilled: str = ""
    fulfilled_by: str = ""
    notes: str = ""
    source_path: Path | None = None

    def requested_date(self) -> date | None:
        return _parse_date(self.requested)

    def fulfilled_date(self) -> date | None:
        return _parse_date(self.fulfilled)


@dataclass
class Governance:
    root: Path
    standards: dict[str, Standard] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    dispensations: dict[str, Dispensation] = field(default_factory=dict)
    assessments: dict[str, ComplianceAssessment] = field(default_factory=dict)
    services: dict[str, Service] = field(default_factory=dict)
    requests: dict[str, Request] = field(default_factory=dict)
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
                f"{self.counts.get('assessments', 0)} assessments, "
                f"{self.counts.get('services', 0)} services, "
                f"{self.counts.get('requests', 0)} requests"
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
    for path in sorted(p for p in base.rglob("*") if p.is_file() and p.suffix in {".yaml", ".yml"}):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except dsl.YAML_ERRORS as exc:
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


def _int_or_zero(raw: Any) -> int:
    """Loading must never raise: the schema check is what reports a bad value.

    ``slaDays: ten`` used to crash ``validate-gov`` here, before ``SVC001`` could
    report it -- a traceback instead of a finding, which is the one thing a gate must
    not do. Records are assembled best-effort, exactly as in dsl.py and facts.py.
    """
    if isinstance(raw, bool) or raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _detect_rules(raw: Any) -> list[dict[str, str]]:
    """``detect:`` entries, best-effort; the schema is what reports a malformed one."""
    if not isinstance(raw, list):
        return []
    rules: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            rules.append({str(k): str(v) for k, v in item.items()})
    return rules


def _parse_date(value: str) -> date | None:
    """Real calendar date or ``None`` -- the record schemas only check date *shape*."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


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
                detect=_detect_rules(data.get("detect")),
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

    for doc in _read_record_files(root, SERVICES_DIR):
        governance.documents.append(("SVC", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        register(
            "SVC",
            governance.services,
            str(data["id"]),
            Service(
                id=str(data["id"]),
                name=str(data.get("name", "") or ""),
                description=str(data.get("description", "") or ""),
                fulfilled_by=str(data.get("fulfilledBy", "") or ""),
                owner=str(data.get("owner", "") or ""),
                sla_days=_int_or_zero(data.get("slaDays")),
                lifecycle=str(data.get("lifecycle", "") or ""),
                self_service=bool(data.get("selfService", False)),
                source_path=doc.path,
            ),
            doc.path,
        )

    for doc in _read_record_files(root, REQUESTS_DIR):
        governance.documents.append(("REQ", doc))
        if doc.data is None or not doc.data.get("id"):
            continue
        data = doc.data
        register(
            "REQ",
            governance.requests,
            str(data["id"]),
            Request(
                id=str(data["id"]),
                service=str(data.get("service", "") or ""),
                requested_by=str(data.get("requestedBy", "") or ""),
                requested=str(data.get("requested", "") or ""),
                scope=_str_list(data.get("scope")),
                status=str(data.get("status", "open") or "open"),
                fulfilled=str(data.get("fulfilled", "") or ""),
                fulfilled_by=str(data.get("fulfilledBy", "") or ""),
                notes=str(data.get("notes", "") or ""),
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
    "SVC": genschema.load_service_schema,
    "REQ": genschema.load_request_schema,
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
        # The schema checks date *shape* only, so '2027-13-45' reaches here. Skipping the
        # whole record on an unparseable date (as this used to) silenced the flagship
        # rule: an expired-but-open waiver, a bogus element and an unknown standard all
        # went unreported. Report the date, then keep checking what does not need it.
        expires = _parse_date(dispensation.expires)
        granted = _parse_date(dispensation.granted)
        for field_name, raw, parsed in (
            ("expires", dispensation.expires, expires),
            ("granted", dispensation.granted, granted),
        ):
            if parsed is None:
                findings.append(
                    Finding(
                        "DISP008",
                        SEVERITY_ERROR,
                        f"{field_name} {raw!r} is not a real calendar date -- an unreadable expiry "
                        "cannot expire, which is how a waiver becomes permanent by accident",
                        file=rel_file,
                        concept=dispensation.id,
                    )
                )
        if expires is not None and granted is not None and expires < granted:
            findings.append(
                Finding(
                    "DISP007",
                    SEVERITY_ERROR,
                    f"expires ({dispensation.expires}) before granted ({dispensation.granted})",
                    file=rel_file,
                    concept=dispensation.id,
                )
            )
        if expires is not None and dispensation.status != "closed" and expires < today:
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
        elif (
            expires is not None
            and dispensation.status != "closed"
            and expires <= today + timedelta(days=EXPIRY_WARNING_DAYS)
        ):
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


def _check_requests(governance: Governance, elements: set[str], today: date) -> list[Finding]:
    findings: list[Finding] = []
    for request in sorted(governance.requests.values(), key=lambda r: r.id):
        rel_file = _rel(governance.root, request.source_path)
        service = governance.services.get(request.service)
        if service is None:
            findings.append(
                Finding(
                    "REQ003",
                    SEVERITY_ERROR,
                    f"references unknown service '{request.service}' -- offerings live in services/",
                    file=rel_file,
                    concept=request.id,
                )
            )
        elif service.lifecycle == "retired":
            findings.append(
                Finding(
                    "REQ008",
                    SEVERITY_WARNING,
                    f"requests retired offering '{service.id}' -- update the catalog or the request",
                    file=rel_file,
                    concept=request.id,
                )
            )
        for element_id in request.scope:
            if element_id not in elements:
                findings.append(
                    Finding(
                        "REQ004",
                        SEVERITY_ERROR,
                        f"scope names '{element_id}' which is not an element in the approved model",
                        file=rel_file,
                        concept=request.id,
                    )
                )
        if request.status == "fulfilled" and not (request.fulfilled and request.fulfilled_by):
            findings.append(
                Finding(
                    "REQ005",
                    SEVERITY_ERROR,
                    "status is 'fulfilled' but the fulfilment date or the deliverable pointer "
                    "(fulfilledBy) is missing -- an unevidenced fulfilment is a closed ticket, not a service",
                    file=rel_file,
                    concept=request.id,
                )
            )
        requested = request.requested_date()
        # Same trap as DISP008: a shape-valid but impossible date would silently take the
        # request out of the SLA calculation, so the demand ledger would look healthy.
        for field_name, raw, parsed in (
            ("requested", request.requested, requested),
            ("fulfilled", request.fulfilled, request.fulfilled_date()),
        ):
            if raw and parsed is None:
                findings.append(
                    Finding(
                        "REQ009",
                        SEVERITY_ERROR,
                        f"{field_name} {raw!r} is not a real calendar date -- SLA and fulfilment "
                        "timing are computed from it",
                        file=rel_file,
                        concept=request.id,
                    )
                )
        if (
            request.status == "open"
            and service is not None
            and service.sla_days > 0
            and requested is not None
            and (today - requested).days > service.sla_days
        ):
            findings.append(
                Finding(
                    "REQ006",
                    SEVERITY_WARNING,
                    f"open for {(today - requested).days} days against an SLA of {service.sla_days} -- "
                    "fulfil it, decline it with a reason, or renegotiate the catalog promise",
                    file=rel_file,
                    concept=request.id,
                )
            )
        fulfilled = request.fulfilled_date()
        if requested is not None and fulfilled is not None and fulfilled < requested:
            findings.append(
                Finding(
                    "REQ010",
                    SEVERITY_ERROR,
                    f"fulfilled ({request.fulfilled}) before it was requested ({request.requested}) -- "
                    "the service line reports average fulfilment time from these dates, so this "
                    "quietly makes performance look better than it is",
                    file=rel_file,
                    concept=request.id,
                )
            )
        if request.status == "declined" and not request.notes:
            findings.append(
                Finding(
                    "REQ007",
                    SEVERITY_WARNING,
                    "declined without notes -- a refusal needs a reason the requester can read",
                    file=rel_file,
                    concept=request.id,
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
    findings += _check_requests(governance, elements, today)

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.concept))

    report = GovReport(root=root, findings=findings)
    report.counts = {
        "standards": len(governance.standards),
        "decisions": len(governance.decisions),
        "dispensations": len(governance.dispensations),
        "assessments": len(governance.assessments),
        "services": len(governance.services),
        "requests": len(governance.requests),
    }
    return report
