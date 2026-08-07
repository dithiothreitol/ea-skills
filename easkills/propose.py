"""Findings become staged proposals: gaps into requirements, overlaps into work packages.

Every report in this repository ends in a list a human has to act on. This turns three of
those lists into the *shape* of the action -- a `Requirement` for a reference gap, a
`Constraint` for an open readiness checkpoint, a `WorkPackage` for a rationalization
candidate -- and stops there. A skeleton with the right id, the right binding and an
honest label is real work saved; a skeleton with invented prose in it is a liability,
because the next reader cannot tell it from something an architect wrote.

So the discipline is the importer's, borrowed whole:

* **Nothing is ever overwritten.** An existing file, or an id already in either zone, is a
  refusal -- never a merge and never a rename-with-a-number.
* **Everything lands in `model/staging/`, `assumed: true`,** with a rationale naming the
  finding and the date it was derived from. The promotion gate keeps it out of `approved`
  until a human supplies an owner and a review date, which is exactly the intended
  bottleneck: generation is cheap, vouching is not.
* **Ids are derived, never counted.** `req-<pack>-<node>`, `con-<element>-<code>`,
  `wp-rationalize-<capability>`. Re-running after fixing three of ten findings proposes
  the same seven ids, so the diff is the news rather than a renumbering.
* **Byte-stable for identical inputs**, which is what makes "re-run it and see" safe.

What is deliberately *not* here: the words. Documentation fields carry an explicit
``PROPOSED --`` placeholder naming what the author has to write, and the templates for
writing it live in skill prose (`ea-align`, `ea-adr`), not in this generator. A tool that
guessed at a requirement's business outcome would produce text that reads as authored and
is not, which is the same failure as a fabricated quote one layer up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import (
    alignment,
    dsl,
    genschema,
    impact as impact_mod,
    oracle,
    readiness as readiness_mod,
    reports,
)
from .validate import SEVERITY_WARNING

SOURCES = ("align", "readiness", "overlap", "time")

STAGING_FILENAME = {
    "align": "proposed-requirements.yaml",
    "readiness": "proposed-constraints.yaml",
    "overlap": "proposed-work-packages.yaml",
    "time": "proposed-scheduling.yaml",
}

# The placeholder is loud on purpose. A half-finished stub must not be able to pass for an
# authored requirement in a review, and `PROPOSED --` is greppable across the repository.
PLACEHOLDER = "PROPOSED --"

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")
SLUG_RE = re.compile(genschema.SLUG_PATTERN)
# The authoring schema's own limit. A generated id that violates it produces a file the
# gate rejects, and re-running regenerates the same broken id -- so the operator cannot
# fix it by editing. Refuse instead, naming the finding that would not fit.
MAX_ID_LENGTH = 80


class ProposeRefusal(RuntimeError):
    """A request the generator refuses rather than half-satisfies."""


@dataclass
class Proposal:
    id: str
    type: str
    name: str
    documentation: str
    rationale: str
    applies_to: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)
    origin: str = ""  # the finding this came from, for the report

    def as_element(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "documentation": self.documentation,
        }
        if self.applies_to:
            item["appliesTo"] = list(self.applies_to)
        if self.properties:
            item["properties"] = dict(self.properties)
        # Last, and always both: `assumed` without `rationale` is PROV002, and the
        # rationale is where the provenance of a *generated* concept actually lives --
        # not a source quote, but the finding and the date that produced it.
        item["assumed"] = True
        item["rationale"] = self.rationale
        return item


@dataclass
class ProposeReport:
    root: Path
    source: str
    as_of: str
    target: Path
    proposals: list[Proposal] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    written: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "source": self.source,
            "asOf": self.as_of,
            "target": str(self.target),
            "written": self.written,
            "proposed": len(self.proposals),
            "skipped": self.skipped,
            "elements": [
                {"id": p.id, "type": p.type, "name": p.name, "appliesTo": p.applies_to, "origin": p.origin}
                for p in self.proposals
            ],
        }


def _slug(text: str) -> str:
    """Make an id fragment. An input that is *already* a valid slug passes through.

    That pass-through is what keeps derived ids collision-free: element and node ids are
    slugs by schema, so rewriting them would map `wc-a.b` and `wc-a-b` onto one id and
    produce `ID001` on the generated file -- which a re-run would then reproduce exactly,
    leaving the operator unable to fix it by editing. Only free-form text (a pack's
    directory name) is actually transformed.
    """
    text = text.strip()
    if SLUG_RE.fullmatch(text):
        return text
    out: list[str] = []
    for char in text.lower():
        if char in SLUG_CHARS:
            out.append(char)
        elif char in " _./":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _check_ids(proposals: list[Proposal]) -> None:
    """Every derived id must be a valid, unique slug -- or the run refuses, by name.

    Silently emitting an id the schema rejects would hand the operator a staging file
    that fails the gate and cannot be repaired by editing, because the next run derives
    the same id again. A refusal names the finding whose id would not work, which is
    something a human can act on.
    """
    seen: dict[str, str] = {}
    for proposal in proposals:
        if not SLUG_RE.fullmatch(proposal.id):
            raise ProposeRefusal(
                f"the id derived for {proposal.origin} is not a valid identifier: "
                f"'{proposal.id}'. Rename the source concept, or propose with --reference "
                "restricted to packs whose names are slugs."
            )
        if len(proposal.id) > MAX_ID_LENGTH:
            raise ProposeRefusal(
                f"the id derived for {proposal.origin} is {len(proposal.id)} characters, over the "
                f"{MAX_ID_LENGTH}-character limit the model schema sets: '{proposal.id}'."
            )
        if proposal.id in seen:
            raise ProposeRefusal(
                f"{proposal.origin} and {seen[proposal.id]} both derive the id '{proposal.id}'. "
                "Two proposals sharing one id is ID001 on the generated file; rename one of the "
                "source concepts."
            )
        seen[proposal.id] = proposal.origin


# ------------------------------------------------------------------------ derivation


def _from_align(root: Path, references: list[str] | None) -> list[Proposal]:
    """One `Requirement` per `ALN004`.

    Driven off the *finding*, not off `status == gap`, and the difference is not
    cosmetic. `align` marks a node a gap and then suppresses `ALN004` when a more
    specific code already named the reason -- a staging-only element claiming it
    (`ALN007`), an exclusion missing its rationale (`ALN005`), a mapping pointing at an
    element that does not exist (`ALN003`). Those nodes need the *named* problem fixed,
    not a requirement filed on top of them; and a stub citing an `ALN004` that was never
    raised would be a rationale that is simply false.

    A real gap is a node the model does not answer and nobody excluded, so the honest
    proposal is "we intend to answer it" -- bound to nothing yet, because what will
    satisfy it is precisely the decision nobody has made.
    """
    report = alignment.align(root, zone="approved", references=references)
    if not report.ok:
        # An unparseable mappings file leaves every leaf reading as a gap, and proposing
        # from that writes one requirement per node of the taxonomy. `align` exits 1 on
        # exactly this; a generator that shrugged and produced fifty stubs would be the
        # more damaging of the two responses.
        codes = sorted({f.code for f in report.errors})
        raise ProposeRefusal(
            f"the alignment report has {len(report.errors)} error(s) ({', '.join(codes)}) -- "
            "fix them before proposing. Until the mappings read cleanly, every node looks "
            "like a gap, and the proposal would be one requirement per node of the taxonomy."
        )

    proposals: list[Proposal] = []
    for pack in report.packs:
        if pack.refused:
            continue
        # Per pack, not across all of them: two packs may legitimately share node ids
        # (two versions of one taxonomy is the obvious case), and a gap in one is not a
        # gap in the other. Every ALN004 carries the file it came from, which is inside
        # the pack directory.
        gaps = {
            f.concept
            for f in report.findings
            if f.code == "ALN004" and f.file.startswith(pack.directory)
        }
        for node in pack.nodes:
            if node.id not in gaps:
                continue
            external = f" ({node.external_id})" if node.external_id else ""
            proposals.append(
                Proposal(
                    id=f"req-{_slug(pack.name)}-{_slug(node.id)}",
                    # A control node becomes a Constraint: a control restricts how the
                    # architecture may be built, which is what the ArchiMate type means.
                    # Everything else is a Requirement.
                    type="Constraint" if node.kind == "control" else "Requirement",
                    name=node.name,
                    documentation=(
                        f"{PLACEHOLDER} state the business outcome, the acceptance signal and the "
                        f"binding scope for '{node.name}'{external} from the {pack.name} reference "
                        "model. See ea-align for what a good one says."
                    ),
                    rationale=(
                        f"Derived from ALN004 on reference node '{node.id}' in pack '{pack.name}': "
                        "the model answers it neither by an element nor by a recorded exclusion. "
                        "Complete or delete before promotion."
                    ),
                    properties={"referenceNode": node.id, "referencePack": pack.name},
                    origin=f"ALN004:{pack.name}/{node.id}",
                )
            )
    return proposals


def _from_readiness(root: Path) -> list[Proposal]:
    """One `Constraint` per open readiness checkpoint that names an element.

    A checkpoint is about *this* element, so the proposal binds to it via `appliesTo`
    and the MOT rules keep that binding honest. `RDY010` is skipped: it names a layer,
    not an element, and a constraint bound to nothing is what `MOT001` exists to stop.

    **Warnings only.** An *open* checkpoint is precisely what `readiness --strict` gates
    on, and that counts warnings. The info-level ones are observations that may be
    perfectly fine -- `RDY002` says a capability no reference anchors, which is often the
    business doing something its industry blueprint never heard of. Filing "Close RDY002
    on cap-x" as a constraint would put a backlog item on a correct model.
    """
    report = readiness_mod.analyse(root, zone="approved")
    proposals: list[Proposal] = []
    for finding in report.findings:
        if not finding.concept or finding.severity != SEVERITY_WARNING:
            continue
        proposals.append(
            Proposal(
                id=f"con-{_slug(finding.concept)}-{finding.code.lower()}",
                type="Constraint",
                name=f"Close {finding.code} on {finding.concept}",
                documentation=(
                    f"{PLACEHOLDER} say what closing this checkpoint requires and who decides it. "
                    f"The checkpoint reads: {finding.message}"
                ),
                rationale=(
                    f"Derived from {finding.code} on '{finding.concept}'. A readiness checkpoint is "
                    "not a defect, so this is a proposal to close it, not a claim that it is broken. "
                    "Complete or delete before promotion."
                ),
                applies_to=[finding.concept],
                properties={"readinessCode": finding.code},
                origin=f"{finding.code}:{finding.concept}",
            )
        )
    return proposals


def _from_overlap(root: Path, today: date) -> list[Proposal]:
    """One `WorkPackage` per rationalization candidate, naming its realizers.

    **Not via `appliesTo`, against the phase plan.** `appliesTo` is the Motivation
    layer's applicability selector, and `MOT002` is an *error* on any other layer --
    `WorkPackage` is Implementation & Migration. The plan said to prefill it here; doing
    so produced a staging file that failed the gate the same generator promises its
    output will pass, which is the worse of the two ways to be wrong.

    The rule is also right on the substance. What a work package's relation to a
    component *is* -- it realizes a deliverable that replaces it, it is associated with
    it, it triggers its retirement -- is the design decision the package exists to take.
    A generator picking one would be answering the question it was asked to raise. So
    the realizers are recorded as a property and named in the placeholder, and the author
    draws the relationship they meant once they know which it is.
    """
    data = reports.debt(root, today=today)
    proposals: list[Proposal] = []
    for item in data["items"]:
        if item["kind"] != "rationalization-candidate":
            continue
        realizers = [r["id"] for r in item.get("realizers", ())]
        proposals.append(
            Proposal(
                id=f"wp-rationalize-{_slug(item['concept'])}",
                type="WorkPackage",
                name=f"Rationalize {item['concept']}",
                documentation=(
                    f"{PLACEHOLDER} decide the outcome before scoping the work: consolidate onto one "
                    f"realizer ({', '.join(realizers)}), keep the redundancy on purpose -- which needs "
                    "an ADR naming the reason -- or split the capability because it is drawn too "
                    "coarse. The tool cannot tell drift from design; see ea-change-triage. Then draw "
                    f"the relationship this package has to {', '.join(realizers)}, which the decision "
                    "above determines and this stub deliberately does not guess."
                ),
                rationale=(
                    f"Derived from the debt register's rationalization-candidate on '{item['concept']}' "
                    f"as of {today.isoformat()}: {item['detail']}. Complete or delete before promotion."
                ),
                # A property, not `appliesTo`: see the docstring. Comma-joined because the
                # property map takes scalars, and the ids are also in the documentation
                # where a human reads them.
                properties={"rationalizes": ", ".join(realizers)},
                origin=f"rationalization-candidate:{item['concept']}",
            )
        )
    return proposals


def _from_time(root: Path, today: date) -> list[Proposal]:
    """One `WorkPackage` per portfolio decision nothing schedules.

    **Not a `Plateau`, against the phase plan** -- and caught before shipping this time,
    which is the only value of having learned it in 7.6. `PLAT001` makes a plateau
    without a `plateauDate` an *error*, so a generated plateau stub would fail the gate
    this command promises its output passes. Supplying the date instead is worse: a
    plateau date is a claim about when a target state is reached, and inventing one puts
    a schedule nobody agreed into the model.

    So the generator produces the *work of scheduling*, and the human creates the
    plateau once they have decided the date. Ordered by blast radius, then id: the
    element whose change reaches furthest is the one to schedule first, and that
    ordering is the only piece of judgement here a tool can actually supply.
    """
    unscheduled = reports.roadmap(root, today=today)["unscheduledIntent"]
    if not unscheduled:
        return []

    radius: dict[str, int] = {}
    for row in unscheduled:
        try:
            radius[row["id"]] = len(impact_mod.analyse(root, scope=row["id"], today=today).affected)
        except impact_mod.ImpactError:
            radius[row["id"]] = 0  # unreachable in practice; never a crash in a generator

    ordered = sorted(unscheduled, key=lambda row: (-radius[row["id"]], row["id"]))
    proposals: list[Proposal] = []
    for row in ordered:
        disposition = row["timeDisposition"]
        proposals.append(
            Proposal(
                id=f"wp-schedule-{_slug(row['id'])}",
                type="WorkPackage",
                name=f"Schedule the {disposition.lower()} of {row['name']}",
                documentation=(
                    f"{PLACEHOLDER} decide when '{row['name']}' is {disposition.lower()}d, then put it "
                    "in a Plateau with a plateauDate -- that is what turns the disposition into a "
                    f"plan and closes PLAT005. Its blast radius is {radius[row['id']]} element(s); "
                    "schedule the wide ones first, or accept in writing that you are not. If the "
                    "disposition is no longer true, the honest fix is to change it rather than to "
                    "schedule work nobody intends to do."
                ),
                rationale=(
                    f"Derived from PLAT005 on '{row['id']}' as of {today.isoformat()}: "
                    f"timeDisposition is '{disposition}' and no Plateau includes it. "
                    "Complete or delete before promotion."
                ),
                properties={"timeDisposition": disposition, "blastRadius": str(radius[row["id"]])},
                origin=f"PLAT005:{row['id']}",
            )
        )
    return proposals


# ---------------------------------------------------------------------------- writing


HEADER = """\
# {role}, generated by `python -m easkills propose --from {source} --as-of {as_of}`.
#
# These are *skeletons in staging*, not authored content. Every one is `assumed: true`
# with a rationale naming the finding it came from, and every documentation field opens
# with `{placeholder}` -- which is what stops a half-finished stub from reading as
# something an architect wrote. Promotion runs the normal gate, so an owner and a review
# date are still a human's to supply.
#
# The honest dispositions are: complete it, or delete it. Leaving it here unchanged is
# neither, and the next reader cannot tell that from work in progress.
#
# Re-running proposes the same ids for the same findings, so a second run after fixing
# some of them shows the remainder as the diff rather than renumbering everything.
"""


class _Dumper(yaml.SafeDumper):
    """Sequences indented under their key, matching every hand-authored file here."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: D102
        return super().increase_indent(flow, False)


