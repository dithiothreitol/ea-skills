"""The harness's request contract, offline: what is sent, what is kept, what counts as failure.

The measurement is only as good as the plumbing around it. These tests pin the four things
0.21.0 changed (D10) without spending a token: the output contract is a JSON schema the API
enforces, the system prompt is cached, the conversation is append-only, and a refusal or a
truncated reply is a failed run rather than a partial one. They also pin `--candidates`:
the choice is reproducible and prefers a candidate that passed its gate.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "eval" / "harness"


def _load(name: str, filename: str):
    if str(HARNESS) not in sys.path:
        sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location(name, HARNESS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def common():
    return _load("common", "common.py")


@pytest.fixture(scope="module")
def run(common):
    return _load("ea_run", "run.py")


# ------------------------------------------------------------------------- contract


def test_the_reply_is_parsed_as_json_files(common):
    reply = json.dumps({"files": [{"path": "./facts/a.yaml", "content": "facts: []\n"}, {"path": "b.yaml", "content": ""}]})
    assert common.extract_files(reply) == {"facts/a.yaml": "facts: []\n", "b.yaml": ""}


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        ("FILE: a.yaml\n```yaml\nx: 1\n```", "not the JSON"),
        (json.dumps({"documents": []}), "no `files` list"),
        (json.dumps({"files": [{"path": "a.yaml"}]}), "malformed"),
        (json.dumps({"files": [{"path": "a.yaml", "content": "1"}, {"path": "./a.yaml", "content": "2"}]}), "twice"),
    ],
)
def test_a_reply_outside_the_contract_is_a_failed_run(common, reply, message):
    with pytest.raises(ValueError, match=message):
        common.extract_files(reply)


def test_the_schema_stays_inside_what_structured_outputs_accept(common):
    """Every object closed, no length or numeric constraints: the subset the API compiles."""

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
                assert set(node.get("required", [])) == set(node.get("properties", {}))
            for banned in ("minLength", "maxLength", "minimum", "maximum", "pattern", "minItems"):
                assert banned not in node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(common.OUTPUT_SCHEMA)


def test_the_request_caches_the_system_prompt_and_carries_the_schema(common):
    session = common.Session(client=None, model=common.DEFAULT_MODEL, system="skills prose", usage=common.Usage())
    request = session.request()
    assert request["model"] == "claude-sonnet-5-5"
    assert request["system"] == [
        {"type": "text", "text": "skills prose", "cache_control": {"type": "ephemeral", "ttl": "1h"}}
    ]
    assert request["cache_control"] == {"type": "ephemeral"}, "the conversation tail, cached automatically"
    assert request["output_config"]["format"] == {"type": "json_schema", "schema": common.OUTPUT_SCHEMA}
    for absent in ("temperature", "top_p", "top_k", "tool_choice", "tools"):
        assert absent not in request


# ---------------------------------------------------------------------- the session


class _Stream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.response


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent: list[dict] = []
        self.messages = self

    def stream(self, **request):
        self.sent.append({**request, "messages": list(request["messages"])})
        return _Stream(self.responses.pop(0))


def _response(text, stop="end_turn", thinking=True, model="claude-sonnet-5-5"):
    content = []
    if thinking:
        content.append(SimpleNamespace(type="thinking", thinking="", signature="sig"))
    content.append(SimpleNamespace(type="text", text=text))
    usage = SimpleNamespace(input_tokens=10, output_tokens=20, cache_creation_input_tokens=300, cache_read_input_tokens=50)
    return SimpleNamespace(content=content, stop_reason=stop, stop_details=None, usage=usage, model=model)


def test_the_history_is_append_only_with_thinking_kept(common):
    first = _response('{"files": []}')
    client = _Client([first, _response('{"files": []}', thinking=False)])
    usage = common.Usage()
    session = common.Session(client, common.DEFAULT_MODEL, "system", usage)
    session.ask("one")
    session.ask("two")
    assert session.messages[1] == {"role": "assistant", "content": first.content}, "the whole turn, thinking included"
    assert [m["role"] for m in client.sent[1]["messages"]] == ["user", "assistant", "user"]
    assert client.sent[1]["messages"][1]["content"][0].type == "thinking"
    assert usage.as_dict() == {
        "calls": 2, "inputTokens": 20, "outputTokens": 40, "cacheWriteTokens": 600, "cacheReadTokens": 100,
        "servedBy": ["claude-sonnet-5-5"],
    }


def test_a_refusal_and_a_truncation_are_failed_runs(common):
    refused = common.Session(_Client([_response("", stop="refusal")]), common.DEFAULT_MODEL, "s", common.Usage())
    with pytest.raises(common.RefusalError):
        refused.ask("x")
    truncated = common.Session(_Client([_response('{"files": [', stop="max_tokens")]), common.DEFAULT_MODEL, "s", common.Usage())
    with pytest.raises(ValueError, match="max_tokens"):
        truncated.ask("x")
    assert len(truncated.messages) == 1, "a truncated turn never enters the history"


def test_the_model_that_answered_is_recorded(common):
    usage = common.Usage()
    common.Session(_Client([_response('{"files": []}', model="claude-opus-5-5")]), common.DEFAULT_MODEL, "s", usage).ask("x")
    assert usage.as_dict()["servedBy"] == ["claude-opus-5-5"], "a different model answering must show"


# ---------------------------------------------------------------------- candidates


def test_the_kept_candidate_passed_its_gate_and_ties_go_to_the_earliest(run):
    assert run.choose([1, 0, 0], [0.9, 0.5, 0.7]) == 2, "a failed gate never wins on agreement"
    assert run.choose([0, 0, 0], [0.6, 0.6, 0.5]) == 0
    assert run.choose([1, 1, 1], [0.2, 0.4, 0.3]) == 1, "if none passed, agreement alone decides"


def test_agreement_is_full_between_identical_models_and_lower_for_a_dissenter(run, tmp_path, example_root):
    roots = []
    for name in ("a", "b", "c"):
        root = tmp_path / name
        shutil.copytree(example_root, root)
        shutil.copytree(root / "model" / "approved", root / "model" / "staging", dirs_exist_ok=True)
        shutil.rmtree(root / "model" / "approved")
        (root / "model" / "approved").mkdir()
        roots.append(root)
    (roots[2] / "model" / "staging" / "relations.yaml").unlink()
    scores = run.agreement(roots)
    assert scores[0] == scores[1] > scores[2]
    assert run.choose([0, 0, 0], scores) == 0


def test_two_candidates_are_refused_because_they_always_tie(run, capsys):
    with pytest.raises(SystemExit):
        run.main(["--case", "clinic", "--candidates", "2"])
    assert "two candidates always tie" in capsys.readouterr().err
