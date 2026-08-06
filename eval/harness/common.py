"""Plumbing shared by the harnesses: the API session, the file contract, the gates.

Two harnesses measure skill prose in two different ways -- `run.py` scores extraction and
modelling against a golden repository, `contracts.py` checks that a governance record a
skill produced satisfies deterministic properties. They share everything except what they
measure, and the shared half is here so a change to the output contract or the key handling
cannot apply to one and not the other.

Like `run.py`, nothing in this file is imported by `easkills/`; the quarantine tests fail
if that ever changes.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_MODEL = "claude-sonnet-5"
MAX_REPAIRS = 3  # the cap the skills themselves prescribe (research: repair loops plateau at 3-4)
MAX_TOKENS = 16000

FILE_MARKER = re.compile(r"^FILE:\s*(?P<path>[A-Za-z0-9._/-]+)\s*$", re.MULTILINE)
FENCE = re.compile(r"```(?:yaml|yml)?\s*\n(?P<body>.*?)```", re.DOTALL)

OUTPUT_CONTRACT = """
Reply with nothing but the files. For each file, one line

FILE: <path relative to the repository root>

followed by one fenced ```yaml block holding that file's entire content. No prose
before, between or after the blocks -- anything else is discarded by the harness.
"""


def load_key() -> str:
    """Environment first, then a local ``.env``. The value is never logged."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "ANTHROPIC_API_KEY is not set. Export it, or put it in .env (which is gitignored)."
    )


def client() -> Any:
    try:
        import anthropic
    except ImportError:
        raise SystemExit("pip install -r requirements-eval.txt") from None
    return anthropic.Anthropic(api_key=load_key())


def easkills(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a core command exactly as a user would, from the repository root."""
    return subprocess.run(
        [sys.executable, "-m", "easkills", *args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def skill(name: str) -> str:
    return (REPO_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def extract_files(text: str) -> dict[str, str]:
    """Parse ``FILE: <path>`` + fenced block pairs out of a model reply.

    A reply that produces no parseable file is a failed run, reported as such -- the
    harness never falls back to "best effort", because a scored run that silently used
    half an answer is worse than no number.
    """
    out: dict[str, str] = {}
    markers = list(FILE_MARKER.finditer(text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        fence = FENCE.search(text, marker.end(), end)
        if fence:
            out[marker.group("path")] = fence.group("body")
    return out


def write_files(root: Path, files: dict[str, str]) -> None:
    """Write a reply's files under ``root``, refusing to escape it."""
    for relative, body in files.items():
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError(f"refusing to write outside the scratch repository: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8", newline="\n")


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, response: Any) -> None:
        self.calls += 1
        self.input_tokens += getattr(response.usage, "input_tokens", 0)
        self.output_tokens += getattr(response.usage, "output_tokens", 0)

    def as_dict(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
        }


class Session:
    """One conversation per phase, so a repair sees what it is repairing."""

    def __init__(self, client: Any, model: str, system: str, usage: Usage) -> None:
        self.client = client
        self.model = model
        self.system = system
        self.usage = usage
        self.messages: list[dict[str, Any]] = []

    def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system,
            messages=self.messages,
        )
        self.usage.add(response)
        text = "".join(block.text for block in response.content if block.type == "text")
        self.messages.append({"role": "assistant", "content": text})
        return text
