"""The approval seal: approved content changed outside ``promote`` is a finding of the gate (D4).

AD-02 says the approved zone is human-signed and that promotion is its only write path.
Since 0.16.0 a hook refuses other writes, and since 0.22.0 promotion itself is put to the
person -- but a hook is a guard rail on one host. An editor, a script, a merge conflict
resolved by hand or a different agent writes straight past it, and the approved zone then
holds content nobody signed, indistinguishable from content somebody did.

So ``promote`` now writes an approval record (``governance-log/approvals/``) carrying the
SHA-256 of every file it put into ``model/approved/``, and the model gate checks the zone
against the records -- the way every consuming command checks the oracle against its pins:

* ``APR001`` -- an approved file whose current bytes no record vouches for: changed (or
  added) outside ``promote``.
* ``APR002`` -- a record that cannot be read, does not satisfy its schema, or repeats an id.
* ``APR003`` -- a record vouches for a file the approved zone no longer holds: deleted
  outside ``promote``. (Promotion never deletes a file; retiring a whole file is promoting
  an empty replacement, which is a signed act like any other.)

**The ramp is state-based** (the ``ISO003`` shape): a repository that holds no record at
all is told once, as information, that its approved zone is not sealed; from its first
record on, every finding is an error. ``promote --seal-existing`` writes that first record
for what an adopting repository already holds, names itself as the seal, and refuses to
run twice -- re-sealing would launder whatever had changed since.

What a record proves is consistency, not identity: anybody can write a YAML file. The git
commit that adds a record is who signed, and in a team the pull request that carries it,
reviewed by the code owners of ``governance-log/approvals/``, is the signature. The seal
turns "somebody edited approved content" from invisible into a failing gate.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from . import dsl, genschema
from .validate import SEVERITY_ERROR, SEVERITY_INFO, Finding

APPROVALS_DIR = Path("governance-log") / "approvals"
YAML_SUFFIXES = {".yaml", ".yml"}


@dataclass
class Record:
    id: str
    kind: str
    approved_by: str
    date: str
    path: Path
    files: dict[str, str] = field(default_factory=dict)  # repo-relative path -> sha256


def sha256_file(path: Path) -> str:
    """The digest of a file's content with line endings normalized, as git stores it.

    A CRLF file on a Windows working tree is committed as LF (``text=auto eol=lf``), so
    hashing the raw bytes would record a digest no other clone can reproduce, and CI would
    report a change nobody made. Normalizing first makes one digest per content.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def approved_files(root: Path) -> list[Path]:
    directory = dsl.zone_dir(root, "approved")
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in YAML_SUFFIXES)


def record_files(root: Path) -> list[Path]:
    directory = root / APPROVALS_DIR
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix in YAML_SUFFIXES)


def load_records(root: Path) -> tuple[list[Record], list[Finding]]:
    """Every readable, schema-valid record, and an ``APR002`` for every other one."""
    validator = Draft202012Validator(genschema.load_approval_schema())
    records: list[Record] = []
    findings: list[Finding] = []
    seen: dict[str, Path] = {}
    for path in record_files(root):
        rel = relative(root, path)
        try:
            data = dsl.load_yaml(path.read_text(encoding="utf-8"))
        except dsl.YAML_ERRORS as exc:
            findings.append(Finding("APR002", SEVERITY_ERROR, f"cannot read the approval record: {exc}", file=rel))
            continue
        data = dsl._normalize_scalars(data) if isinstance(data, dict) else data
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)) if isinstance(data, dict) else []
        if not isinstance(data, dict) or errors:
            message = errors[0].message if errors else "the top level of an approval record must be a mapping"
            locator = "/".join(str(p) for p in errors[0].absolute_path) if errors else ""
            findings.append(
                Finding(
                    "APR002",
                    SEVERITY_ERROR,
                    f"the approval record does not satisfy its schema: {message} -- an unreadable record "
                    "vouches for nothing",
                    file=rel,
                    locator=locator,
                )
            )
            continue
        if data["id"] in seen:
            findings.append(
                Finding(
                    "APR002",
                    SEVERITY_ERROR,
                    f"duplicate approval record id '{data['id']}' (also {relative(root, seen[data['id']])})",
                    file=rel,
                    concept=data["id"],
                )
            )
            continue
        seen[data["id"]] = path
        records.append(
            Record(
                id=data["id"],
                kind=data["kind"],
                approved_by=data["approvedBy"],
                date=data["date"],
                path=path,
                files={entry["path"]: entry["sha256"] for entry in data["files"]},
            )
        )
    records.sort(key=lambda r: (r.date, r.id))
    return records, findings


