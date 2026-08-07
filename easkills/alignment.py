"""Two-way coverage of the model against a reference architecture (the ALN family).

"When is a layer done?" is only answerable against a yardstick. The repository already
had one -- the sources, via ``coverage`` -- which answers *did we model what we were
told*. This adds the second: a reference taxonomy, which answers *did we model what an
industry blueprint says a business like this has*.

Two directions, deliberately unequal:

* **Reference -> model.** Every node is ``covered``, ``partial``, a **gap**, or
  ``out-of-scope`` *with a recorded rationale*. Nothing passes by being unexamined --
  the same rule as ``conformance``. A gap is a warning, because an unmapped node is a
  question, not a defect; an *unrecorded* exclusion is an error, because silence
  masquerading as a decision is the failure this whole family exists to prevent.
* **Model -> reference.** Local elements no mapping anchors are reported as
  information, never as findings. A business does things its industry blueprint never
  heard of, and a tool that called that a defect would teach architects to model the
  blueprint instead of the business.

Two asymmetries worth knowing before reading a report:

* **Out-of-scope inherits downwards; coverage does not.** Declaring a branch out of
  scope is one decision about one area, so it carries to the whole subtree. Claiming a
  branch covered is a claim about every leaf under it, and those are earned one at a
  time.
* **Only leaves are scored.** A branch is a heading, not something an application
  realizes. Branches carry a rolled-up percentage of their subtree instead.

Everything fails closed. An exclusion without a rationale does not exclude (ALN005);
a coverage claim resting on an element this zone does not hold does not cover
(ALN003/ALN007). Under-reporting a gap is the failure mode that matters here, so every
ambiguity resolves towards *gap*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import dsl, genschema, reference as reference_mod, ui
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

STATUS_COVERED = "covered"
STATUS_PARTIAL = "partial"
STATUS_GAP = "gap"
STATUS_OUT_OF_SCOPE = "out-of-scope"
# Not a mapping status: what a taxonomy *heading* gets. A branch is not something an
# application realizes, so calling an unmapped one a gap would invent findings for the
# shape of the taxonomy rather than for the state of the architecture.
STATUS_BRANCH = "branch"

# What a node of each kind is answered by, locally. Used only for the *informational*
# unanchored list: it decides which local elements a pack could plausibly anchor, so
# that a capability reference does not report every Node and Artifact as unanchored.
KIND_LOCAL_TYPES: dict[str, tuple[str, ...]] = {
    "capability": ("Capability", "ValueStream"),
    "process": ("BusinessProcess", "BusinessFunction", "BusinessInteraction"),
    "control": ("Requirement", "Constraint", "Principle"),
    "domain": ("Grouping",),
}

# A partial counts half: it found the connection and contested the grain, which is the
# same arithmetic the golden-set scorer uses for a derived relationship.
COVERAGE_WEIGHT = {STATUS_COVERED: 1.0, STATUS_PARTIAL: 0.5, STATUS_GAP: 0.0}


class AlignmentError(RuntimeError):
    """An operator mistake worth refusing on (an unknown ``--reference`` name)."""


@dataclass(frozen=True)
class NodeAlignment:
    id: str
    name: str
    kind: str
    parent: str
    external_id: str
    depth: int
    leaf: bool
    status: str
    elements: tuple[str, ...] = ()
    note: str = ""
    rationale: str = ""
    # True when the status was inherited from an out-of-scope ancestor rather than
    # declared here -- so a reader can tell a decision from its consequences.
    inherited_from: str = ""

    @property
    def scored(self) -> bool:
        return self.leaf and self.status != STATUS_OUT_OF_SCOPE

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "parent": self.parent,
            "externalId": self.external_id,
            "depth": self.depth,
            "leaf": self.leaf,
            "status": self.status,
            "elements": list(self.elements),
            "note": self.note,
            "rationale": self.rationale,
            "inheritedFrom": self.inherited_from,
        }


@dataclass(frozen=True)
class BranchRollup:
    id: str
    name: str
    in_scope: int
    out_of_scope: int
    credit: float

    @property
    def ratio(self) -> float | None:
        return self.credit / self.in_scope if self.in_scope else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "inScope": self.in_scope,
            "outOfScope": self.out_of_scope,
            "credit": round(self.credit, 4),
            "coverage": None if self.ratio is None else round(self.ratio, 4),
        }


@dataclass
class PackAlignment:
    name: str
    directory: str
    refused: str = ""
    nodes: list[NodeAlignment] = field(default_factory=list)
    branches: list[BranchRollup] = field(default_factory=list)
    # Local elements of a type this pack could anchor, that no mapping names.
    unanchored: list[tuple[str, str, str]] = field(default_factory=list)  # (id, type, name)

    @property
    def scored(self) -> list[NodeAlignment]:
        return [node for node in self.nodes if node.scored]

    @property
    def in_scope(self) -> int:
        return len(self.scored)

    @property
    def credit(self) -> float:
        return sum(COVERAGE_WEIGHT.get(node.status, 0.0) for node in self.scored)

    @property
    def ratio(self) -> float | None:
        """Coverage of the scored (leaf, in-scope) nodes -- ``None`` when there are none.

        Deliberately not 1.0: a vacuous 100% is how an empty measurement reads as a
        perfect one, and this repository has paid for that mistake once already.
        """
        return self.credit / self.in_scope if self.in_scope else None

    def counts(self) -> dict[str, int]:
        tally = {status: 0 for status in (STATUS_COVERED, STATUS_PARTIAL, STATUS_GAP, STATUS_OUT_OF_SCOPE)}
        for node in self.nodes:
            if node.leaf:
                tally[node.status] = tally.get(node.status, 0) + 1
        return tally

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "directory": self.directory,
            "refused": self.refused,
            "nodes": [node.as_dict() for node in self.nodes],
            "leafCounts": self.counts(),
            "inScope": self.in_scope,
            "credit": round(self.credit, 4),
            "coverage": None if self.ratio is None else round(self.ratio, 4),
            "branches": [branch.as_dict() for branch in self.branches],
            "unanchored": [
                {"id": item[0], "type": item[1], "name": item[2]} for item in self.unanchored
            ],
        }


@dataclass
class AlignmentReport:
    root: Path
    zone: str
    packs: list[PackAlignment] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def in_scope(self) -> int:
        return sum(pack.in_scope for pack in self.packs)

    @property
    def credit(self) -> float:
        return sum(pack.credit for pack in self.packs)

    @property
    def ratio(self) -> float | None:
        return self.credit / self.in_scope if self.in_scope else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "zone": self.zone,
            "ok": self.ok,
            "inScope": self.in_scope,
            "credit": round(self.credit, 4),
            "coverage": None if self.ratio is None else round(self.ratio, 4),
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": sum(1 for f in self.findings if f.severity == SEVERITY_INFO),
            },
            "packs": [pack.as_dict() for pack in self.packs],
            "findings": [f.as_dict() for f in self.findings],
        }

    def render(self) -> str:
        overall = "n/a" if self.ratio is None else f"{self.ratio:.0%}"
        lines = [
            ui.bold(f"Reference alignment -- zone '{self.zone}' at {self.root}"),
            ui.dim(
                f"{len(self.packs)} reference pack(s), {self.in_scope} node(s) in scope, "
                f"coverage {overall}"
            ),
        ]
        if not self.packs:
            lines += ["", ui.dim(f"No reference pack found under {reference_mod.REFERENCE_DIRNAME}/.")]
        for pack in self.packs:
            lines.append("")
            lines += _render_pack(pack)
        lines.append("")
        if not self.findings:
            lines.append(ui.dim("No findings."))
        else:
            for finding in self.findings:
                lines.append(finding.render())
        lines += ["", ui.verdict(self.ok, len(self.errors), len(self.warnings))]
        return "\n".join(lines)


_STATUS_STYLE = {
    STATUS_COVERED: ui.green,
    STATUS_PARTIAL: ui.yellow,
    STATUS_GAP: ui.red,
    STATUS_OUT_OF_SCOPE: ui.dim,
    STATUS_BRANCH: ui.dim,
}


def _render_pack(pack: PackAlignment) -> list[str]:
    ratio = "n/a" if pack.ratio is None else f"{pack.ratio:.0%}"
    header = f"{ui.bullet()} {ui.bold(pack.name)}" if ui.enabled() else pack.name
    lines = [header]
    if pack.refused:
        lines.append(f"  {ui.red('refused')}  {pack.refused}")
        return lines
    tally = pack.counts()
    lines.append(
        ui.dim(
            f"  {pack.in_scope} in scope, coverage {ratio} -- "
            f"{tally[STATUS_COVERED]} covered, {tally[STATUS_PARTIAL]} partial, "
            f"{tally[STATUS_GAP]} gap, {tally[STATUS_OUT_OF_SCOPE]} out-of-scope (leaf nodes)"
        )
    )
    for node in pack.nodes:
        style = _STATUS_STYLE.get(node.status, ui.dim)
        indent = "  " + "  " * node.depth
        label = f"{node.id} {node.name}" if not node.external_id else f"{node.external_id} {node.name}"
        detail = ""
        if node.elements:
            detail = ui.dim(" <- " + ", ".join(node.elements))
        elif node.status == STATUS_OUT_OF_SCOPE and node.inherited_from:
            detail = ui.dim(f" (inherited from {node.inherited_from})")
        lines.append(f"{indent}{style(f'{node.status:<12}')} {label}{detail}")
        if node.note:
            lines.append(f"{indent}             {ui.dim('note: ' + node.note)}")
        if node.rationale and not node.inherited_from:
            lines.append(f"{indent}             {ui.dim('rationale: ' + node.rationale)}")
    if pack.branches:
        lines.append(ui.dim("  branch rollup:"))
        for branch in pack.branches:
            value = "n/a" if branch.ratio is None else f"{branch.ratio:.0%}"
            lines.append(
                f"    {value:>4}  {branch.name} "
                + ui.dim(f"({branch.credit:g}/{branch.in_scope} in scope, {branch.out_of_scope} out-of-scope)")
            )
    if pack.unanchored:
        lines.append(
            ui.dim(
                f"  {len(pack.unanchored)} local element(s) this reference does not anchor "
                "(information, not a finding):"
            )
        )
        for element_id, element_type, name in pack.unanchored:
            lines.append(f"    {ui.cyan(element_id)} {ui.dim(f'{element_type} -- {name}')}")
    return lines


def _rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _schema_validators() -> dict[str, Draft202012Validator]:
    return {
        reference_mod.MODEL_FILENAME: Draft202012Validator(genschema.load_reference_schema()),
        reference_mod.MAPPINGS_FILENAME: Draft202012Validator(genschema.load_reference_mappings_schema()),
    }


def align(
    root: Path,
    zone: str = "approved",
    references: list[str] | None = None,
) -> AlignmentReport:
    """Align the model in ``zone`` against every reference pack (or the named ones)."""
    if zone not in dsl.ZONES:
        raise AlignmentError(f"unknown zone '{zone}'")
    try:
        packs = reference_mod.load(root, references)
    except reference_mod.ReferenceError as exc:
        raise AlignmentError(str(exc)) from exc

    model, _documents, _config = dsl.load_zone(root, zone)
    local_ids = set(model.elements)
    # What ``approved`` cannot see but a promotion would bring: needed for ALN007, and
    # only loaded when it can change an answer.
    staging_only: set[str] = set()
    if zone == "approved":
        staged, _docs, _cfg = dsl.load_zone(root, "staging")
        staging_only = set(staged.elements) - local_ids

    validators = _schema_validators()
    report = AlignmentReport(root=root, zone=zone)
    findings: list[Finding] = []

    for pack in packs:
        alignment, pack_findings = _align_pack(root, pack, model, local_ids, staging_only, validators)
        report.packs.append(alignment)
        findings += pack_findings

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.locator, f.concept))
    report.findings = findings
    return report


def _align_pack(
    root: Path,
    pack: reference_mod.ReferencePack,
    model: dsl.Model,
    local_ids: set[str],
    staging_only: set[str],
    validators: dict[str, Draft202012Validator],
) -> tuple[PackAlignment, list[Finding]]:
    directory = _rel(root, pack.directory)
    alignment = PackAlignment(name=pack.name, directory=directory)
    findings: list[Finding] = []

    if pack.refused:
        alignment.refused = pack.refused
        findings.append(
            Finding(
                "ALN001",
                SEVERITY_ERROR,
                f"reference pack '{pack.name}' does not match its pinned SHA-256 sums "
                f"({pack.refused}) -- refusing to read it, because coverage measured against "
                "an edited taxonomy is not a measurement. Re-pin only for a deliberate, "
                "reviewed upgrade of the pack (`python -m easkills pin-reference`).",
                file=f"{directory}/{reference_mod.CHECKSUMS_FILENAME}",
                concept=pack.name,
            )
        )
        return alignment, findings

    # ALN000 -- the files must read as a taxonomy and a mapping list.
    taxonomy_unreadable = False
    for doc in pack.documents:
        rel = _rel(root, doc.path)
        is_taxonomy = doc.path.name == reference_mod.MODEL_FILENAME
        if doc.parse_error:
            findings.append(
                Finding("ALN000", SEVERITY_ERROR, f"cannot read file: {doc.parse_error}", file=rel)
            )
            taxonomy_unreadable |= is_taxonomy
            continue
        if doc.data is None:
            continue
        validator = validators.get(doc.path.name)
        if validator is None:
            continue
        for error in sorted(validator.iter_errors(doc.data), key=lambda e: list(e.absolute_path)):
            locator = "/".join(str(p) for p in error.absolute_path) or "(root)"
            findings.append(Finding("ALN000", SEVERITY_ERROR, error.message, file=rel, locator=locator))
            taxonomy_unreadable |= is_taxonomy
    for message, locator in pack.defects:
        findings.append(
            Finding(
                "ALN000",
                SEVERITY_ERROR,
                f"{message} -- the file does not read as a taxonomy",
                file=f"{directory}/{reference_mod.MODEL_FILENAME}",
                locator=locator,
            )
        )

    if not pack.nodes:
        # Silent when the taxonomy did not parse: "declares no nodes" would be a
        # misleading diagnosis of a file that never read, and ALN000 already has it.
        if not taxonomy_unreadable:
            findings.append(
                Finding(
                    "ALN008",
                    SEVERITY_ERROR,
                    f"reference pack '{pack.name}' declares no nodes -- an empty yardstick reports "
                    "full coverage of nothing, which is worse than no yardstick at all",
                    file=f"{directory}/{reference_mod.MODEL_FILENAME}",
                    concept=pack.name,
                )
            )
        return alignment, findings

    mappings_file = f"{directory}/{reference_mod.MAPPINGS_FILENAME}"

    # --------------------------------------------------------------- mapping checks
    by_ref: dict[str, reference_mod.NodeMapping] = {}
    # Node ids for which a finding more specific than ALN004 was already raised; the
    # node still shows as a gap in the table, so completeness is kept without saying
    # the same thing twice.
    diagnosed: set[str] = set()
    for mapping in pack.mappings:
        if mapping.ref in by_ref:
            findings.append(
                Finding(
                    "ALN006",
                    SEVERITY_ERROR,
                    f"a second mapping entry targets reference node '{mapping.ref}' -- one node, "
                    "one recorded judgement; merge the element lists or split the node",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=mapping.ref,
                )
            )
            continue
        by_ref[mapping.ref] = mapping
        if mapping.ref not in pack.nodes:
            findings.append(
                Finding(
                    "ALN002",
                    SEVERITY_ERROR,
                    f"mapping targets '{mapping.ref}', which is not a node of reference "
                    f"'{pack.name}' -- a mapping to nothing is coverage of nothing",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=mapping.ref,
                )
            )
            continue
        if mapping.status == STATUS_OUT_OF_SCOPE and not mapping.rationale.strip():
            findings.append(
                Finding(
                    "ALN005",
                    SEVERITY_ERROR,
                    f"'{mapping.ref}' is declared out-of-scope with no rationale -- out-of-scope is "
                    "a decision somebody signs, and the node is reported as a gap until it carries "
                    "one",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=mapping.ref,
                )
            )
            diagnosed.add(mapping.ref)

    # Which elements of each mapping this zone actually holds.
    resolved: dict[str, list[str]] = {}
    for ref, mapping in by_ref.items():
        if ref not in pack.nodes:
            continue
        here: list[str] = []
        unknown: list[str] = []
        staged: list[str] = []
        for element_id in mapping.elements:
            if element_id in local_ids:
                here.append(element_id)
            elif element_id in staging_only:
                staged.append(element_id)
            else:
                unknown.append(element_id)
        resolved[ref] = here
        for element_id in unknown:
            findings.append(
                Finding(
                    "ALN003",
                    SEVERITY_ERROR,
                    f"mapping for '{ref}' names element '{element_id}', which is not in the "
                    f"{model.zone} model -- check the id, or model it before claiming it as coverage",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=ref,
                )
            )
        if staged and not here:
            findings.append(
                Finding(
                    "ALN007",
                    SEVERITY_WARNING,
                    f"'{ref}' is claimed by staging-only element(s) {', '.join(staged)} while reading "
                    "the approved zone -- the node stays a gap until the proposal is promoted "
                    "(`--zone staging` shows what promotion would close)",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=ref,
                )
            )
            diagnosed.add(ref)
        elif staged:
            findings.append(
                Finding(
                    "ALN007",
                    SEVERITY_WARNING,
                    f"'{ref}' also names staging-only element(s) {', '.join(staged)}; the status "
                    f"reported here rests on the approved element(s) {', '.join(here)} only",
                    file=mappings_file,
                    locator=mapping.locator,
                    concept=ref,
                )
            )
        if unknown and not here and not staged:
            # Every element named is absent: ALN003 already says why this is a gap.
            diagnosed.add(ref)

    # --------------------------------------------------------------- node statuses
    children = pack.children
    excluded_by: dict[str, str] = {}  # node id -> the node whose decision excludes it
    for node_id in pack.order:
        mapping = by_ref.get(node_id)
        if mapping is not None and mapping.status == STATUS_OUT_OF_SCOPE and mapping.rationale.strip():
            excluded_by[node_id] = node_id
            continue
        for ancestor in pack.ancestors(node_id):
            ancestor_mapping = by_ref.get(ancestor)
            if (
                ancestor_mapping is not None
                and ancestor_mapping.status == STATUS_OUT_OF_SCOPE
                and ancestor_mapping.rationale.strip()
            ):
                excluded_by[node_id] = ancestor
                break

    depths = {node_id: len(pack.ancestors(node_id)) for node_id in pack.order}
    for node_id in pack.order:
        node = pack.nodes[node_id]
        mapping = by_ref.get(node_id)
        leaf = not children.get(node_id)
        source = excluded_by.get(node_id, "")
        if source:
            status = STATUS_OUT_OF_SCOPE
            elements: tuple[str, ...] = ()
            note = by_ref[source].note if source == node_id else ""
            rationale = by_ref[source].rationale
            inherited = "" if source == node_id else source
        elif mapping is not None and mapping.status in {STATUS_COVERED, STATUS_PARTIAL} and resolved.get(node_id):
            status = mapping.status
            elements = tuple(resolved[node_id])
            note = mapping.note
            rationale = ""
            inherited = ""
        else:
            status = STATUS_GAP if leaf else STATUS_BRANCH
            elements = ()
            note = mapping.note if mapping is not None else ""
            rationale = ""
            inherited = ""
        alignment.nodes.append(
            NodeAlignment(
                id=node_id,
                name=node.name,
                kind=node.kind,
                parent=node.parent,
                external_id=node.external_id,
                depth=depths[node_id],
                leaf=leaf,
                status=status,
                elements=elements,
                note=note,
                rationale=rationale,
                inherited_from=inherited,
            )
        )
        if leaf and status == STATUS_GAP and node_id not in diagnosed:
            findings.append(
                Finding(
                    "ALN004",
                    SEVERITY_WARNING,
                    f"reference node '{node_id}' ({node.name}) is not mapped to anything and is not "
                    "declared out-of-scope -- either the architecture has a gap here, or the "
                    "decision not to cover it is unrecorded",
                    file=mappings_file if pack.mappings else f"{directory}/{reference_mod.MODEL_FILENAME}",
                    concept=node_id,
                )
            )

    # --------------------------------------------------------------- rollups + info
    by_id = {node.id: node for node in alignment.nodes}
    for node_id in pack.order:
        if not children.get(node_id):
            continue
        subtree = [by_id[child] for child in _descendants(children, node_id) if by_id[child].leaf]
        in_scope = [node for node in subtree if node.status != STATUS_OUT_OF_SCOPE]
        alignment.branches.append(
            BranchRollup(
                id=node_id,
                name=pack.nodes[node_id].name,
                in_scope=len(in_scope),
                out_of_scope=len(subtree) - len(in_scope),
                credit=sum(COVERAGE_WEIGHT.get(node.status, 0.0) for node in in_scope),
            )
        )

    anchored = {element_id for mapping in pack.mappings for element_id in mapping.elements}
    kinds = {node.kind for node in pack.nodes.values()}
    anchorable = {t for kind in kinds for t in KIND_LOCAL_TYPES.get(kind, ())}
    alignment.unanchored = sorted(
        (element.id, element.type, element.name)
        for element in model.elements.values()
        if element.type in anchorable and element.id not in anchored
    )
    return alignment, findings


def _descendants(children: dict[str, list[str]], node_id: str) -> list[str]:
    out: list[str] = []
    stack = list(children.get(node_id, ()))
    seen: set[str] = set()
    while stack:
        current = stack.pop(0)
        if current in seen:
            continue
        seen.add(current)
        out.append(current)
        stack.extend(children.get(current, ()))
    return out
