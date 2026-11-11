"""``intake-redact``: the copy of a sensitive source that is fit to commit.

Sources are committed verbatim -- that is what makes a quote checkable -- and git history
is permanent: an interview committed once is in every clone, even after the file is
deleted. Some sources name people, quote opinions about colleagues, or carry details a
repository shared with a supplier must not hold. The honest response is not to stop
quoting them; it is to quote a redacted copy, made by code, whose relationship to the
original is recorded.

So this converter applies a replacement map a person wrote (``find`` -> ``replace``, in
order, case-sensitive, nothing inferred) to a text source kept outside git
(``facts/sources-private/`` is ignored by the scaffold), and writes the copy into
``facts/sources/`` with a header recording the original's SHA-256 and how many
replacements were made -- **not the map**, because the map names exactly what was removed.
A rule that matched nothing is reported: a name spelled differently in the source is a
name left in. Quotes are then verified against the redacted copy like any other source.

It interprets nothing and guesses nothing: no name detection, no patterns. Deciding what
is sensitive is a judgement, and the map is where that judgement is written down.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import dsl

TEXT_SUFFIXES = {".md", ".txt"}


class RedactError(RuntimeError):
    pass


@dataclass
class RedactReport:
    source: str
    target: str
    sha256: str
    rules: int
    replacements: int
    unmatched: list[int] = field(default_factory=list)  # 1-based rule numbers that matched nothing

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_map(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise RedactError(f"{path} does not exist")
    try:
        data = dsl.load_yaml(path.read_text(encoding="utf-8"))
    except dsl.YAML_ERRORS as exc:
        raise RedactError(f"cannot read the replacement map: {exc}") from None
    rules = data.get("replacements") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        raise RedactError("the map needs a non-empty `replacements:` list of {find, replace} entries")
    out: list[tuple[str, str]] = []
    for number, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict) or not isinstance(rule.get("find"), str) or not rule["find"]:
            raise RedactError(f"replacement {number} needs a non-empty `find` string")
        replace = rule.get("replace", "")
        if not isinstance(replace, str):
            raise RedactError(f"replacement {number}: `replace` must be a string")
        if rule["find"] in replace:
            raise RedactError(f"replacement {number} puts back what it removes ({rule['find']!r} is in its replacement)")
        out.append((rule["find"], replace))
    return out


def redact(source: Path, mapping: Path, out: Path, overwrite: bool = False) -> RedactReport:
    if not source.is_file():
        raise RedactError(f"{source} does not exist")
    if source.suffix.lower() not in TEXT_SUFFIXES:
        raise RedactError(
            f"{source.name}: redaction works on text sources ({', '.join(sorted(TEXT_SUFFIXES))}); convert a "
            "PDF, Word or spreadsheet file with intake-doc or intake-csv first, then redact the result"
        )
    if out.exists() and not overwrite:
        raise RedactError(
            f"{out} already exists -- re-run with --overwrite once you have checked the diff, so a redaction "
            "never silently replaces evidence a fact may already cite"
        )
    raw = source.read_bytes()
    # One newline convention before any rule runs: a `find` written with \n must match a
    # transcript saved with \r\n, or a name split across a line break is committed.
    text = raw.decode("utf-8").replace("\r\n", "\n")
    rules = load_map(mapping)
    total = 0
    unmatched: list[int] = []
    for number, (find, replace) in enumerate(rules, start=1):
        count = text.count(find)
        if not count:
            unmatched.append(number)
        total += count
        text = text.replace(find, replace)
    # Rules run in order, so a later replacement can put back what an earlier one removed.
    # Whatever the order did, no `find` may survive into a copy bound for permanent history.
    survivors = [number for number, (find, _replace) in enumerate(rules, start=1) if find in text]
    if survivors:
        raise RedactError(
            f"the redacted text still contains what rule(s) {', '.join(map(str, survivors))} remove -- a later "
            "replacement put it back; reorder or rewrite the map. Nothing was written"
        )
    report = RedactReport(
        source=source.name,
        target=str(out),
        sha256=hashlib.sha256(raw).hexdigest(),
        rules=len(rules),
        replacements=total,
        unmatched=unmatched,
    )
    # The original's file name is not recorded either: the name of a sensitive source often
    # carries exactly what the map removes ("interview-jan-kowalski.md").
    header = [
        "# Redacted source",
        "",
        "> Redacted from the original by `easkills intake-redact`. Do not edit: re-run the redaction "
        "instead, so quotes verified against this file stay traceable to the original's bytes. The "
        "original is not committed, and neither its name nor the replacement map -- which names what "
        "was removed -- is recorded here.",
        "",
        f"- **SHA-256 of the original:** `{report.sha256}`",
        f"- **Replacements:** {report.rules} rule(s), {report.replacements} occurrence(s)",
    ]
    document = "\n".join(header) + "\n\n\n" + text.rstrip("\n") + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8", newline="\n")
    return report
