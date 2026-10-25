"""What changed: between two plateaus of the plan, or since a commit of the model.

Two questions an architect asks before every board and that nothing answered:
"what does the target state change?" and "what changed since we last looked?". Both
are read-only derivations (D9). ``--plateau A B`` reads the plan the model already
records -- the same membership ``roadmap`` reads, so the two cannot disagree. ``--ref``
reads the approved zone as git holds it at a commit, through ``git ls-tree`` and
``git show``; it never checks anything out, never writes the index, and never touches
the working tree.

A change is reported by field, not by line: a relationship that moved between files is
not a change, and an element whose ``lifecycle`` changed says so by name.
"""

from __future__ import annotations

import subprocess
from dataclasses import fields
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from . import dsl, reports, ui


class DiffError(RuntimeError):
    pass


# --------------------------------------------------------------------------- plateaus


def _row(element: dsl.Element) -> dict[str, str]:
    return {"id": element.id, "type": element.type, "name": element.name}


def plateaus(root: Path, first: str, second: str) -> dict[str, Any]:
    """What enters, leaves and stays between plateau ``first`` and plateau ``second``."""
    model, _documents, _config = dsl.load(root, "approved")
    for plateau_id in (first, second):
        element = model.elements.get(plateau_id)
        if element is None:
            raise DiffError(f"'{plateau_id}' is not an element of the approved model")
        if element.type != "Plateau":
            raise DiffError(f"'{plateau_id}' is a {element.type}, not a Plateau")
    membership = reports.plateau_membership(model)
    held_first = set(membership.get(first, []))
    held_second = set(membership.get(second, []))

    def rows(ids: set[str]) -> list[dict[str, str]]:
        return [
            _row(model.elements[i]) if i in model.elements else {"id": i, "type": "", "name": ""}
            for i in sorted(ids)
        ]

    # A Gap is the distance between plateaus. One associated with either end belongs to
    # this difference -- a model often ties the gap to the target state only -- and naming
    # it points at what closes it.
    related: dict[str, set[str]] = {}
    for relationship in model.relationships.values():
        for near, far in ((relationship.source, relationship.target), (relationship.target, relationship.source)):
            element = model.elements.get(near)
            if element is not None and element.type == "Gap" and far in (first, second):
                related.setdefault(near, set()).add(far)
    gaps = [{**_row(model.elements[g]), "plateaus": sorted(related[g])} for g in sorted(related)]
    return {
        "from": {"id": first, "name": model.elements[first].name, "date": model.elements[first].properties.get("plateauDate", "")},
        "to": {"id": second, "name": model.elements[second].name, "date": model.elements[second].properties.get("plateauDate", "")},
        "enters": rows(held_second - held_first),
        "leaves": rows(held_first - held_second),
        "stays": rows(held_first & held_second),
        "gaps": gaps,
    }


def render_plateaus(data: dict[str, Any]) -> str:
    first, second = data["from"], data["to"]

    def label(plateau: dict[str, str]) -> str:
        return f"{plateau['name']} ({plateau['id']}{', ' + plateau['date'] if plateau['date'] else ''})"

    lines = [ui.bold(f"From {label(first)} to {label(second)}"), ""]
    for key, mark, title in (("enters", "+", "Enters"), ("leaves", "-", "Leaves"), ("stays", "=", "Stays")):
        items = data[key]
        lines.append(f"{title} ({len(items)}):")
        if not items:
            lines.append(ui.dim("  none"))
        for item in items:
            lines.append(f"  {mark} {item['id']}  {ui.dim(item['type'])}  {item['name']}")
    if data["gaps"]:
        lines.append("")
        lines.append("Gap(s) at either end:")
        for gap in data["gaps"]:
            lines.append(f"  {gap['id']}  {gap['name']}  {ui.dim('at ' + ', '.join(gap['plateaus']))}")
    if not data["enters"] and not data["leaves"]:
        lines.append("")
        lines.append(
            "Both plateaus hold the same elements. If the change between them is real, it lives in "
            "the gap or in properties, not in membership -- or the target plateau is not modelled yet."
        )
    return "\n".join(lines)


# ------------------------------------------------------------------------- git refs


def _git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise DiffError("git is not installed or not on PATH; `diff --ref` reads the history through it") from exc
    if done.returncode != 0:
        raise DiffError(f"git {' '.join(args)} failed: {(done.stderr or done.stdout).strip()}")
    return done.stdout


