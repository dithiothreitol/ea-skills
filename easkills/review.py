"""The review sheet: every staged claim beside its evidence, weakest first (D5).

A promotion asserts that a person read what they sign. The gate proves the staged model
is well formed and that every quote exists; it cannot prove the quote supports the claim
-- that is entailment, and the cheapest place to check it is the eyes of the person
signing. Until now they had to assemble the comparison themselves: open the staged YAML,
follow each ``fact:`` into the register, follow each quote into its source, find the
line. Nobody does that for forty concepts, so in practice a promotion signed a file list.

``easkills review`` does the assembling and nothing else. Per staged concept: what it
claims (type, name, endpoints, documentation), and each piece of evidence with its file
and line -- through which fact, and with the fact's confidence. Claims are grouped
weakest first: no evidence at all (``assumed``), evidence the sources dispute
(``contested``), evidence only implied, quotes that match only approximately, and
finally plain verbatim quotes. The sheet opens with what the promotion would change on
disk, replaced files and deleted concepts included, because a deletion is a signed
decision too.

It decides nothing and writes nothing but the sheet. Deterministic: no date, no clock,
the same bytes for the same repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import dsl, facts as facts_mod, intake, promote as promote_mod
from .validate import _normalize, _quote_match

STRENGTHS = ("missing", "assumed", "contested", "implied", "approximate", "quoted")
HEADINGS = {
    "missing": "Evidence that cannot be located",
    "assumed": "No evidence -- declared assumptions",
    "contested": "Evidence the sources dispute",
    "implied": "Evidence only implied",
    "approximate": "Quotes that match only approximately",
    "quoted": "Verbatim evidence",
}
EXPLANATIONS = {
    "missing": "A quote the source does not contain; the gate refuses these, and so should you.",
    "assumed": "Promoting one of these accepts it on the signer's word -- say so in the commit.",
    "contested": "The model follows one side of a disagreement; the other side is quoted in the register.",
    "implied": "The quote supports the claim only indirectly; read whether you would draw the same inference.",
    "approximate": "The quote differs from its source in wording; read both.",
    "quoted": "Read whether each quote says what the claim says. The gate checked it exists, not that.",
}


@dataclass
class Evidence:
    quote: str
    file: str
    line: str  # "12" or "12-14", or "" when the quote is not located exactly
    verdict: str  # exact | approx | missing
    via: str = ""  # fact id
    confidence: str = ""  # the fact's confidence, when via a fact
    contests: list[str] = field(default_factory=list)


@dataclass
class Claim:
    id: str
    kind: str  # element | relationship
    type: str
    name: str
    file: str
    documentation: str = ""
    source: str = ""
    target: str = ""
    rationale: str = ""
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def strength(self) -> str:
        if not self.evidence:
            return "assumed"
        verdicts = {e.verdict for e in self.evidence}
        if "missing" in verdicts:
            return "missing"
        if any(e.confidence == "contested" for e in self.evidence):
            return "contested"
        if any(e.confidence == "implied" for e in self.evidence):
            return "implied"
        if "approx" in verdicts:
            return "approximate"
        return "quoted"


@dataclass
class Sheet:
    root: Path
    name: str
    moves: list[tuple[str, str, bool]] = field(default_factory=list)  # staged, approved, replaces
    removed: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    views: list[tuple[str, str, str]] = field(default_factory=list)  # id, name, file


class ReviewError(RuntimeError):
    pass


def _locator(root: Path, facts_root: Path, threshold: float, cache: dict) -> callable:
    def locate(file: str, quote: str) -> tuple[str, str]:
        path, _problem = dsl.resolve_provenance_file(root, facts_root, file)
        if path is None or not path.is_file():
            return "", "missing"
        if path not in cache:
            # One fold per source: the coverage index is the matcher's normal form with a
            # line number per character, so it serves as the haystack and the locator both.
            cache[path] = intake._index_source(path.read_text(encoding="utf-8", errors="replace"))
        norm, lines, _paras = cache[path]
        needle = _normalize(quote)
        verdict = _quote_match(norm, needle, threshold)
        if verdict != "exact":
            return "", verdict
        position = norm.find(needle)
        first, last = lines[position], lines[min(position + len(needle), len(lines)) - 1]
        return (str(first) if first == last else f"{first}-{last}"), "exact"

    return locate


def review(root: Path, files: list[Path] | None = None) -> Sheet:
    """Assemble the sheet for the staged files that ``promote`` would move."""
    try:
        selected = promote_mod._resolve_selection(root, files)
    except promote_mod.PromoteError as exc:
        raise ReviewError(str(exc)) from None
    model, _docs, config = dsl.load_merged(root, selected, zone_label="approved")
    register, _rdocs, _entities = facts_mod.load(root)
    threshold, _problem = dsl.config_number(config, "quoteMatchThreshold", 0.90, minimum=0.0, maximum=1.0)
    locate = _locator(root, model.facts_root(), threshold, {})

    sheet = Sheet(root=root, name=model.name)
    staging_dir = dsl.zone_dir(root, "staging").resolve()
    approved_dir = dsl.zone_dir(root, "approved")
    shadowed = dsl.shadowed_approved_files(root, selected)
    for path in selected:
        relative = path.relative_to(staging_dir)
        target = approved_dir / relative
        sheet.moves.append(
            (
                (Path("model") / "staging" / relative).as_posix(),
                (Path("model") / "approved" / relative).as_posix(),
                target.resolve() in shadowed,
            )
        )
    sheet.removed = promote_mod._dropped_concepts(root, selected)

    staged = {p.resolve() for p in selected}
    for concept in [*model.elements.values(), *model.relationships.values()]:
        if concept.source_path is None or concept.source_path.resolve() not in staged:
            continue
        is_relationship = isinstance(concept, dsl.Relationship)
        claim = Claim(
            id=concept.id,
            kind="relationship" if is_relationship else "element",
            type=concept.type,
            name=concept.name,
            file=concept.source_path.relative_to(root).as_posix(),
            documentation=concept.documentation,
            source=getattr(concept, "source", "") if is_relationship else "",
            target=getattr(concept, "target", "") if is_relationship else "",
            rationale=concept.rationale if concept.assumed else "",
        )
        for provenance in concept.provenance:
            if provenance.fact:
                fact = register.facts.get(provenance.fact)
                if fact is None:
                    claim.evidence.append(Evidence("", "", "", "missing", via=provenance.fact))
                    continue
                for item in fact.provenance:
                    line, verdict = locate(item.file, item.quote)
                    claim.evidence.append(
                        Evidence(
                            item.quote, item.file, line, verdict, via=fact.id,
                            confidence=fact.confidence, contests=sorted(fact.contests),
                        )
                    )
            elif provenance.file:
                line, verdict = locate(provenance.file, provenance.quote)
                claim.evidence.append(Evidence(provenance.quote, provenance.file, line, verdict))
        sheet.claims.append(claim)
    for view in model.views.values():
        if view.source_path is not None and view.source_path.resolve() in staged:
            sheet.views.append((view.id, view.name, view.source_path.relative_to(root).as_posix()))
    sheet.claims.sort(key=lambda c: (STRENGTHS.index(c.strength), c.file, c.kind, c.id))
    sheet.views.sort()
    return sheet


def _quote(text: str) -> str:
    return " ".join(text.split())


def markdown(sheet: Sheet) -> str:
    lines = [
        "# Review sheet",
        "",
        f"**{sheet.name}** -- the staged content `easkills promote` would move, read against the "
        "approved zone.",
        "",
        "> Every staged claim beside its evidence, weakest first. This sheet decides nothing: the "
        "promotion is `easkills promote --approved-by <who> --as-of <date>`, run by the person "
        "who read it, and the commit that carries it is the signature.",
        "",
        "## What the promotion changes",
        "",
        "| Staged file | Lands as | |",
        "|---|---|---|",
    ]
    for staged, approved, replaces in sheet.moves:
        lines.append(f"| `{staged}` | `{approved}` | {'replaces the approved file' if replaces else 'new file'} |")
    lines.append("")
    if sheet.removed:
        lines.append(
            "**Deleted from the approved zone** (a replacement file leaves them out): "
            + ", ".join(f"`{concept}`" for concept in sheet.removed)
        )
    else:
        lines.append("Nothing is deleted from the approved zone.")
    counts = {strength: sum(1 for c in sheet.claims if c.strength == strength) for strength in STRENGTHS}
    lines += [
        "",
        "| Evidence | Claims |",
        "|---|---|",
        *(f"| {HEADINGS[s]} | {counts[s]} |" for s in STRENGTHS if counts[s]),
        "",
    ]
    for strength in STRENGTHS:
        group = [c for c in sheet.claims if c.strength == strength]
        if not group:
            continue
        lines += [f"## {HEADINGS[strength]} ({len(group)})", "", EXPLANATIONS[strength], ""]
        for claim in group:
            if claim.kind == "relationship":
                title = f"### `{claim.id}` -- {claim.type} `{claim.source}` -> `{claim.target}`"
            else:
                title = f"### `{claim.id}` -- {claim.type} \"{claim.name}\""
            lines += [title, "", f"*{claim.file}*", ""]
            if claim.documentation:
                lines += [_quote(claim.documentation), ""]
            if claim.rationale:
                lines.append(f"- **Assumed:** {_quote(claim.rationale)}")
            for evidence in claim.evidence:
                if not evidence.quote:
                    lines.append(f"- cites `{evidence.via}`, which is not in the fact register")
                    continue
                label = " lines " if "-" in evidence.line else " line "
                where = f"`{evidence.file}`" + (f"{label}{evidence.line}" if evidence.line else "")
                if evidence.verdict != "exact":
                    where += " -- " + ("matches only approximately" if evidence.verdict == "approx" else "not found in the source")
                via = ""
                if evidence.via:
                    via = f", via `{evidence.via}`"
                    if evidence.confidence in {"contested", "implied"}:
                        via += f" ({evidence.confidence}"
                        if evidence.contests:
                            via += ": disputes " + ", ".join(f"`{c}`" for c in evidence.contests)
                        via += ")"
                lines.append(f"- \"{_quote(evidence.quote)}\" -- {where}{via}")
            lines.append("")
    if sheet.views:
        lines += ["## Views", "", "Views carry no evidence of their own: they show the concepts above.", ""]
        lines += [f"- `{view_id}` \"{name}\" -- *{file}*" for view_id, name, file in sheet.views]
        lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"
