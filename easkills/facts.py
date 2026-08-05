"""The fact register: verified statements extracted from sources by ``ea-intake``.

Facts sit between raw sources and the model (docs/BLUEPRINT.md, AD-03/AD-04):

* A fact is one atomic statement carrying at least one verbatim quote, and the quote
  is located mechanically in the cited source -- same discipline as model provenance.
* Entities give recurring names a canonical form plus an alias table, so downstream
  modelling resolves "the portal" and "Order Portal" to the same thing.
* Unlike model concepts, facts have **no** ``assumed`` escape hatch. A statement that
  cannot cite a source is not a fact; it belongs in a clarification question instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from . import dsl, genschema, ui
from .validate import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    Finding,
    _normalize,
    _quote_match,
)

REGISTER_DIR = Path("facts") / "register"
ENTITIES_FILE = Path("facts") / "entities.yaml"
SOURCE_SUFFIXES = {".md", ".txt"}


@dataclass
class Fact:
    id: str
    statement: str
    provenance: list[dsl.Provenance] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    confidence: str = "stated"
    # Facts this one contradicts. A contradiction is recorded, never resolved silently:
    # both sides stay, each with its own verified quote, and the model decides which one
    # it follows -- visibly (PROV009), not by which source happened to be read last.
    contests: list[str] = field(default_factory=list)
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Entity:
    id: str
    name: str
    kind: str = ""
    aliases: list[str] = field(default_factory=list)
    documentation: str = ""
    source_path: Path | None = None
    locator: str = ""


@dataclass
class Register:
    root: Path
    config: dict[str, Any]
    facts: dict[str, Fact] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    duplicate_fact_ids: list[tuple[str, Path, Path]] = field(default_factory=list)
    duplicate_entity_ids: list[tuple[str, Path, Path]] = field(default_factory=list)

    def facts_root(self) -> Path:
        return (self.root / str(self.config.get("factsRoot", "."))).resolve()

    def sources_dir(self) -> Path:
        return (self.root / str(self.config.get("sourcesDir", "facts/sources"))).resolve()


@dataclass
class FactsReport:
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
            ui.bold(f"Fact register validation at {self.root}"),
            ui.dim(
                f"{self.counts.get('facts', 0)} facts, "
                f"{self.counts.get('entities', 0)} entities, "
                f"{self.counts.get('sources', 0)} source file(s)"
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


def _str_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if isinstance(x, (str, int))]


def load_register_documents(root: Path) -> list[dsl.Document]:
    """Read every YAML file under facts/register, path-sorted for determinism."""
    directory = root / REGISTER_DIR
    documents: list[dsl.Document] = []
    if not directory.is_dir():
        return documents
    paths = sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in {".yaml", ".yml"})
    for path in paths:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except dsl.YAML_ERRORS as exc:
            documents.append(dsl.Document(path=path, data=None, parse_error=str(exc)))
            continue
        if data is None:
            data = {}
        if not isinstance(data, dict):
            documents.append(
                dsl.Document(path=path, data=None, parse_error="top level of a register file must be a mapping")
            )
            continue
        documents.append(dsl.Document(path=path, data=data))
    return documents


def load_entities_document(root: Path) -> dsl.Document | None:
    path = root / ENTITIES_FILE
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except dsl.YAML_ERRORS as exc:
        return dsl.Document(path=path, data=None, parse_error=str(exc))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return dsl.Document(path=path, data=None, parse_error="top level of the entity table must be a mapping")
    return dsl.Document(path=path, data=data)


def build_register(
    root: Path,
    documents: list[dsl.Document],
    entities_doc: dsl.Document | None,
    config: dict[str, Any],
) -> Register:
    """Assemble a Register best-effort; malformed items are skipped (validator reports them)."""
    register = Register(root=root, config=config)
    for doc in documents:
        if doc.data is None:
            continue
        for index, item in enumerate(doc.data.get("facts") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            fact = Fact(
                id=str(item.get("id", "")),
                statement=str(item.get("statement", "") or ""),
                provenance=dsl._provenance(item.get("provenance")),
                entities=_str_list(item.get("entities")),
                topics=_str_list(item.get("topics")),
                confidence=str(item.get("confidence", "stated") or "stated"),
                contests=_str_list(item.get("contests")),
                source_path=doc.path,
                locator=f"facts[{index}]",
            )
            existing = register.facts.get(fact.id)
            if existing is not None:
                register.duplicate_fact_ids.append((fact.id, existing.source_path or doc.path, doc.path))
                continue
            register.facts[fact.id] = fact
    if entities_doc is not None and entities_doc.data is not None:
        for index, item in enumerate(entities_doc.data.get("entities") or []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            entity = Entity(
                id=str(item.get("id", "")),
                name=str(item.get("name", "") or ""),
                kind=str(item.get("kind", "") or ""),
                aliases=_str_list(item.get("aliases")),
                documentation=str(item.get("documentation", "") or ""),
                source_path=entities_doc.path,
                locator=f"entities[{index}]",
            )
            existing_entity = register.entities.get(entity.id)
            if existing_entity is not None:
                register.duplicate_entity_ids.append(
                    (entity.id, existing_entity.source_path or entities_doc.path, entities_doc.path)
                )
                continue
            register.entities[entity.id] = entity
    return register


def load(root: Path) -> tuple[Register, list[dsl.Document], dsl.Document | None]:
    config = dsl.load_config(root)
    documents = load_register_documents(root)
    entities_doc = load_entities_document(root)
    register = build_register(root, documents, entities_doc, config)
    return register, documents, entities_doc


# ------------------------------------------------------------------------ validation


def check_schema(
    root: Path, documents: list[dsl.Document], entities_doc: dsl.Document | None
) -> list[Finding]:
    findings: list[Finding] = []
    facts_validator = Draft202012Validator(genschema.load_facts_schema())
    entities_validator = Draft202012Validator(genschema.load_entities_schema())
    for doc, validator in [(d, facts_validator) for d in documents] + (
        [(entities_doc, entities_validator)] if entities_doc is not None else []
    ):
        rel = _rel(root, doc.path)
        if doc.parse_error:
            findings.append(Finding("FACT000", SEVERITY_ERROR, f"cannot read file: {doc.parse_error}", file=rel))
            continue
        if doc.data is None:
            continue
        for error in sorted(validator.iter_errors(doc.data), key=lambda e: list(e.absolute_path)):
            locator = "/".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(Finding("FACT001", SEVERITY_ERROR, error.message, file=rel, locator=locator))
    return findings


def check_identifiers(register: Register) -> list[Finding]:
    findings: list[Finding] = []
    for key, first, second in register.duplicate_fact_ids:
        findings.append(
            Finding(
                "FACT002",
                SEVERITY_ERROR,
                f"duplicate fact id '{key}' also defined in {_rel(register.root, first)}",
                file=_rel(register.root, second),
                concept=key,
            )
        )
    for key, first, second in register.duplicate_entity_ids:
        findings.append(
            Finding(
                "ENT001",
                SEVERITY_ERROR,
                f"duplicate entity id '{key}'",
                file=_rel(register.root, second),
                concept=key,
            )
        )
    return findings


def check_quotes(register: Register) -> list[Finding]:
    """Locate every quote in its cited source -- the same gate model provenance passes."""
    findings: list[Finding] = []
    threshold, _problem = dsl.config_number(
        register.config, "quoteMatchThreshold", 0.90, minimum=0.0, maximum=1.0
    )  # the model gate reports a bad value (SCHEMA002); never crash on it here
    facts_root = register.facts_root()
    cache: dict[Path, str | None] = {}

    for fact in register.facts.values():
        rel_file = _rel(register.root, fact.source_path)
        for provenance in fact.provenance:
            source_path, problem = dsl.resolve_provenance_file(register.root, facts_root, provenance.file)
            if source_path is None:
                findings.append(
                    Finding(
                        "FACT008",
                        SEVERITY_ERROR,
                        f"provenance file {provenance.file!r} {problem} -- the evidence for a fact "
                        "must be a source file in this repository",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
                continue
            if source_path not in cache:
                cache[source_path] = (
                    source_path.read_text(encoding="utf-8", errors="replace") if source_path.is_file() else None
                )
            text = cache[source_path]
            if text is None:
                findings.append(
                    Finding(
                        "FACT003",
                        SEVERITY_ERROR,
                        f"provenance source file not found: {provenance.file}",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
                continue
            verdict = _quote_match(_normalize(text), _normalize(provenance.quote), threshold)
            if verdict == "missing":
                findings.append(
                    Finding(
                        "FACT004",
                        SEVERITY_ERROR,
                        f"provenance quote not found in {provenance.file}: {provenance.quote[:80]!r} -- "
                        "a citation that cannot be located is a fabricated citation",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
            elif verdict == "approx":
                findings.append(
                    Finding(
                        "FACT005",
                        SEVERITY_WARNING,
                        f"provenance quote matches {provenance.file} only approximately; quote verbatim text",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
    return findings


def check_entities(register: Register) -> list[Finding]:
    findings: list[Finding] = []

    for fact in sorted(register.facts.values(), key=lambda f: f.id):
        for ref in fact.entities:
            if ref not in register.entities:
                findings.append(
                    Finding(
                        "FACT006",
                        SEVERITY_ERROR,
                        f"fact references unknown entity '{ref}' -- add it to facts/entities.yaml "
                        "or fix the reference",
                        file=_rel(register.root, fact.source_path),
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )

    # A term (canonical name or alias) must resolve to exactly one entity; a collision
    # means entity resolution failed and downstream modelling would merge two things.
    terms: dict[str, tuple[str, str]] = {}
    for entity in sorted(register.entities.values(), key=lambda e: e.id):
        rel_file = _rel(register.root, entity.source_path)
        for role, term in [("name", entity.name)] + [("alias", a) for a in entity.aliases]:
            key = _normalize(term)
            if not key:
                continue
            if key in terms and terms[key][0] != entity.id:
                other_id, other_role = terms[key]
                findings.append(
                    Finding(
                        "ENT002",
                        SEVERITY_ERROR,
                        f"{role} {term!r} collides with the {other_role} of entity '{other_id}' -- "
                        "one term must resolve to exactly one entity",
                        file=rel_file,
                        locator=entity.locator,
                        concept=entity.id,
                    )
                )
            else:
                terms.setdefault(key, (entity.id, role))

    referenced = {ref for fact in register.facts.values() for ref in fact.entities}
    for entity in sorted(register.entities.values(), key=lambda e: e.id):
        if entity.id not in referenced:
            findings.append(
                Finding(
                    "ENT003",
                    SEVERITY_WARNING,
                    f"entity '{entity.name}' is never referenced by any fact",
                    file=_rel(register.root, entity.source_path),
                    locator=entity.locator,
                    concept=entity.id,
                )
            )
    return findings


def check_contradictions(register: Register) -> list[Finding]:
    """Sources disagree; the register has to say so, and say it in a followable way.

    Nothing here decides who is right -- that is a modelling decision, made in the open
    and reported by ``PROV009``. These checks only ensure a recorded contradiction names
    the other side, that the other side exists, and that it points back.
    """
    findings: list[Finding] = []
    for fact in sorted(register.facts.values(), key=lambda f: f.id):
        rel_file = _rel(register.root, fact.source_path)
        if fact.confidence == "contested" and not fact.contests:
            findings.append(
                Finding(
                    "FACT009",
                    SEVERITY_ERROR,
                    "confidence is 'contested' but no 'contests' fact is named -- a contradiction "
                    "nobody can follow is hinted at, not recorded",
                    file=rel_file,
                    locator=fact.locator,
                    concept=fact.id,
                )
            )
        for ref in sorted(fact.contests):
            other = register.facts.get(ref)
            if other is None:
                findings.append(
                    Finding(
                        "FACT010",
                        SEVERITY_ERROR,
                        f"contests unknown fact '{ref}'",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
                continue
            if fact.id not in other.contests or other.confidence != "contested":
                findings.append(
                    Finding(
                        "FACT011",
                        SEVERITY_WARNING,
                        f"contests '{ref}', but '{ref}' does not record the disagreement back -- "
                        "a one-sided contradiction reads as if one source simply won",
                        file=rel_file,
                        locator=fact.locator,
                        concept=fact.id,
                    )
                )
    return findings


def check_duplicate_statements(register: Register) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for fact in sorted(register.facts.values(), key=lambda f: f.id):
        key = _normalize(fact.statement)
        if not key:
            continue
        if key in seen:
            findings.append(
                Finding(
                    "FACT007",
                    SEVERITY_WARNING,
                    f"statement duplicates fact '{seen[key]}' -- merge them and keep both quotes as provenance",
                    file=_rel(register.root, fact.source_path),
                    locator=fact.locator,
                    concept=fact.id,
                )
            )
        else:
            seen[key] = fact.id
    return findings


def iter_source_files(register: Register) -> list[Path]:
    directory = register.sources_dir()
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in SOURCE_SUFFIXES)


def check_uncited_sources(register: Register) -> list[Finding]:
    """A source nobody cites is either unread or unreadable; both need surfacing."""
    findings: list[Finding] = []
    facts_root = register.facts_root()
    cited = {
        path
        for fact in register.facts.values()
        for provenance in fact.provenance
        for path in [dsl.resolve_provenance_file(register.root, facts_root, provenance.file)[0]]
        if path is not None
    }
    for path in iter_source_files(register):
        if path.resolve() not in cited:
            findings.append(
                Finding(
                    "SRC001",
                    SEVERITY_WARNING,
                    "source file is never cited by any fact -- it has not been ingested "
                    "(run ea-intake over it) or contains nothing extractable (say so in the intake report)",
                    file=_rel(register.root, path),
                )
            )
    return findings


def validate_facts(root: Path) -> FactsReport:
    register, documents, entities_doc = load(root)

    findings: list[Finding] = []
    findings += check_schema(root, documents, entities_doc)
    findings += check_identifiers(register)
    findings += check_quotes(register)
    findings += check_entities(register)
    findings += check_contradictions(register)
    findings += check_duplicate_statements(register)
    findings += check_uncited_sources(register)

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.concept))

    report = FactsReport(root=root, findings=findings)
    report.counts = {
        "facts": len(register.facts),
        "entities": len(register.entities),
        "sources": len(iter_source_files(register)),
        "files": len(documents),
    }
    return report
