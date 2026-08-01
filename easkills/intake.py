"""Deterministic intake tooling: chunking sources and measuring fact coverage.

Both halves exist so the extraction skill (``ea-intake``) can lean on code for the
parts research says not to trust a language model with:

* **Chunking** -- small chunks roughly double entity recall (GraphRAG), and a
  deterministic chunker means a re-run processes identical units, so gleaning
  passes and reviews are comparable across runs.
* **Coverage** -- "which parts of the source produced no facts" is a mechanical
  question. The answer is where clarification questions come from; a model asked
  to self-assess coverage will simply say it covered everything.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import facts as facts_mod
from .validate import _normalize

DEFAULT_MAX_CHARS = 2000
MIN_SENTENCE_CHARS = 30
_SENTENCE_END_RE = re.compile(r"[.!?]")


# ------------------------------------------------------------------------- chunking


@dataclass(frozen=True)
class Chunk:
    id: str
    file: str
    start_line: int
    end_line: int
    text: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Block:
    start_line: int
    end_line: int
    text: str


def _blocks(text: str) -> list[_Block]:
    """Split into blank-line-separated blocks, keeping 1-based line numbers."""
    blocks: list[_Block] = []
    current: list[str] = []
    start = 0
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not current:
                start = number
            current.append(line)
        elif current:
            blocks.append(_Block(start, number - 1, "\n".join(current)))
            current = []
    if current:
        blocks.append(_Block(start, start + len(current) - 1, "\n".join(current)))
    return blocks


def _split_oversized(block: _Block, max_chars: int) -> list[_Block]:
    """Split a block that alone exceeds the budget, at line granularity so the
    reported line numbers stay exact. A single line longer than the budget is
    kept whole -- there is no honest way to sub-address it."""
    pieces: list[_Block] = []
    current: list[str] = []
    size = 0
    start = block.start_line
    for offset, line in enumerate(block.text.splitlines()):
        number = block.start_line + offset
        if current and size + len(line) + 1 > max_chars:
            pieces.append(_Block(start, number - 1, "\n".join(current)))
            current, size, start = [], 0, number
        current.append(line)
        size += len(line) + 1
    if current:
        pieces.append(_Block(start, start + len(current) - 1, "\n".join(current)))
    return pieces


def chunk_text(text: str, file: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Greedily pack whole blocks into chunks of at most ``max_chars``."""
    units: list[_Block] = []
    for block in _blocks(text):
        if len(block.text) > max_chars:
            units.extend(_split_oversized(block, max_chars))
        else:
            units.append(block)

    chunks: list[Chunk] = []
    current: list[_Block] = []
    size = 0

    def flush() -> None:
        if not current:
            return
        chunks.append(
            Chunk(
                id=f"c{len(chunks) + 1:03d}",
                file=file,
                start_line=current[0].start_line,
                end_line=current[-1].end_line,
                text="\n\n".join(b.text for b in current),
            )
        )

    for unit in units:
        if current and size + len(unit.text) + 2 > max_chars:
            flush()
            current, size = [], 0
        current.append(unit)
        size += len(unit.text) + 2
    flush()
    return chunks


def chunk_file(path: Path, file_label: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    return chunk_text(path.read_text(encoding="utf-8", errors="replace"), file_label, max_chars)


def render_chunks(chunks: list[Chunk]) -> str:
    lines: list[str] = []
    for chunk in chunks:
        lines.append(
            f"-- {chunk.file} {chunk.id}  lines {chunk.start_line}-{chunk.end_line}  ({len(chunk.text)} chars)"
        )
        lines.append(chunk.text)
        lines.append("")
    lines.append(f"{len(chunks)} chunk(s)")
    return "\n".join(lines)


# ------------------------------------------------------------------------- coverage


@dataclass(frozen=True)
class Sentence:
    start_line: int
    end_line: int
    text: str          # normalized
    covered: bool


@dataclass
class FileCoverage:
    file: str
    sentences: int = 0
    covered: int = 0
    facts: int = 0
    uncovered: list[Sentence] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.covered / self.sentences if self.sentences else 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "sentences": self.sentences,
            "covered": self.covered,
            "coverage": round(self.ratio, 4),
            "facts": self.facts,
            "uncovered": [
                {"lines": f"{s.start_line}-{s.end_line}", "text": s.text} for s in self.uncovered
            ],
        }


