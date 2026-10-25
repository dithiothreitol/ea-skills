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

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The current Sonnet, the tier every earlier baseline was measured on (claude-sonnet-5),
# so a move between baselines is a model generation, not a tier change.
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_REPAIRS = 3  # the cap the skills themselves prescribe (research: repair loops plateau at 3-4)
# Streamed, so a large ceiling costs nothing until it is used. A whole modelling phase is
# one reply, thinking included; a truncated reply is a failed run, never half an answer.
MAX_TOKENS = 64000

# The output contract, enforced by the API rather than parsed out of prose (D10). Until
# 0.21.0 the reply was `FILE: <path>` lines and fenced YAML found by regular expressions,
# so a model that wrapped one block differently lost a file and the score measured the
# parser. A JSON schema on `output_config.format` makes a malformed reply impossible
# instead of merely unlikely. Not a tool call: forcing a tool is a 400 on the current
# models, and an unforced one adds "the model did not call the tool" -- a failure of the
# API surface, not of the skill being measured.
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative to the repository root."},
                    "content": {"type": "string", "description": "The file's entire YAML content."},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["files"],
    "additionalProperties": False,
}

OUTPUT_CONTRACT = """
Your reply is one JSON object, `{"files": [{"path": ..., "content": ...}]}`: every file
you write, each with its path relative to the repository root and its entire YAML
content. A file you leave out is not written; nothing outside the object is read.
"""


class RefusalError(RuntimeError):
    """The model declined. A run that ends here is a failed run, reported by name -- never
    silently rescued by another model, which would score that model as this one."""


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
    """The files of a reply under the output contract: ``{path: content}``.

    The schema is enforced by the API, so this mostly re-checks what cannot be wrong --
    but a reply that names no file, or names one twice, is a failed run, reported as
    such. The harness never falls back to "best effort": a scored run that silently used
    half an answer is worse than no number.
    """
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"reply is not the JSON the output contract requires: {exc}") from exc
    items = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("reply has no `files` list")
    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
            raise ValueError(f"malformed file entry: {item!r}"[:200])
        path = item["path"].strip()
        path = path[2:] if path.startswith("./") else path
        if path in out:
            raise ValueError(f"the reply writes {path} twice")
        out[path] = item["content"]
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
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    calls: int = 0
    served_by: set[str] = field(default_factory=set)

    def add(self, response: Any) -> None:
        usage = response.usage
        self.calls += 1
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        # The model that answered, as the API reports it: the record of what was measured.
        self.served_by.add(str(getattr(response, "model", "") or ""))

    def as_dict(self) -> dict[str, Any]:
        # `inputTokens` stays the uncached input, as the API reports it; the two cache
        # counts sit beside it, so a baseline before caching and one after are read with
        # the same arithmetic plus two columns, not a redefined one.
        return {
            "calls": self.calls,
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheWriteTokens": self.cache_write_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "servedBy": sorted(m for m in self.served_by if m),
        }


class Session:
    """One conversation per phase, so a repair sees what it is repairing.

    Three properties the measurement depends on:

    * **The system prompt is cached**, with the one-hour TTL: it is the skills' prose, the
      same bytes for every run of a phase, and runs of one phase start more than five
      minutes apart. The growing conversation is cached automatically behind it, so a
      repair re-reads its history instead of paying for it again.
    * **The history is append-only.** The whole assistant turn goes back -- thinking blocks
      included, unchanged -- because the current models bind thinking to the conversation
      that produced it, and a history that dropped or edited a turn would quietly change
      what the next turn can see.
    * **Sampling is the API default** (no temperature: current models reject one), and
      effort is the model's default, so the spread across runs stays the honest part.
    """

    def __init__(self, client: Any, model: str, system: str, usage: Usage) -> None:
        self.client = client
        self.model = model
        self.system = system
        self.usage = usage
        self.messages: list[dict[str, Any]] = []

    def request(self) -> dict[str, Any]:
        """The request body, separated out so a test can read what is sent."""
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": [
                {"type": "text", "text": self.system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}
            ],
            "cache_control": {"type": "ephemeral"},
            "output_config": {"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            "messages": self.messages,
        }

    def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        with self.client.messages.stream(**self.request()) as stream:
            response = stream.get_final_message()
        self.usage.add(response)
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise RefusalError(f"the model declined (category: {category or 'unspecified'})")
        if response.stop_reason == "max_tokens":
            raise ValueError(f"the reply hit max_tokens ({MAX_TOKENS}) and is incomplete")
        self.messages.append({"role": "assistant", "content": response.content})
        return "".join(block.text for block in response.content if block.type == "text")
