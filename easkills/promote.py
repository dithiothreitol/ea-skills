"""Promote staging content into the approved zone -- the only write path (AD-02).

The gate is ``validate.validate_promotion``: approved plus the selected staging files,
judged by approved-zone standards (governance metadata mandatory, every semantic rule
on). Only when that merged result is error-free do files move. The move itself is a
plain filesystem rename mirrored under ``model/approved/``, so the git diff *is* the
promotion record -- reviewable, revertable, and signed by whoever commits it.

Deliberately not here: any automatic stamping of ``owner`` or ``lastReviewed``.
Promotion asserts that a human reviewed the content; the gate forces that evidence
to exist in the staging files *before* the move rather than fabricating it during.

Since 0.22.0 a promotion also writes an approval record (``seal.py``): who signed, when,
and the SHA-256 of every file it moved, so approved content that later changes by any
other route fails the model gate (``APR001``). ``--approved-by`` and ``--as-of`` are
therefore required for a real promotion -- the record is a committed artifact, so its date
is never the wall clock (the rule ``propose`` follows for the same reason).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import dsl, seal, ui
from . import validate as validate_mod


class PromoteError(RuntimeError):
    pass


@dataclass
class PromoteResult:
    root: Path
    report: validate_mod.Report
    dry_run: bool
    # (staging-relative repo path, approved-relative repo path) for each file.
    moves: list[tuple[str, str]] = field(default_factory=list)
    # Approved files this promotion overwrites, and the approved concept ids that
    # disappear with them -- a replacement is a deletion of whatever it leaves out.
    replaced: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    moved: bool = False
    record: Path | None = None  # the approval record a real promotion wrote

    @property
    def ok(self) -> bool:
        return self.report.ok

    def render(self) -> str:
        lines = [self.report.render(), ""]
        if not self.ok:
            lines.append(ui.red(ui.bold("Promotion blocked: the merged result must validate cleanly first.")))
            return "\n".join(lines)
        verb = "Would move" if not self.moved else "Moved"
        for source, target in self.moves:
            note = ui.yellow("  (replaces the approved file)") if target in self.replaced else ""
            lines.append(f"{ui.green(verb)}  {ui.dim(source)}  {ui.arrow()}  {ui.bold(target)}{note}")
        if self.dropped:
            lines.append(
                ui.yellow(
                    f"{ui.warning_sign()} replacing those files removes {len(self.dropped)} approved "
                    f"concept(s): {', '.join(self.dropped)}"
                )
            )
            lines.append(
                ui.dim(
                    "   The gate validated the result *after* the replacement, so nothing is left "
                    "dangling -- but these are deletions, and the commit signs for them."
                )
            )
        if not self.moved:
            lines.append(ui.dim("Dry run: nothing was moved, and no approval record was written."))
        else:
            lines.append(ui.green(f"{ui.check()} {len(self.moves)} file(s) promoted."))
            if self.record is not None:
                lines.append(f"Approval record: {ui.bold(self.record.relative_to(self.root).as_posix())}")
            lines.append(
                ui.dim(
                    "Review the diff and commit the moved files together with the record -- the "
                    "commit is who signed, the record is what the gate checks from now on."
                )
            )
        return "\n".join(lines)


def staging_files(root: Path) -> list[Path]:
    directory = dsl.zone_dir(root, "staging")
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in {".yaml", ".yml"})


def _resolve_selection(root: Path, files: list[Path] | None) -> list[Path]:
    everything = staging_files(root)
    if not files:
        if not everything:
            raise PromoteError("nothing to promote: model/staging/ has no YAML files")
        return everything
    staging_dir = dsl.zone_dir(root, "staging").resolve()
    selected: list[Path] = []
    for given in files:
        path = (given if given.is_absolute() else root / given).resolve()
        if not path.is_file():
            raise PromoteError(f"staging file not found: {given}")
        try:
            path.relative_to(staging_dir)
        except ValueError:
            raise PromoteError(f"not a staging file (must live under model/staging/): {given}")
        selected.append(path)
    return sorted(selected)


def _dropped_concepts(root: Path, selected: list[Path], today: date | None = None) -> list[str]:
    """Approved ids that exist now and would not exist after this promotion.

    A staging file replaces the approved file of the same name, so anything the
    approved file held and the staging file leaves out is deleted. The gate validates
    the post-move result, so nothing is left dangling -- but a deletion must still be
    visible to whoever signs the commit, not discovered later in a diff.
    """
    before, _docs, _config = dsl.load(root, "approved")
    after, _docs, _config = dsl.load_merged(root, selected, zone_label="approved")
    gone = (set(before.elements) | set(before.relationships) | set(before.views)) - (
        set(after.elements) | set(after.relationships) | set(after.views)
    )
    return sorted(gone)


def _signature(approved_by: str | None, as_of: str | None) -> tuple[str, str]:
    """Who signs and when, both required for anything that writes an approval record."""
    who = (approved_by or "").strip()
    day = (as_of or "").strip()
    if not who or not day:
        raise PromoteError(
            "a promotion writes an approval record, which needs --approved-by <who signs> and "
            "--as-of <YYYY-MM-DD>: the record says who signed and when, and its date is never "
            "taken from the clock (run with --dry-run to see the plan without signing)"
        )
    try:
        date.fromisoformat(day)
    except ValueError:
        raise PromoteError(f"--as-of must be a real date in YYYY-MM-DD form, got {day!r}") from None
    return who, day


def promote(
    root: Path,
    files: list[Path] | None = None,
    dry_run: bool = False,
    today: date | None = None,
    approved_by: str | None = None,
    as_of: str | None = None,
) -> PromoteResult:
    """Validate approved+selected staging as approved; on a clean gate, move the files
    and write the approval record that vouches for them."""
    if not dry_run:
        approved_by, as_of = _signature(approved_by, as_of)
    selected = _resolve_selection(root, files)
    if not dry_run:
        _refuse_half_seal(root, selected)
    report = validate_mod.validate_promotion(root, staging_paths=selected, today=today)

    staging_dir = dsl.zone_dir(root, "staging").resolve()
    approved_dir = dsl.zone_dir(root, "approved")
    shadowed = dsl.shadowed_approved_files(root, selected)
    moves: list[tuple[str, str]] = []
    replaced: list[str] = []
    for path in selected:
        relative = path.relative_to(staging_dir)
        source_rel = str((Path("model") / "staging" / relative)).replace("\\", "/")
        target_rel = str((Path("model") / "approved" / relative)).replace("\\", "/")
        moves.append((source_rel, target_rel))
        if (approved_dir / relative).resolve() in shadowed:
            replaced.append(target_rel)

    result = PromoteResult(
        root=root,
        report=report,
        dry_run=dry_run,
        moves=moves,
        replaced=replaced,
        dropped=_dropped_concepts(root, selected, today=today),
    )
    if not report.ok or dry_run:
        return result

    # Everything the record says is computed before a file moves -- the merged model is the
    # post-move truth the gate just judged -- and the record is written first. A failure
    # writing it leaves staging untouched; a failure while moving rolls the moves back and
    # removes the record, so no file is ever in the approved zone without its signature.
    _before_model, before_docs, _config = dsl.load(root, "approved")
    before = seal.concept_definitions(before_docs)
    after_model, after_docs, _config = dsl.load_merged(root, selected, zone_label="approved")
    after = seal.concept_definitions(after_docs)
    staged = {path.resolve() for path in selected}
    assumed = [
        concept.id
        for concept in [*after_model.elements.values(), *after_model.relationships.values()]
        if concept.assumed and concept.source_path is not None and concept.source_path.resolve() in staged
    ]
    targets = [approved_dir / path.relative_to(staging_dir) for path in selected]
    result.record = seal.write_record(
        root,
        kind="promotion",
        approved_by=approved_by,
        day=as_of,
        files=selected,
        paths=[seal.relative(root, target) for target in targets],
        added=sorted(set(after) - set(before)),
        changed=sorted(i for i in set(after) & set(before) if after[i] != before[i]),
        removed=sorted(set(before) - set(after)),
        assumptions=assumed,
    )
    # Every rename that completed, (source, destination), in the order it ran. A replaced
    # approved file is set aside, not overwritten, until every move has succeeded; undoing
    # means reversing the renames last-first, which puts each file exactly where it was.
    done: list[tuple[Path, Path]] = []
    try:
        for path, target in zip(selected, targets):
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                backup = target.with_name(target.name + ".promote-backup")
                os.replace(target, backup)
                done.append((target, backup))
            os.replace(path, target)
            done.append((path, target))
    except OSError as exc:
        for source, destination in reversed(done):
            os.replace(destination, source)
        result.record.unlink(missing_ok=True)
        result.record = None
        raise PromoteError(f"the promotion could not move its files ({exc}); nothing was moved") from None
    for _source, destination in done:
        if destination.name.endswith(".promote-backup"):
            destination.unlink(missing_ok=True)
    result.moved = True
    return result


def _refuse_half_seal(root: Path, selected: list[Path]) -> None:
    """Refuse a first promotion that would vouch for some approved files and not others.

    A repository with approved content and no record yet is unsealed: the gate says so,
    as information. A promotion there writes the first record -- and if it vouched only
    for the files it moved, every other approved file would fail APR001 at once while
    ``--seal-existing`` refused to run, because a record exists. So the first signature
    of an existing zone is the seal, given deliberately, and promotion comes after it.
    """
    if seal.record_files(root):
        return
    staging_dir = dsl.zone_dir(root, "staging").resolve()
    replaced = {seal.relative(root, dsl.zone_dir(root, "approved") / p.relative_to(staging_dir)) for p in selected}
    unsealed = [f for f in seal.approved_files(root) if seal.relative(root, f) not in replaced]
    if unsealed:
        raise PromoteError(
            f"the approved zone holds {len(unsealed)} file(s) no approval record vouches for yet. Seal what "
            "it already holds first -- `easkills promote --seal-existing --approved-by <who> --as-of <date>` "
            "-- on the decision of whoever signs for it, then promote; a first record that vouched only "
            "for this promotion would leave the rest failing APR001"
        )


@dataclass
class SealResult:
    root: Path
    report: validate_mod.Report
    dry_run: bool
    files: list[str] = field(default_factory=list)
    record: Path | None = None

    @property
    def ok(self) -> bool:
        return self.report.ok

    def render(self) -> str:
        lines = [self.report.render(), ""]
        if not self.ok:
            lines.append(ui.red(ui.bold("Seal refused: the approved zone must validate cleanly before it is sealed.")))
            return "\n".join(lines)
        if self.record is None:
            lines.append(f"Would seal {len(self.files)} approved file(s). " + ui.dim("Dry run: no record was written."))
            return "\n".join(lines)
        lines.append(
            ui.green(f"{ui.check()} Sealed {len(self.files)} approved file(s): ")
            + ui.bold(self.record.relative_to(self.root).as_posix())
        )
        lines.append(
            ui.dim(
                "This is the initial record of a repository adopting the seal. Commit it; from now on "
                "approved content that changes outside `easkills promote` fails `validate` (APR001)."
            )
        )
        return "\n".join(lines)


def seal_existing(
    root: Path, approved_by: str | None, as_of: str | None, dry_run: bool = False, today: date | None = None
) -> SealResult:
    """Write the one initial record vouching for everything the approved zone holds now.

    Refuses when any record already exists: sealing again would vouch for whatever changed
    since the last record, which is the exact laundering the seal exists to prevent.
    """
    if not dry_run:
        approved_by, as_of = _signature(approved_by, as_of)
    if seal.record_files(root):
        raise PromoteError(
            "the approved zone is already sealed (governance-log/approvals/ holds records); "
            "--seal-existing writes the first record only -- sealing again would vouch for "
            "whatever changed since, unsigned"
        )
    files = seal.approved_files(root)
    if not files:
        raise PromoteError("nothing to seal: model/approved/ holds no YAML files")
    report = validate_mod.validate(root, zone="approved", today=today)
    result = SealResult(root=root, report=report, dry_run=dry_run, files=[seal.relative(root, f) for f in files])
    if not report.ok or dry_run:
        return result
    result.record = seal.write_record(root, kind="seal", approved_by=approved_by, day=as_of, files=files)
    return result
