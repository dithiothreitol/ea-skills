"""Deterministic validation of the model DSL.

Three layers, in order (docs/BLUEPRINT.md AD-05):

1. **Schema**   -- every YAML fragment against the generated JSON Schema.
2. **Integrity** -- identifiers, references, provenance verified against real source
   text, ownership and review metadata.
3. **Semantics** -- the ArchiMate 3.2 permitted-relationship matrix, structural
   cycles, naming conventions and a starter set of EA smells.

No language model is involved in any check here. That is the point: relationship
semantics is the weakest part of LLM model generation, so it is decided by the
vendored oracle instead.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from . import dsl, genschema, oracle

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_PLACEHOLDER_RE = re.compile(r"\b(tbd|todo|tba|xxx|fixme|\?\?\?)\b", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    file: str = ""
    locator: str = ""
    concept: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        where = self.file or "-"
        if self.locator:
            where = f"{where}:{self.locator}"
        subject = f" [{self.concept}]" if self.concept else ""
        return f"{self.severity.upper():<7} {self.code}  {where}{subject}\n         {self.message}"


@dataclass
class Report:
    root: Path
    zone: str
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
            "zone": self.zone,
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
            f"EA model validation -- zone '{self.zone}' at {self.root}",
            f"ArchiMate oracle {oracle.matrix_version()}; "
            f"{self.counts.get('elements', 0)} elements, "
            f"{self.counts.get('relationships', 0)} relationships, "
            f"{self.counts.get('views', 0)} views",
            "",
        ]
        if not self.findings:
            lines.append("No findings.")
        else:
            for finding in self.findings:
                lines.append(finding.render())
        lines += [
            "",
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s) -- "
            + ("PASS" if self.ok else "FAIL"),
        ]
        return "\n".join(lines)


def _rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()


def _quote_match(haystack_norm: str, quote_norm: str, threshold: float) -> str:
    """Return ``exact``, ``approx`` or ``missing`` for a provenance quote."""
    if not quote_norm:
        return "missing"
    if quote_norm in haystack_norm:
        return "exact"
    span = len(quote_norm)
    if span > len(haystack_norm):
        ratio = difflib.SequenceMatcher(None, quote_norm, haystack_norm).ratio()
        return "approx" if ratio >= threshold else "missing"
    step = max(1, span // 4)
    best = 0.0
    matcher = difflib.SequenceMatcher()
    matcher.set_seq2(quote_norm)
    for start in range(0, len(haystack_norm) - span + 1, step):
        window = haystack_norm[start : start + span]
        matcher.set_seq1(window)
        if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
            continue
        best = max(best, matcher.ratio())
        if best >= threshold:
            return "approx"
    return "approx" if best >= threshold else "missing"


def _iter_concepts(model: dsl.Model) -> Iterable[dsl.Concept]:
    yield from model.elements.values()
    yield from model.relationships.values()


# --------------------------------------------------------------------------- layer 0


def check_oracle() -> list[Finding]:
    findings: list[Finding] = []
    try:
        results = oracle.verify_checksums()
    except oracle.OracleError as exc:
        return [Finding("ORACLE001", SEVERITY_ERROR, str(exc))]
    for result in results:
        if not result.actual:
            findings.append(
                Finding("ORACLE001", SEVERITY_ERROR, f"vendored oracle file is missing: {result.name}")
            )
        elif not result.ok:
            findings.append(
                Finding(
                    "ORACLE001",
                    SEVERITY_ERROR,
                    f"vendored oracle file {result.name} does not match its pinned SHA-256 "
                    f"(expected {result.expected[:16]}..., got {result.actual[:16]}...). "
                    "Re-pin deliberately with 'python -m easkills pin-oracle' after reviewing the change.",
                )
            )
    version = oracle.matrix_version()
    if version != "3.2":
        findings.append(
            Finding("ORACLE002", SEVERITY_WARNING, f"relationship matrix declares ArchiMate {version}, expected 3.2")
        )
    missing = oracle.unmapped_layers()
    if missing:
        findings.append(
            Finding("ORACLE003", SEVERITY_WARNING, f"concepts without a layer assignment: {', '.join(sorted(missing))}")
        )
    return findings


# --------------------------------------------------------------------------- layer 1


def check_schema(root: Path, documents: list[dsl.Document], schema: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    validator = Draft202012Validator(schema)
    for doc in documents:
        rel = _rel(root, doc.path)
        if doc.parse_error:
            findings.append(Finding("SCHEMA000", SEVERITY_ERROR, f"cannot read file: {doc.parse_error}", file=rel))
            continue
        if doc.data is None:
            continue
        for error in sorted(validator.iter_errors(doc.data), key=lambda e: list(e.absolute_path)):
            locator = "/".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(Finding("SCHEMA001", SEVERITY_ERROR, error.message, file=rel, locator=locator))
    return findings


def check_identifiers(model: dsl.Model) -> list[Finding]:
    findings: list[Finding] = []
    for key, first, second in model.duplicate_ids:
        findings.append(
            Finding(
                "ID001",
                SEVERITY_ERROR,
                f"duplicate identifier '{key}' also defined in {_rel(model.root, first)}",
                file=_rel(model.root, second),
                concept=key,
            )
        )
    shared = set(model.elements) & set(model.relationships)
    for key in sorted(shared):
        findings.append(
            Finding("ID002", SEVERITY_ERROR, f"identifier '{key}' is used by both an element and a relationship", concept=key)
        )
    return findings


def check_references(model: dsl.Model) -> list[Finding]:
    findings: list[Finding] = []
    for relationship in model.relationships.values():
        rel_file = _rel(model.root, relationship.source_path)
        for role, ref in (("source", relationship.source), ("target", relationship.target)):
            if ref not in model.elements:
                findings.append(
                    Finding(
                        "REF001",
                        SEVERITY_ERROR,
                        f"relationship {role} '{ref}' does not resolve to an element in this zone",
                        file=rel_file,
                        locator=relationship.locator,
                        concept=relationship.id,
                    )
                )
    for view in model.views.values():
        view_file = _rel(model.root, view.source_path)
        for ref in view.include:
            if ref not in model.elements:
                findings.append(
                    Finding(
                        "REF002",
                        SEVERITY_ERROR,
                        f"view includes unknown element '{ref}'",
                        file=view_file,
                        locator=view.locator,
                        concept=view.id,
                    )
                )
        if not view.include:
            findings.append(
                Finding(
                    "REF003",
                    SEVERITY_WARNING,
                    "view has no elements to show",
                    file=view_file,
                    locator=view.locator,
                    concept=view.id,
                )
            )
    return findings


def check_provenance(model: dsl.Model) -> list[Finding]:
    """Verify traceability mechanically: quotes must exist in the cited source.

    A provenance item is either a direct citation (``file`` + ``quote``) or a
    reference to a fact in the register (``fact:``). Fact references are resolved
    and the *fact's* quotes re-verified here, so the chain from model concept to
    source text stays mechanical even if the register was edited after intake.
    """
    from . import facts as facts_mod  # local import: facts.py imports Finding from here

    findings: list[Finding] = []
    threshold = float(model.config.get("quoteMatchThreshold", 0.90))
    facts_root = model.facts_root()
    cache: dict[Path, str | None] = {}
    register, _register_docs, _entities_doc = facts_mod.load(model.root)

    def verify_quote(concept: dsl.Concept, file: str, quote: str, via: str = "") -> None:
        rel_file = _rel(model.root, concept.source_path)
        suffix = f" (via fact '{via}')" if via else ""
        source_path = (facts_root / file).resolve()
        if source_path not in cache:
            cache[source_path] = (
                source_path.read_text(encoding="utf-8", errors="replace") if source_path.is_file() else None
            )
        text = cache[source_path]
        if text is None:
            findings.append(
                Finding(
                    "PROV002",
                    SEVERITY_ERROR,
                    f"provenance source file not found: {file}{suffix}",
                    file=rel_file,
                    locator=concept.locator,
                    concept=concept.id,
                )
            )
            return
        verdict = _quote_match(_normalize(text), _normalize(quote), threshold)
        if verdict == "missing":
            findings.append(
                Finding(
                    "PROV003",
                    SEVERITY_ERROR,
                    f"provenance quote not found in {file}: {quote[:80]!r}{suffix} -- "
                    "a citation that cannot be located is a fabricated citation",
                    file=rel_file,
                    locator=concept.locator,
                    concept=concept.id,
                )
            )
        elif verdict == "approx":
            findings.append(
                Finding(
                    "PROV004",
                    SEVERITY_WARNING,
                    f"provenance quote matches {file} only approximately{suffix}; quote verbatim text",
                    file=rel_file,
                    locator=concept.locator,
                    concept=concept.id,
                )
            )

    for concept in _iter_concepts(model):
        rel_file = _rel(model.root, concept.source_path)
        if not concept.provenance:
            if not concept.assumed:
                findings.append(
                    Finding(
                        "PROV001",
                        SEVERITY_ERROR,
                        "no provenance and not marked 'assumed: true' -- every concept must be "
                        "traceable to a source or explicitly declared an assumption",
                        file=rel_file,
                        locator=concept.locator,
                        concept=concept.id,
                    )
                )
            elif not concept.rationale:
                findings.append(
                    Finding(
                        "PROV005",
                        SEVERITY_ERROR,
                        "marked 'assumed: true' but no rationale given",
                        file=rel_file,
                        locator=concept.locator,
                        concept=concept.id,
                    )
                )
            else:
                findings.append(
                    Finding(
                        "PROV006",
                        SEVERITY_INFO,
                        f"assumed, pending confirmation: {concept.rationale}",
                        file=rel_file,
                        locator=concept.locator,
                        concept=concept.id,
                    )
                )
            continue

        for provenance in concept.provenance:
            if provenance.fact:
                fact = register.facts.get(provenance.fact)
                if fact is None:
                    findings.append(
                        Finding(
                            "PROV007",
                            SEVERITY_ERROR,
                            f"provenance references fact '{provenance.fact}' which is not in the "
                            "fact register (facts/register/)",
                            file=rel_file,
                            locator=concept.locator,
                            concept=concept.id,
                        )
                    )
                    continue
                for fact_provenance in fact.provenance:
                    verify_quote(concept, fact_provenance.file, fact_provenance.quote, via=fact.id)
                continue
            verify_quote(concept, provenance.file, provenance.quote)
    return findings


def check_governance_metadata(model: dsl.Model, today: date | None = None) -> list[Finding]:
    """Ownership and review recency: the documented mitigations for repository rot."""
    findings: list[Finding] = []
    approved = model.zone == "approved"
    severity = SEVERITY_ERROR if approved else SEVERITY_WARNING
    staleness_days = int(model.config.get("stalenessDays", 365))
    today = today or date.today()

    for element in model.elements.values():
        rel_file = _rel(model.root, element.source_path)
        if not element.owner:
            findings.append(
                Finding(
                    "GOV001",
                    severity,
                    "no owner assigned -- unowned content is what makes an EA repository go stale",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        if not element.last_reviewed:
            findings.append(
                Finding(
                    "GOV002",
                    severity,
                    "no lastReviewed date",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
            continue
        try:
            reviewed = datetime.strptime(element.last_reviewed, "%Y-%m-%d").date()
        except ValueError:
            findings.append(
                Finding(
                    "GOV003",
                    SEVERITY_ERROR,
                    f"lastReviewed is not a valid ISO date: {element.last_reviewed!r}",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
            continue
        age = (today - reviewed).days
        if age > staleness_days:
            findings.append(
                Finding(
                    "GOV004",
                    SEVERITY_WARNING,
                    f"not reviewed for {age} days (threshold {staleness_days})",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        elif reviewed > today:
            findings.append(
                Finding(
                    "GOV005",
                    SEVERITY_WARNING,
                    f"lastReviewed is in the future: {element.last_reviewed}",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
    return findings


# --------------------------------------------------------------------------- layer 2


def check_relationship_matrix(model: dsl.Model) -> list[Finding]:
    """The flagship check: is this relationship permitted by ArchiMate 3.2 at all?"""
    findings: list[Finding] = []
    for relationship in model.relationships.values():
        source = model.elements.get(relationship.source)
        target = model.elements.get(relationship.target)
        if source is None or target is None:
            continue  # already reported as REF001
        allowed = oracle.allowed_relationships(source.type, target.type)
        if relationship.type in allowed:
            continue
        hint = ", ".join(sorted(allowed)) if allowed else "none"
        reverse = oracle.allowed_relationships(target.type, source.type)
        extra = ""
        if relationship.type in reverse:
            extra = " -- it is permitted in the opposite direction, so the endpoints are probably swapped"
        findings.append(
            Finding(
                "REL001",
                SEVERITY_ERROR,
                f"{relationship.type} from {source.type} '{source.id}' to {target.type} '{target.id}' "
                f"is not permitted by the ArchiMate {oracle.matrix_version()} relationship matrix. "
                f"Permitted here: {hint}{extra}",
                file=_rel(model.root, relationship.source_path),
                locator=relationship.locator,
                concept=relationship.id,
            )
        )
    return findings


def check_structural_cycles(model: dsl.Model) -> list[Finding]:
    """Composition and aggregation must form a hierarchy, never a cycle."""
    findings: list[Finding] = []
    graph: dict[str, list[tuple[str, dsl.Relationship]]] = {}
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        if relationship.type not in {"Composition", "Aggregation"}:
            continue
        if relationship.source not in model.elements or relationship.target not in model.elements:
            continue
        graph.setdefault(relationship.source, []).append((relationship.target, relationship))

    WHITE, GREY, BLACK = 0, 1, 2
    colour: dict[str, int] = {}
    reported: set[frozenset[str]] = set()

    def walk(node: str, trail: list[str]) -> None:
        colour[node] = GREY
        for neighbour, relationship in graph.get(node, []):
            state = colour.get(neighbour, WHITE)
            if state == GREY:
                cycle = trail[trail.index(neighbour) :] + [neighbour] if neighbour in trail else [node, neighbour]
                signature = frozenset(cycle)
                if signature not in reported:
                    reported.add(signature)
                    findings.append(
                        Finding(
                            "REL002",
                            SEVERITY_ERROR,
                            f"{relationship.type} closes a structural cycle: " + " -> ".join(cycle)
                            + " -- composition and aggregation must form a hierarchy",
                            file=_rel(model.root, relationship.source_path),
                            locator=relationship.locator,
                            concept=relationship.id,
                        )
                    )
            elif state == WHITE:
                walk(neighbour, trail + [neighbour])
        colour[node] = BLACK

    for node in sorted(graph):
        if colour.get(node, WHITE) == WHITE:
            walk(node, [node])
    return findings


def check_duplicate_relationships(model: dsl.Model) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[tuple[str, str, str], str] = {}
    for relationship in sorted(model.relationships.values(), key=lambda r: r.id):
        key = (relationship.type, relationship.source, relationship.target)
        if key in seen:
            findings.append(
                Finding(
                    "REL003",
                    SEVERITY_WARNING,
                    f"duplicates relationship '{seen[key]}' ({relationship.type} "
                    f"{relationship.source} -> {relationship.target})",
                    file=_rel(model.root, relationship.source_path),
                    locator=relationship.locator,
                    concept=relationship.id,
                )
            )
        else:
            seen[key] = relationship.id
    return findings


def check_naming(model: dsl.Model) -> list[Finding]:
    findings: list[Finding] = []
    by_type_name: dict[tuple[str, str], str] = {}
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        rel_file = _rel(model.root, element.source_path)
        name = element.name
        if _PLACEHOLDER_RE.search(name):
            findings.append(
                Finding(
                    "NAME001",
                    SEVERITY_WARNING,
                    f"name contains a placeholder: {name!r}",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        if name != name.strip() or "  " in name:
            findings.append(
                Finding(
                    "NAME002",
                    SEVERITY_WARNING,
                    f"name has irregular whitespace: {name!r}",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        if len(name) < 3:
            findings.append(
                Finding(
                    "NAME003",
                    SEVERITY_WARNING,
                    f"name is too short to be meaningful: {name!r}",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        key = (element.type, name.casefold())
        if key in by_type_name:
            findings.append(
                Finding(
                    "NAME004",
                    SEVERITY_WARNING,
                    f"another {element.type} named {name!r} already exists ('{by_type_name[key]}') -- "
                    "duplicate names across a model are an EA smell and break traceability",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        else:
            by_type_name[key] = element.id
    return findings


def check_motivation(model: dsl.Model) -> list[Finding]:
    """The AD-09 applicability selector: what a motivation element binds must be real."""
    findings: list[Finding] = []
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if not element.applies_to:
            continue
        rel_file = _rel(model.root, element.source_path)
        if oracle.layer_of(element.type) != "Motivation":
            findings.append(
                Finding(
                    "MOT002",
                    SEVERITY_ERROR,
                    f"appliesTo is an applicability selector for Motivation-layer elements; "
                    f"{element.type} is not one -- model this dependency as a relationship instead",
                    file=rel_file,
                    locator=element.locator,
                    concept=element.id,
                )
            )
        for ref in element.applies_to:
            if ref not in model.elements:
                findings.append(
                    Finding(
                        "MOT001",
                        SEVERITY_ERROR,
                        f"appliesTo references '{ref}' which does not resolve to an element",
                        file=rel_file,
                        locator=element.locator,
                        concept=element.id,
                    )
                )
    return findings


def check_standards(model: dsl.Model, today: date | None = None) -> list[Finding]:
    """SIB lifecycle enforcement: what an element claims to follow must exist, and
    following a dead standard needs either a migration or a time-bounded waiver."""
    from . import govern  # local import: govern.py imports Finding from here

    findings: list[Finding] = []
    if not any(e.standards for e in model.elements.values()):
        return findings
    today = today or date.today()
    governance = govern.load(model.root)

    for element in sorted(model.elements.values(), key=lambda e: e.id):
        rel_file = _rel(model.root, element.source_path)
        for ref in element.standards:
            standard = governance.standards.get(ref)
            if standard is None:
                findings.append(
                    Finding(
                        "STD001",
                        SEVERITY_ERROR,
                        f"references standard '{ref}' which is not in the SIB (standards/)",
                        file=rel_file,
                        locator=element.locator,
                        concept=element.id,
                    )
                )
                continue
            if standard.lifecycle not in {"deprecated", "retired"}:
                continue
            successor = f" -- successor: {standard.successor}" if standard.successor else ""
            dispensation = governance.covering(element.id, ref, today)
            if dispensation is not None:
                findings.append(
                    Finding(
                        "STD004",
                        SEVERITY_INFO,
                        f"{standard.lifecycle} standard '{ref}' is covered by dispensation "
                        f"'{dispensation.id}' until {dispensation.expires}{successor}",
                        file=rel_file,
                        locator=element.locator,
                        concept=element.id,
                    )
                )
            elif standard.lifecycle == "retired":
                findings.append(
                    Finding(
                        "STD002",
                        SEVERITY_ERROR,
                        f"references retired standard '{ref}'{successor} -- migrate, or file a "
                        "time-bounded dispensation (governance-log/dispensations/)",
                        file=rel_file,
                        locator=element.locator,
                        concept=element.id,
                    )
                )
            else:
                findings.append(
                    Finding(
                        "STD003",
                        SEVERITY_WARNING,
                        f"references deprecated standard '{ref}'{successor} -- plan the migration "
                        "before it is retired",
                        file=rel_file,
                        locator=element.locator,
                        concept=element.id,
                    )
                )
    return findings


def check_iso_alignment(model: dsl.Model) -> list[Finding]:
    """ISO/IEC/IEEE 42010 6.3-6.4: stakeholders hold concerns, views frame them.

    These are the checkable halves of the standard's conformance list. Reference
    errors are always on; the coverage warnings fire only once the repository has
    started declaring concerns -- a model that does not use the apparatus yet is
    not nagged about it.
    """
    findings: list[Finding] = []
    uses_apparatus = bool(model.concerns) or bool(model.stakeholders)

    for stakeholder in sorted(model.stakeholders.values(), key=lambda s: s.id):
        rel_file = _rel(model.root, stakeholder.source_path)
        for ref in stakeholder.concerns:
            if ref not in model.concerns:
                findings.append(
                    Finding(
                        "ISO002",
                        SEVERITY_ERROR,
                        f"stakeholder holds unknown concern '{ref}'",
                        file=rel_file,
                        locator=stakeholder.locator,
                        concept=stakeholder.id,
                    )
                )
        if not stakeholder.concerns:
            findings.append(
                Finding(
                    "ISO004",
                    SEVERITY_WARNING,
                    f"stakeholder '{stakeholder.name}' holds no concerns -- either capture what "
                    "they care about or leave them out of the architecture description",
                    file=rel_file,
                    locator=stakeholder.locator,
                    concept=stakeholder.id,
                )
            )

    framed: set[str] = set()
    for view in sorted(model.views.values(), key=lambda v: v.id):
        rel_file = _rel(model.root, view.source_path)
        for ref in view.concerns:
            if ref not in model.concerns:
                findings.append(
                    Finding(
                        "ISO001",
                        SEVERITY_ERROR,
                        f"view frames unknown concern '{ref}'",
                        file=rel_file,
                        locator=view.locator,
                        concept=view.id,
                    )
                )
            else:
                framed.add(ref)
        if uses_apparatus and not view.concerns:
            findings.append(
                Finding(
                    "ISO005",
                    SEVERITY_WARNING,
                    f"view '{view.name}' frames no declared concern -- a view that answers "
                    "no stakeholder question is a view nobody reads",
                    file=rel_file,
                    locator=view.locator,
                    concept=view.id,
                )
            )

    held = {ref for s in model.stakeholders.values() for ref in s.concerns}
    for concern in sorted(model.concerns.values(), key=lambda c: c.id):
        rel_file = _rel(model.root, concern.source_path)
        if concern.id not in framed:
            findings.append(
                Finding(
                    "ISO003",
                    SEVERITY_WARNING,
                    f"concern is framed by no view: {concern.statement!r} -- an unaddressed "
                    "concern is a documented gap in the architecture description",
                    file=rel_file,
                    locator=concern.locator,
                    concept=concern.id,
                )
            )
        if concern.id not in held:
            findings.append(
                Finding(
                    "ISO006",
                    SEVERITY_WARNING,
                    f"no stakeholder holds concern {concern.statement!r} -- concerns belong "
                    "to someone; an ownerless concern cannot be prioritised or confirmed",
                    file=rel_file,
                    locator=concern.locator,
                    concept=concern.id,
                )
            )
    return findings


def check_smells(model: dsl.Model) -> list[Finding]:
    """Starter subset of the EA smells catalogue, as deterministic graph queries."""
    findings: list[Finding] = []
    connected: set[str] = set()
    for relationship in model.relationships.values():
        connected.add(relationship.source)
        connected.add(relationship.target)
    # appliesTo bindings are connectivity too: a requirement that binds a system is
    # not an isolated element, and neither is the system it binds.
    for element in model.elements.values():
        for ref in element.applies_to:
            if ref in model.elements:
                connected.add(element.id)
                connected.add(ref)
    for element in sorted(model.elements.values(), key=lambda e: e.id):
        if element.id in connected:
            continue
        findings.append(
            Finding(
                "SMELL001",
                SEVERITY_WARNING,
                f"{element.type} '{element.name}' has no relationships (isolated element / dead component)",
                file=_rel(model.root, element.source_path),
                locator=element.locator,
                concept=element.id,
            )
        )
    return findings


# --------------------------------------------------------------------------- entry point

CHECK_ORDER = (
    "oracle",
    "schema",
    "identifiers",
    "references",
    "provenance",
    "governance",
    "matrix",
    "cycles",
    "duplicates",
    "motivation",
    "standards",
    "iso",
    "naming",
    "smells",
)


def _run_checks(
    model: dsl.Model, documents: list[dsl.Document], root: Path, zone: str, today: date | None
) -> Report:
    schema = genschema.load_schema()

    findings: list[Finding] = []
    findings += check_oracle()
    findings += check_schema(root, documents, schema)
    findings += check_identifiers(model)
    findings += check_references(model)
    findings += check_provenance(model)
    findings += check_governance_metadata(model, today=today)
    findings += check_relationship_matrix(model)
    findings += check_structural_cycles(model)
    findings += check_duplicate_relationships(model)
    findings += check_motivation(model)
    findings += check_standards(model, today=today)
    findings += check_iso_alignment(model)
    findings += check_naming(model)
    findings += check_smells(model)

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.concept))

    report = Report(root=root, zone=zone, findings=findings)
    report.counts = {
        "elements": len(model.elements),
        "relationships": len(model.relationships),
        "views": len(model.views),
        "stakeholders": len(model.stakeholders),
        "concerns": len(model.concerns),
        "files": len(documents),
    }
    return report


def validate(root: Path, zone: str = "approved", today: date | None = None) -> Report:
    """Validate a zone. ``staging`` is validated as an overlay on ``approved``:
    staging is a proposed delta, so its relationships may reference approved
    elements and a same-id concept is an update proposal, not a duplicate."""
    if zone == "staging":
        model, documents, _config = dsl.load_merged(root, zone_label="staging")
    else:
        model, documents, _config = dsl.load(root, zone)
    return _run_checks(model, documents, root, zone, today)


def validate_promotion(
    root: Path, staging_paths: list[Path] | None = None, today: date | None = None
) -> Report:
    """The promotion gate: approved plus (selected) staging, judged by *approved*
    standards -- governance metadata is mandatory, exactly as it will be after the
    move. This is what must pass before any file leaves staging."""
    model, documents, _config = dsl.load_merged(root, staging_paths, zone_label="approved")
    return _run_checks(model, documents, root, "approved+staging", today)