def _documents_at(root: Path, ref: str, zone: str = "approved") -> list[dsl.Document]:
    """The zone's YAML files as git holds them at ``ref``, parsed like the working tree's."""
    names = _git(root, "ls-tree", "-r", "--name-only", "--full-name", ref, "--", f"model/{zone}").splitlines()
    documents: list[dsl.Document] = []
    for name in sorted(names):
        if PurePosixPath(name).suffix not in {".yaml", ".yml"}:
            continue
        path = Path(name)
        text = _git(root, "show", f"{ref}:{name}")
        try:
            data = yaml.safe_load(text)
        except dsl.YAML_ERRORS as exc:
            documents.append(dsl.Document(path=path, data=None, parse_error=str(exc)))
            continue
        if data is None:
            data = {}
        if not isinstance(data, dict):
            documents.append(dsl.Document(path=path, data=None, parse_error="top level of a model file must be a mapping"))
            continue
        documents.append(dsl.Document(path=path, data=dsl._normalize_scalars(data)))
    return documents


# Bookkeeping, not content: where a concept is written is not what it says.
IGNORED_FIELDS = {"source_path", "locator"}
FIELD_NAMES = {"last_reviewed": "lastReviewed", "applies_to": "appliesTo"}


def _changed_fields(before: Any, after: Any) -> list[str]:
    changed: list[str] = []
    for spec in fields(before):
        if spec.name in IGNORED_FIELDS:
            continue
        old, new = getattr(before, spec.name), getattr(after, spec.name)
        if old == new:
            continue
        if spec.name == "properties":
            for key in sorted(set(old) | set(new)):
                if old.get(key) != new.get(key):
                    changed.append(f"properties.{key}")
            continue
        changed.append(FIELD_NAMES.get(spec.name, spec.name))
    return changed


def _compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    def row(item: Any) -> dict[str, Any]:
        out = {"id": item.id, "type": getattr(item, "type", ""), "name": item.name}
        if isinstance(item, dsl.Relationship):
            out.update(source=item.source, target=item.target)
        return out

    added = [row(after[i]) for i in sorted(set(after) - set(before))]
    removed = [row(before[i]) for i in sorted(set(before) - set(after))]
    changed = []
    for item_id in sorted(set(before) & set(after)):
        names = _changed_fields(before[item_id], after[item_id])
        if names:
            changed.append({**row(after[item_id]), "fields": names})
    return {"added": added, "removed": removed, "changed": changed}


def since(root: Path, ref: str) -> dict[str, Any]:
    """The approved zone now, against the approved zone at ``ref``."""
    _git(root, "rev-parse", "--is-inside-work-tree")
    try:
        commit = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()
    except DiffError as exc:
        raise DiffError(f"'{ref}' is not a commit this repository knows") from exc
    short = _git(root, "rev-parse", "--short", commit).strip()
    then_documents = _documents_at(root, commit)
    config = dsl.load_config(root)
    then = dsl.build_model(root, "approved", then_documents, config)
    now, _documents, _config = dsl.load(root, "approved")
    unreadable = [d.path.as_posix() for d in then_documents if d.data is None]
    return {
        "ref": ref,
        "commit": short,
        "files": len(then_documents),
        "unreadableAtRef": unreadable,
        "elements": _compare(then.elements, now.elements),
        "relationships": _compare(then.relationships, now.relationships),
        "views": _compare(then.views, now.views),
    }


def _label(item: dict[str, Any]) -> str:
    if "source" in item and not item["name"]:
        return f"{item['source']} {ui.arrow()} {item['target']}"
    return item["name"]


def render_since(data: dict[str, Any]) -> str:
    lines = [ui.bold(f"The approved model now, against {data['ref']} ({data['commit']})"), ""]
    if data["unreadableAtRef"]:
        lines.append(ui.yellow("Unreadable at that commit (compared as absent): " + ", ".join(data["unreadableAtRef"])))
        lines.append("")
    quiet = True
    for key, title in (("elements", "Elements"), ("relationships", "Relationships"), ("views", "Views")):
        part = data[key]
        if not (part["added"] or part["removed"] or part["changed"]):
            continue
        quiet = False
        lines.append(
            f"{title}: {len(part['added'])} added, {len(part['removed'])} removed, {len(part['changed'])} changed"
        )
        for mark, items in (("+", part["added"]), ("-", part["removed"])):
            for item in items:
                lines.append(f"  {mark} {item['id']}  {ui.dim(item['type'])}  {_label(item)}".rstrip())
        for item in part["changed"]:
            lines.append(f"  ~ {item['id']}  {', '.join(item['fields'])}")
        lines.append("")
    if quiet:
        lines.append(f"{ui.green(ui.check())} Nothing in the approved zone changed since {data['ref']}.")
    return "\n".join(lines).rstrip("\n")