def check_seal(root: Path) -> list[Finding]:
    """APR001-APR003 for the approved zone at ``root``."""
    records, findings = load_records(root)
    files = approved_files(root)
    if not record_files(root):
        if files:
            findings.append(
                Finding(
                    "APR001",
                    SEVERITY_INFO,
                    f"the approved zone is not sealed: no approval record vouches for its {len(files)} file(s). "
                    "`easkills promote --seal-existing --approved-by <who> --as-of <date>` writes the first "
                    "one; from then on, approved content that changes outside `promote` fails this gate",
                    file="model/approved",
                )
            )
        return findings

    # Only the latest record naming a file counts. An earlier digest is a version that was
    # signed and then superseded by a later signature; restoring it by hand undoes that
    # later decision without anybody signing, which is exactly what the seal must catch.
    latest: dict[str, tuple[str, str]] = {}  # path -> (sha256, record id), records in order
    for record in records:
        for path, digest in record.files.items():
            latest[path] = (digest, record.id)
    present: set[str] = set()
    for path in files:
        rel = relative(root, path)
        present.add(rel)
        digest = sha256_file(path)
        known = latest.get(rel)
        if not known:
            findings.append(
                Finding(
                    "APR001",
                    SEVERITY_ERROR,
                    "no approval record vouches for this file -- it entered the approved zone outside "
                    "`easkills promote`. Move it back to model/staging/ and promote it, so a person signs it",
                    file=rel,
                )
            )
        elif digest != known[0]:
            last = known[1]
            findings.append(
                Finding(
                    "APR001",
                    SEVERITY_ERROR,
                    f"changed since it was approved: its content (SHA-256 {digest[:12]}...) is not what "
                    f"'{last}', the latest record naming it, vouched for. Approved content changes only "
                    "through `easkills promote` -- put the change in model/staging/ and promote it",
                    file=rel,
                )
            )
    for path in sorted(set(latest) - present):
        last = latest[path][1]
        findings.append(
            Finding(
                "APR003",
                SEVERITY_ERROR,
                f"'{last}' vouches for {path}, which the approved zone no longer holds -- deleted outside "
                "`easkills promote`. Promotion never deletes a file; retiring one is promoting an empty "
                "replacement, which a person signs",
                file=path,
            )
        )
    return findings


# --------------------------------------------------------------------------- writing


class _Dumper(yaml.SafeDumper):
    """Indent sequences under their key, as every hand-authored file here does."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # noqa: D102
        return super().increase_indent(flow, False)


def next_record_id(root: Path, day: str) -> str:
    """``approval-<date>-<NN>``: chronological within a day, derived, never random."""
    prefix = f"approval-{day}-"
    taken = {p.stem for p in record_files(root) if p.stem.startswith(prefix)}
    number = 1
    while f"{prefix}{number:02d}" in taken:
        number += 1
    return f"{prefix}{number:02d}"


def concept_definitions(documents: list[dsl.Document]) -> dict[str, Any]:
    """id -> the concept's authored definition, for comparing two states of a zone."""
    definitions: dict[str, Any] = {}
    for document in documents:
        if not isinstance(document.data, dict):
            continue
        for section in ("elements", "relationships", "views"):
            for item in document.data.get(section) or []:
                if isinstance(item, dict) and item.get("id"):
                    definitions[str(item["id"])] = item
    return definitions


def write_record(
    root: Path,
    *,
    kind: str,
    approved_by: str,
    day: str,
    files: list[Path],
    paths: list[str] | None = None,
    added: list[str] | None = None,
    changed: list[str] | None = None,
    removed: list[str] | None = None,
    assumptions: list[str] | None = None,
) -> Path:
    record_id = next_record_id(root, day)
    data: dict[str, Any] = {
        "id": record_id,
        "kind": kind,
        "approvedBy": approved_by,
        "date": day,
        # `paths` names where each file will be once promoted; the bytes are read from
        # `files`, which a promotion has not moved yet (a rename keeps them identical).
        "files": sorted(
            (
                {"path": path, "sha256": sha256_file(source)}
                for path, source in zip(paths or [relative(root, f) for f in files], files)
            ),
            key=lambda entry: entry["path"],
        ),
    }
    for key, values in (("added", added), ("changed", changed), ("removed", removed), ("assumptionsAccepted", assumptions)):
        if values:
            data[key] = sorted(values)
    header = (
        "# Written by `easkills promote`. Do not edit: the model gate checks every approved file\n"
        "# against these digests (APR001-APR003), and the commit adding this file is who signed.\n"
    )
    target = root / APPROVALS_DIR / f"{record_id}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    target.write_text(header + body, encoding="utf-8", newline="\n")
    return target
