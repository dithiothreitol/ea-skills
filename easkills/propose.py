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

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import alignment, dsl, readiness as readiness_mod, reports

SOURCES = ("align", "readiness", "overlap")

STAGING_FILENAME = {
    "align": "proposed-requirements.yaml",
    "readiness": "proposed-constraints.yaml",
    "overlap": "proposed-work-packages.yaml",
}

# The placeholder is loud on purpose. A half-finished stub must not be able to pass for an
# authored requirement in a review, and `PROPOSED --` is greppable across the repository.
PLACEHOLDER = "PROPOSED --"

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


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
    out: list[str] = []
    for char in text.strip().lower():
        if char in SLUG_CHARS:
            out.append(char)
        elif char in " _./":
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


# ------------------------------------------------------------------------ derivation


def _from_align(root: Path, references: list[str] | None) -> list[Proposal]:
    """One `Requirement` per reference node that came back a gap.

    A gap is a node the model does not answer and nobody excluded, so the honest
    proposal is "we intend to answer it" -- a requirement, bound to nothing yet, because
    what will satisfy it is precisely the decision nobody has made.
    """
    report = alignment.align(root, zone="approved", references=references)
    proposals: list[Proposal] = []
    for pack in report.packs:
        if pack.refused:
            continue
        for node in pack.nodes:
            if node.status != alignment.STATUS_GAP:
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
    """
    report = readiness_mod.analyse(root, zone="approved")
    proposals: list[Proposal] = []
    for finding in report.findings:
        if not finding.concept:
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
    """One `WorkPackage` per rationalization candidate, bound to its realizers.

    `appliesTo` is prefilled here and nowhere else in this module, because it is the one
    case where the finding already knows the answer: the elements a rationalization
    touches *are* the realizers the query named.
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
                    "coarse. The tool cannot tell drift from design; see ea-change-triage."
                ),
                rationale=(
                    f"Derived from the debt register's rationalization-candidate on '{item['concept']}' "
                    f"as of {today.isoformat()}: {item['detail']}. Complete or delete before promotion."
                ),
                applies_to=realizers,
                origin=f"rationalization-candidate:{item['concept']}",
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
    else:
        candidates = _from_overlap(root, as_of)

    known = _existing_ids(root)
    for candidate in sorted(candidates, key=lambda p: p.id):
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