@dataclass
class CoverageReport:
    root: Path
    files: list[FileCoverage] = field(default_factory=list)

    @property
    def sentences(self) -> int:
        return sum(f.sentences for f in self.files)

    @property
    def covered(self) -> int:
        return sum(f.covered for f in self.files)

    @property
    def ratio(self) -> float:
        return self.covered / self.sentences if self.sentences else 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "sentences": self.sentences,
            "covered": self.covered,
            "coverage": round(self.ratio, 4),
            "files": [f.as_dict() for f in self.files],
        }

    def render(self) -> str:
        lines = [f"Source coverage at {self.root}", ""]
        if not self.files:
            lines.append("No source files found.")
        for coverage in self.files:
            lines.append(
                f"{coverage.file}: {coverage.covered}/{coverage.sentences} statements cited "
                f"({coverage.ratio:.0%}), {coverage.facts} fact(s)"
            )
            for sentence in coverage.uncovered:
                text = sentence.text if len(sentence.text) <= 100 else sentence.text[:97] + "..."
                lines.append(f"  uncited  lines {sentence.start_line}-{sentence.end_line}: {text}")
        lines += [
            "",
            f"TOTAL {self.covered}/{self.sentences} ({self.ratio:.0%}) -- "
            "uncited statements are candidate clarification questions, not automatic defects",
        ]
        return "\n".join(lines)


def _index_source(text: str) -> tuple[str, list[int], set[int]]:
    """Normalize like the quote matcher does, tracking the original line of every
    normalized character and the offsets where a new paragraph starts."""
    norm: list[str] = []
    lines: list[int] = []
    para_starts: set[int] = set()
    line_no = 1
    saw_space = False
    saw_break = False
    newlines = 0
    for ch in text:
        if ch == "\n":
            line_no += 1
            newlines += 1
            saw_space = True
            if newlines >= 2:
                saw_break = True
            continue
        if ch.isspace():
            saw_space = True
            continue
        newlines = 0
        if norm and saw_space:
            norm.append(" ")
            lines.append(line_no)
        if saw_break or not norm:
            para_starts.add(len(norm))
        saw_space = False
        saw_break = False
        for folded in ch.casefold():
            norm.append(folded)
            lines.append(line_no)
    return "".join(norm), lines, para_starts


def _sentence_spans(norm: str, para_starts: set[int]) -> list[tuple[int, int]]:
    """Sentence intervals over the normalized text; paragraph breaks always split."""
    boundaries = sorted(para_starts | {len(norm)})
    spans: list[tuple[int, int]] = []
    for para_start, para_end in zip(boundaries, boundaries[1:]):
        start = para_start
        position = para_start
        while position < para_end:
            match = _SENTENCE_END_RE.search(norm, position, para_end)
            if match is None:
                break
            # Sentence ends only where the punctuation is followed by a space;
            # "PostgreSQL 16." mid-sentence numbers and "e.g." stay intact enough.
            end = match.end()
            if end >= para_end or norm[end] == " ":
                text = norm[start:end].strip()
                if text:
                    spans.append((start, end))
                start = end + 1
            position = end
        tail = norm[start:para_end].strip()
        if tail:
            spans.append((start, para_end))
    return spans


MIN_TABLE_ROW_CHARS = 40


def _substantive(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith(("#", "*")):
        return False  # markdown headings and emphasis-only metadata lines
    # Table rows carry content, but short ones are headers ("| System | Role |...").
    minimum = MIN_TABLE_ROW_CHARS if stripped.startswith("|") else MIN_SENTENCE_CHARS
    if len(text) < minimum:
        return False
    return any(ch.isalpha() for ch in text)


def coverage(root: Path) -> CoverageReport:
    register, _documents, _entities = facts_mod.load(root)
    facts_root = register.facts_root()

    quotes_by_file: dict[Path, list[str]] = {}
    facts_by_file: dict[Path, int] = {}
    for fact in register.facts.values():
        counted: set[Path] = set()
        for provenance in fact.provenance:
            path = (facts_root / provenance.file).resolve()
            quotes_by_file.setdefault(path, []).append(_normalize(provenance.quote))
            if path not in counted:
                facts_by_file[path] = facts_by_file.get(path, 0) + 1
                counted.add(path)

    report = CoverageReport(root=root)
    for path in facts_mod.iter_source_files(register):
        resolved = path.resolve()
        norm, lines, para_starts = _index_source(path.read_text(encoding="utf-8", errors="replace"))
        covered = [False] * len(norm)
        for quote in quotes_by_file.get(resolved, []):
            if not quote:
                continue
            start = norm.find(quote)
            while start != -1:
                for i in range(start, start + len(quote)):
                    covered[i] = True
                start = norm.find(quote, start + 1)

        file_coverage = FileCoverage(file=facts_mod._rel(root, path), facts=facts_by_file.get(resolved, 0))
        for span_start, span_end in _sentence_spans(norm, para_starts):
            text = norm[span_start:span_end].strip()
            if not _substantive(text):
                continue
            file_coverage.sentences += 1
            overlap = sum(1 for i in range(span_start, span_end) if covered[i])
            is_covered = overlap >= (span_end - span_start) * 0.5
            if is_covered:
                file_coverage.covered += 1
            else:
                file_coverage.uncovered.append(
                    Sentence(
                        start_line=lines[span_start],
                        end_line=lines[span_end - 1],
                        text=text,
                        covered=False,
                    )
                )
        report.files.append(file_coverage)
    return report