# Long prose goes out as a folded block (`>`), the way every hand-authored file in this
# repository writes documentation. The default single-quoted scalar doubles every
# apostrophe inside it -- and these stubs quote finding messages that are full of
# 'element-id' quotes, so the first thing an author has to do would be un-escaping the
# text they came to edit. A generated file nobody wants to open is a generated file
# nobody completes.
def _represent_str(dumper: yaml.SafeDumper, value: str):
    style = ">" if len(value) > 80 and "\n" not in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def _existing_ids(root: Path) -> dict[str, str]:
    """Every id already present in either zone, with the zone it is in.

    Both zones, deliberately: proposing an id that already exists in staging would
    collide on promotion, and proposing one that exists in `approved` would look like an
    update proposal for a concept nobody meant to touch.
    """
    known: dict[str, str] = {}
    for zone in ("approved", "staging"):
        try:
            model, _documents, _config = dsl.load(root, zone)
        except Exception:  # noqa: BLE001 -- an unreadable zone is the gate's problem, not ours
            continue
        for identifier in list(model.elements) + list(model.relationships):
            known.setdefault(identifier, zone)
    return known


def propose(
    root: Path,
    source: str,
    as_of: date,
    references: list[str] | None = None,
    out: Path | None = None,
    dry_run: bool = False,
) -> ProposeReport:
    if source not in SOURCES:
        raise ProposeRefusal(f"unknown source '{source}'; expected one of {', '.join(SOURCES)}")

    target = out or (root / "model" / "staging" / STAGING_FILENAME[source])
    report = ProposeReport(root=root, source=source, as_of=as_of.isoformat(), target=target)

    if source == "align":
        candidates = _from_align(root, references)
    elif source == "readiness":
        candidates = _from_readiness(root)
    elif source == "overlap":
        candidates = _from_overlap(root, as_of)
    else:
        candidates = _from_time(root, as_of)

    # Belt and braces on the rule that produced the worst defect in this module: a stub
    # carrying `appliesTo` on a non-Motivation type is MOT002, an *error*, so the file
    # would fail the gate this generator promises its output passes. Checked centrally
    # rather than per source, because the next source added is where it would recur.
    for candidate in candidates:
        if candidate.applies_to and oracle.layer_of(candidate.type) != "Motivation":
            raise ProposeRefusal(
                f"internal: {candidate.origin} would bind appliesTo on a {candidate.type}, which "
                "is not a Motivation-layer element (MOT002). Model that dependency as a "
                "relationship instead."
            )
    _check_ids(candidates)

    known = _existing_ids(root)
    # Source order, not id order. Every source enumerates deterministically (taxonomy
    # order, sorted findings, sorted items), and one of them enumerates *meaningfully*:
    # `--from time` sorts by blast radius so the widest change is proposed first. Sorting
    # by id here silently threw that away -- the ordering the plan asked for, defeated by
    # a line meant only to make the output stable.
    for candidate in candidates:
        zone = known.get(candidate.id)
        if zone is not None:
            # Not an error and not an overwrite: the id existing means somebody already
            # acted on this finding. Saying so by name is more useful than either
            # silently skipping it or refusing the whole run over it.
            report.skipped.append(
                {"id": candidate.id, "reason": f"already exists in model/{zone}/", "origin": candidate.origin}
            )
            continue
        report.proposals.append(candidate)

    if not report.proposals:
        return report

    if target.exists():
        raise ProposeRefusal(
            f"{target} already exists -- propose never overwrites. Complete or delete what is "
            "in it, or pass --out to write elsewhere."
        )
    if dry_run:
        return report

    body = yaml.dump(
        {"elements": [p.as_element() for p in report.proposals]},
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=98,
    )
    header = HEADER.format(
        role=_ROLE[source], source=source, as_of=as_of.isoformat(), placeholder=PLACEHOLDER
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(header + "\n" + body, encoding="utf-8", newline="\n")
    report.written = True
    return report


_ROLE = {
    "align": "Requirements proposed for unanswered reference nodes",
    "readiness": "Constraints proposed for open readiness checkpoints",
    "overlap": "Work packages proposed for rationalization candidates",
    "time": "Work packages proposed for portfolio decisions nothing schedules",
}


def render(report: ProposeReport) -> str:
    from . import ui

    lines = [
        ui.bold(f"Proposals from {report.source} -- as of {report.as_of} at {report.root}"),
        "",
    ]
    if not report.proposals and not report.skipped:
        lines += [
            ui.green(f"{ui.check()} Nothing to propose: that source reported no findings to act on."),
            "",
            ui.verdict(True, 0, 0),
        ]
        return "\n".join(lines)

    for proposal in report.proposals:
        binding = ", ".join(proposal.applies_to) or ui.dim("binds nothing yet")
        lines.append(f"  {ui.bold('{:<44}'.format(proposal.id))} {ui.cyan(proposal.type)}")
        lines.append(f"      {ui.dim('from ' + proposal.origin)}  ->  {binding}")
    if report.skipped:
        lines.append("")
        lines.append(ui.bold("Already acted on"))
        for skipped in report.skipped:
            lines.append(f"  {ui.dim('{:<44}'.format(skipped['id']))} {skipped['reason']}")
    lines.append("")
    if not report.proposals:
        # Every finding already has its skeleton. Re-running is a no-op that says so --
        # the derived ids are what make that possible, and printing "0 would be written"
        # with the placeholder advice underneath would read as something going wrong.
        lines.append(
            ui.green(
                f"{ui.check()} Nothing new to propose: every finding this source reports already "
                "has a proposal in the model."
            )
        )
    else:
        lines.append(
            ui.green(f"{ui.check()} {len(report.proposals)} skeleton(s) written to {report.target}")
            if report.written
            else ui.yellow(f"{len(report.proposals)} skeleton(s) would be written to {report.target}")
        )
        lines.append(
            ui.dim(
                f"Every one is `assumed: true` and opens with `{PLACEHOLDER}`. Complete it or delete "
                "it -- leaving it unchanged is neither, and promotion will not take it without an "
                "owner and a review date."
            )
        )
    lines += ["", ui.verdict(True, 0, 0)]
    return "\n".join(lines)
