"""``serve``: the approved model as a read-only MCP server over stdio.

AD-10 deferred a network facade until someone asked for one; Phase 8 reversed that
(operator decision 3): demand cannot appear for a surface that does not exist, and
reading the approved zone breaks nothing AD-09 protects. So this is the smallest honest
surface -- an agent in any MCP host can ask the questions the reports answer, without a
shell, and cannot change anything (D9):

* **Read-only by construction.** The tool table below is an allowlist of report
  functions; nothing that writes -- ``promote``, ``propose``, the intake commands,
  ``import``, ``compile``, ``render``, ``docs``, ``gen-schema``, the pin commands -- is
  reachable, and a test asserts the table against that list and runs every tool over a
  copy of a repository to prove no file changes.
* **The approved zone only.** Staging is a proposal; a server answering from it would
  present an unreviewed model as the architecture.
* **Standard library only**, newline-delimited JSON-RPC 2.0 on stdin/stdout, the
  handshake of MCP revision 2025-11-25 (and the earlier revisions a client may ask for).
  Nothing but protocol messages is ever written to stdout: report code runs with stdout
  captured, and colour is off.

The repository is the nearest directory at or above ``--root`` (default: the project
directory the host names in ``CLAUDE_PROJECT_DIR``, else the working directory) that
holds ``ea.config.yaml``. Every call reads the model from disk again, so an answer is
never staler than the files.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, BinaryIO, Callable

from jsonschema import Draft202012Validator

from . import (
    __version__,
    airegister,
    analyst,
    contextpack,
    diff as diff_mod,
    docgen,
    dora,
    dsl,
    gdpr,
    i18n,
    impact,
    query as query_mod,
    readiness,
    reports,
    security,
    timeline,
    validate,
)

SERVER_NAME = "ea-skills"
# Newest first: an unsupported request is answered with the first entry, as the
# lifecycle specification asks.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
RESOURCE_NOT_FOUND = -32002

DESCRIPTION_URI = "easkills://architecture-description"
CONTEXT_PREFIX = "easkills://context/"
CONTEXT_TYPES = ("ApplicationComponent", "Capability")

INSTRUCTIONS = (
    "Read-only access to an enterprise architecture repository's approved model. Every "
    "answer is a deterministic report; nothing here changes the repository. Staging "
    "proposals are not visible. Changes go through the repository's own review: files in "
    "model/staging/, then `easkills promote`."
)

# The domain errors a report raises for a bad question (an unknown id, nothing in scope).
# They are answers the caller should read, so they become tool errors, not protocol errors.
DOMAIN_ERRORS: tuple[type[BaseException], ...] = (
    airegister.AiActError,
    contextpack.ContextError,
    diff_mod.DiffError,
    dora.DoraError,
    gdpr.GdprError,
    impact.ImpactError,
    query_mod.QueryError,
    timeline.TimelineError,
    ValueError,
)


def find_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / dsl.CONFIG_FILENAME).is_file():
            return candidate
    return start


def _as_of(arguments: dict[str, Any]) -> date | None:
    raw = arguments.get("asOf")
    return date.fromisoformat(raw) if raw else None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    run: Callable[[Path, dict[str, Any]], tuple[str, Any]]
    required: tuple[str, ...] = ()

    def definition(self) -> dict[str, Any]:
        schema: dict[str, Any] = {"type": "object", "properties": self.properties, "additionalProperties": False}
        if self.required:
            schema["required"] = list(self.required)
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": schema,
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        }


AS_OF = {"asOf": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$", "description": "Evaluate dates against this day (YYYY-MM-DD); default today."}}
LANG = {"lang": {"enum": list(i18n.LANGUAGES), "description": "Language of the generated document."}}
SCOPE = {"scope": {"type": "string", "description": "Element id."}}


def _register(module: Any, root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    """The document itself, never its JSON: a host that prefers structured content would
    otherwise hand the model the rows without the notice above them or the gap section,
    which are the two parts that keep a generated register from passing as a filing."""
    register = module.build(root, today=_as_of(arguments))
    if not register.in_scope:
        return module.render(register), None
    return module.markdown(register, arguments.get("lang", i18n.DEFAULT)), None


def _validate(root: Path, _arguments: dict[str, Any]) -> tuple[str, Any]:
    report = validate.validate(root, zone="approved")
    return report.render(), report.as_dict()


def _report(build: Callable[..., dict[str, Any]], render: Callable[[dict[str, Any]], str]) -> Callable[[Path, dict[str, Any]], tuple[str, Any]]:
    def run(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
        data = build(root, today=_as_of(arguments))
        return render(data), data

    return run


def _readiness(root: Path, _arguments: dict[str, Any]) -> tuple[str, Any]:
    report = readiness.analyse(root, zone="approved")
    return report.render(), report.as_dict()


def _impact(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    report = impact.analyse(root, scope=arguments["scope"], depth=arguments.get("depth"), today=_as_of(arguments))
    return impact.render(report), report.as_dict()


def _exposure(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    report = security.exposure(root, zone="approved", depth=arguments.get("depth"))
    return security.render_exposure(report), report.as_dict()


def _query(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    data = query_mod.run(
        root,
        zone="approved",
        types=arguments.get("types"),
        where=arguments.get("where"),
        start=arguments.get("from"),
        hops=arguments.get("hops", 1),
        relations=arguments.get("relations"),
        direction=arguments.get("direction", "both"),
        show=arguments.get("show"),
    )
    return query_mod.render(data), data


def _plateaus(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    data = diff_mod.plateaus(root, arguments["from"], arguments["to"])
    return diff_mod.render_plateaus(data), data


def _since(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    data = diff_mod.since(root, arguments["ref"])
    return diff_mod.render_since(data), data


def _trend(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    data = timeline.trend(root, last=arguments.get("last"))
    return timeline.render_trend(data), data


def _context(root: Path, arguments: dict[str, Any]) -> tuple[str, Any]:
    pack = contextpack.build(root, scope=arguments["scope"], today=_as_of(arguments))
    return pack.markdown, None


def _rtm(root: Path, _arguments: dict[str, Any]) -> tuple[str, Any]:
    matrix = analyst.rtm(root, zone="approved")
    return analyst.render_rtm(matrix), matrix.as_dict()


def _glossary(root: Path, _arguments: dict[str, Any]) -> tuple[str, Any]:
    data = analyst.glossary(root)
    return analyst.render_glossary(data), data.as_dict()


TOOLS: tuple[Tool, ...] = (
    Tool("validate", "Run the model gate over the approved zone: every finding with its rule code.", {}, _validate),
    Tool("kpi", "Model-quality and portfolio metrics on a date.", AS_OF, _report(reports.kpi, reports.render_kpi)),
    Tool("trend", "The KPI series the repository has committed, and what regressed since the previous snapshot.",
         {"last": {"type": "integer", "minimum": 1, "description": "Show only the last N snapshots."}}, _trend),
    Tool("staleness", "Review age of every approved element.", AS_OF, _report(reports.staleness, reports.render_staleness)),
    Tool("debt", "The EA-debt register: smells, overlaps, obsolescence, each with its elements.", AS_OF, _report(reports.debt, reports.render_debt)),
    Tool("roadmap", "Plateaus in date order, what each holds, the gaps, and Migrate/Eliminate decisions no plateau schedules.", AS_OF, _report(reports.roadmap, reports.render_roadmap)),
    Tool("readiness", "Per-layer definition of done: the checkpoints each layer has not met, naming elements.", {}, _readiness),
    Tool("impact", "Blast radius of a change to one element, with the stakeholders to inform.",
         {**SCOPE, "depth": {"type": "integer", "minimum": 1}, **AS_OF}, _impact, ("scope",)),
    Tool("exposure", "What an attacker holding each publicly exposed element could reach.",
         {"depth": {"type": "integer", "minimum": 1}}, _exposure),
    Tool(
        "query",
        "Find elements by type and property, optionally within N hops of one element along chosen relationships. "
        "Conditions: key=value, key!=value, key~token (membership in a space-joined value), key= (absent).",
        {
            "types": {"type": "array", "items": {"type": "string"}},
            "where": {"type": "array", "items": {"type": "string"}},
            "from": {"type": "string"},
            "hops": {"type": "integer", "minimum": 1},
            "relations": {"type": "array", "items": {"type": "string"}},
            "direction": {"enum": list(query_mod.DIRECTIONS)},
            "show": {"type": "array", "items": {"type": "string"}},
        },
        _query,
    ),
    Tool("diff_plateaus", "What enters, leaves and stays between two plateaus, and the gaps at either end.",
         {"from": {"type": "string"}, "to": {"type": "string"}}, _plateaus, ("from", "to")),
    Tool("diff_since", "Elements, relationships and views added, removed or changed in the approved zone since a git commit.",
         {"ref": {"type": "string", "description": "A commit, tag or branch."}}, _since, ("ref",)),
    Tool("context", "The agent context pack for one element or capability: what governs it and what it depends on.",
         {**SCOPE, **AS_OF}, _context, ("scope",)),
    Tool("rtm", "Requirement traceability: what each obligation binds, what realizes it, what evidences it.", {}, _rtm),
    Tool("glossary", "The entity table as a glossary, with the facts and elements behind each term.", {}, _glossary),
    Tool("dora_register", "The DORA Register of Information generated from the model, gaps named.", {**AS_OF, **LANG},
         lambda root, arguments: _register(dora, root, arguments)),
    Tool("ai_act_register", "The EU AI Act system inventory generated from the model, gaps named.", {**AS_OF, **LANG},
         lambda root, arguments: _register(airegister, root, arguments)),
    Tool("gdpr_register", "The GDPR Art. 30 record of processing generated from the model, gaps named.", {**AS_OF, **LANG},
         lambda root, arguments: _register(gdpr, root, arguments)),
)
TOOL_INDEX = {tool.name: tool for tool in TOOLS}


class Server:
    """One stdio session. ``handle`` maps a parsed message to a response (or None)."""

    def __init__(self, root: Path):
        self.root = root
        self.protocol: str | None = None

    # ---------------------------------------------------------------- dispatch

    def handle(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "not a JSON-RPC 2.0 request")
        method = message["method"]
        if "id" not in message:
            return None  # a notification: initialized, cancelled -- nothing to answer
        request_id = message["id"]
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _error(request_id, INVALID_PARAMS, "params must be an object")
        if method == "ping":
            return _result(request_id, {})
        if method == "initialize":
            return _result(request_id, self._initialize(params))
        handler = {
            "tools/list": self._tools_list,
            "tools/call": self._tools_call,
            "resources/list": self._resources_list,
            "resources/templates/list": self._templates_list,
            "resources/read": self._resources_read,
        }.get(method)
        if handler is None:
            return _error(request_id, METHOD_NOT_FOUND, f"method not supported: {method}")
        if self.protocol is None:
            return _error(request_id, INVALID_REQUEST, "send initialize first")
        try:
            return _result(request_id, handler(params))
        except _ProtocolError as exc:
            return _error(request_id, exc.code, str(exc))

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        self.protocol = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": self.protocol,
            "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    # ------------------------------------------------------------------- tools

    def _tools_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": [tool.definition() for tool in TOOLS]}

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        tool = TOOL_INDEX.get(name) if isinstance(name, str) else None
        if tool is None:
            raise _ProtocolError(INVALID_PARAMS, f"unknown tool: {name}")
        arguments = params.get("arguments") or {}
        problems = sorted(
            Draft202012Validator(tool.definition()["inputSchema"]).iter_errors(arguments), key=lambda e: e.message
        )
        if problems:
            return _tool_error(f"invalid arguments for {name}: {problems[0].message}")
        try:
            text, structured = _quietly(lambda: tool.run(self.root, arguments))
        except DOMAIN_ERRORS as exc:
            return _tool_error(str(exc))
        except Exception as exc:  # a report crashing is a bug, but never a dead session
            return _tool_error(f"internal error in {name}: {type(exc).__name__}: {exc}")
        result: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": False}
        if isinstance(structured, dict):
            result["structuredContent"] = structured
        return result

    # --------------------------------------------------------------- resources

    def _resources_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        model, _documents, _config = _quietly(lambda: dsl.load(self.root, "approved"))
        resources = [
            {
                "uri": DESCRIPTION_URI,
                "name": "architecture-description",
                "title": "Architecture description",
                "description": "The ISO 42010-shaped architecture description, generated from the approved model.",
                "mimeType": "text/markdown",
            }
        ]
        for element in sorted(model.elements.values(), key=lambda e: e.id):
            if element.type in CONTEXT_TYPES:
                resources.append(
                    {
                        "uri": CONTEXT_PREFIX + element.id,
                        "name": f"context-{element.id}",
                        "title": f"Context pack: {element.name}",
                        "mimeType": "text/markdown",
                    }
                )
        return {"resources": resources}

    def _templates_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {
            "resourceTemplates": [
                {
                    "uriTemplate": CONTEXT_PREFIX + "{id}",
                    "name": "context-pack",
                    "title": "Context pack for any approved element",
                    "mimeType": "text/markdown",
                }
            ]
        }

    def _resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        if uri == DESCRIPTION_URI:
            model, _documents, _config = _quietly(lambda: dsl.load(self.root, "approved"))
            text = _quietly(lambda: docgen.build_markdown(model))
        elif isinstance(uri, str) and uri.startswith(CONTEXT_PREFIX):
            scope = uri[len(CONTEXT_PREFIX):]
            try:
                text = _quietly(lambda: contextpack.build(self.root, scope=scope).markdown)
            except contextpack.ContextError as exc:
                raise _ProtocolError(RESOURCE_NOT_FOUND, str(exc)) from exc
        else:
            raise _ProtocolError(RESOURCE_NOT_FOUND, f"resource not found: {uri}")
        return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}


class _ProtocolError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _quietly(call: Callable[[], Any]) -> Any:
    """Run report code with stdout captured: one stray print would corrupt the stream."""
    with contextlib.redirect_stdout(io.StringIO()):
        return call()


def serve(root: Path, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> int:
    """Answer newline-delimited JSON-RPC from ``stdin`` until it closes."""
    os.environ["NO_COLOR"] = "1"
    source = stdin if stdin is not None else sys.stdin.buffer
    sink = stdout if stdout is not None else sys.stdout.buffer
    server = Server(find_root(root))

    def send(message: dict[str, Any]) -> None:
        # Bytes, not text: a Windows text stream would turn the delimiter into CRLF.
        sink.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n")
        sink.flush()

    for raw in source:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            send(_error(None, PARSE_ERROR, "not valid JSON"))
            continue
        response = server.handle(message)
        if response is not None:
            send(response)
    return 0


def default_root() -> Path:
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(project) if project else Path.cwd()
