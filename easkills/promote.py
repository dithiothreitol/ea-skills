"""Promote staging content into the approved zone -- the only write path (AD-02).

The gate is ``validate.validate_promotion``: approved plus the selected staging files,
judged by approved-zone standards (governance metadata mandatory, every semantic rule
on). Only when that merged result is error-free do files move. The move itself is a
plain filesystem rename mirrored under ``model/approved/``, so the git diff *is* the
promotion record -- reviewable, revertable, and signed by whoever commits it.

Deliberately not here: any automatic stamping of ``owner`` or ``lastReviewed``.
Promotion asserts that a human reviewed the content; the gate forces that evidence
to exist in the staging files *before* the move rather than fabricating it during.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import dsl, ui
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
            lines.append(ui.dim("Dry run: nothing was moved."))
        else:
            lines.append(
                ui.green(f"{ui.check()} {len(self.moves)} file(s) promoted.")
                + " Review the diff and commit -- the commit is the approval record."
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


def promote(
    root: Path,
    files: list[Path] | None = None,
    dry_run: bool = False,
    today: date | None = None,
) -> PromoteResult:
    """Validate approved+selected staging as approved; on a clean gate, move the files."""
    selected = _resolve_selection(root, files)
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

    for path in selected:
        target = approved_dir / path.relative_to(staging_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, target)
    result.moved = True
    return result
