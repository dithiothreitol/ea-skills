"""Phase 8.5, surface: query, diagram export, heatmaps, and the read-only MCP server.

What these must never do is the first thing tested. ``query`` and ``serve`` cannot
change a file (D9): the server's tool table is held to an allowlist, every tool runs over
a copy of a repository, and the copy is byte-compared afterwards. The export is held to
the procedures PlantUML's ArchiMate library actually defines, because one wrong name
fails a whole diagram in the tool somebody pasted it into.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest

from easkills import cli, dsl, export, genschema, oracle, query, render, serve

REPO_ROOT = Path(__file__).resolve().parents[1]
FINCO = REPO_ROOT / "eval" / "fixtures" / "finco"


@pytest.fixture
def repo(tmp_path, example_root) -> Path:
    target = tmp_path / "repo"
    shutil.copytree(example_root, target)
    return target


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------- query


def test_query_filters_by_type_and_shows_property_columns(example_root):
    data = query.run(example_root, types=["ApplicationComponent"], show=["timeDisposition"])
    assert [(r["id"], r["timeDisposition"]) for r in data["results"]] == [
        ("app-erp-core", "Tolerate"),
        ("app-order-portal", "Invest"),
        ("app-wms", "Migrate"),
    ]


def test_membership_reads_a_combined_scope_and_equality_does_not():
    """The 0.15.0 lesson, as a query: `regulatoryScope=gdpr` misses `dora gdpr`."""
    assert {r["id"] for r in query.run(FINCO, where=["regulatoryScope~gdpr"])["results"]} == {"app-crm", "app-kyc-screening"}
    assert not query.run(FINCO, where=["regulatoryScope=gdpr"])["results"]


def test_empty_value_means_absent_and_not_equal_includes_absent(example_root):
    absent = {r["id"] for r in query.run(example_root, where=["timeDisposition="])["results"]}
    assert "app-wms" not in absent and "cap-customer-service" in absent
    others = {r["id"] for r in query.run(example_root, where=["timeDisposition!=Migrate"])["results"]}
    assert "app-wms" not in others and "cap-customer-service" in others


def test_own_fields_are_queryable(example_root):
    rows = query.run(example_root, where=["layer=Strategy", "assumed=false"])["results"]
    assert rows and all(oracle.layer_of(r["type"]) == "Strategy" for r in rows)


def test_hops_walk_relationships_and_the_motivation_binding(example_root):
    data = query.run(example_root, start="app-wms", hops=1, relations=["appliesTo"], direction="in")
    assert [(r["id"], r["via"], r["direction"]) for r in data["results"]] == [
        ("constraint-wms-cloud-budget", "appliesTo", "in")
    ]
    two = {r["id"]: r["hop"] for r in query.run(example_root, start="app-wms", hops=2, relations=["Serving"])["results"]}
    assert two == {"process-order-fulfilment": 1, "service-order-api": 2}


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["--type", "Applicationcomponent"], "not an ArchiMate element type"),
        (["--where", "no operator"], "cannot read the condition"),
        (["--from", "nope"], "not an element"),
        (["--from", "app-wms", "--rel", "Serves"], "not a relationship type"),
        (["--from", "app-wms", "--hops", "0"], "starts at 1"),
    ],
)
def test_a_bad_question_is_a_refusal_naming_the_problem(argv, message, example_root, capsys):
    assert cli.main(["query", "--root", str(example_root), *argv]) == 1
    assert message in capsys.readouterr().out


def test_query_cli_writes_json(example_root, tmp_path):
    out = tmp_path / "q.json"
    assert cli.main(["query", "--root", str(example_root), "--type", "Capability", "--json", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["count"] == 3


# --------------------------------------------------------------------------- export


@pytest.mark.parametrize("element_type", sorted(oracle.element_types()))
def test_every_oracle_type_has_a_plantuml_procedure_the_library_defines(element_type):
    assert export.plantuml_procedure(element_type) in export.PLANTUML_PROCEDURES


@pytest.mark.parametrize("relationship_type", sorted(oracle.relationship_types()))
def test_every_relationship_type_has_a_plantuml_procedure(relationship_type):
    assert f"Rel_{relationship_type}" in export.PLANTUML_PROCEDURES


def test_aliases_are_injective_and_safe():
    ids = ["a.b", "a_b", "a-b", "end", "1st"]
    aliases = export._aliases(ids)
    assert len(set(aliases.values())) == len(ids)
    assert all(alias.replace("_", "").isalnum() and not alias[0].isdigit() for alias in aliases.values())
    assert aliases["end"] != "end", "a Mermaid keyword cannot be a node id"


def test_plantuml_export_of_a_view(example_root):
    model, _documents, _config = dsl.load(example_root, "approved")
    text = export.plantuml(model, model.views["capability-realization"])
    assert text.startswith("@startuml capability-realization\n!include <archimate/Archimate>\n")
    assert 'Application_Component(app_wms, "Warehouse Management System")' in text
    assert "Rel_Realization(app_wms, cap_warehouse_operations" in text
    assert text.endswith("@enduml\n")


def test_mermaid_export_dashes_realization_and_colours_layers(example_root):
    model, _documents, _config = dsl.load(example_root, "approved")
    text = export.mermaid(model, model.views["capability-realization"])
    assert "flowchart TB" in text and "app_wms -.->|Realization| cap_warehouse_operations" in text
    assert f"classDef application fill:{render.LAYER_FILL['Application']}" in text


def test_export_cli_writes_one_file_per_view_byte_stable(example_root, tmp_path, capsys):
    for name in ("a", "b"):
        assert cli.main(["export", "--root", str(example_root), "--format", "mermaid", "--out", str(tmp_path / name)]) == 0
    files = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert files == [f"{v}.mmd" for v in sorted(dsl.load(example_root, "approved")[0].views)]
    for name in files:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    capsys.readouterr()
    assert cli.main(["export", "--root", str(example_root), "--format", "plantuml", "--view", "layered-overview"]) == 0
    assert capsys.readouterr().out.startswith("@startuml layered-overview")
    assert cli.main(["export", "--root", str(example_root), "--format", "plantuml", "--view", "nope"]) == 1


# --------------------------------------------------------------------------- render


@pytest.mark.parametrize(
    ("name", "lines"),
    [
        ("Order Portal", ["Order Portal"]),
        ("Warehouse Management System", ["Warehouse Management", "System"]),
        ("A" * 30, ["A" * 24, "A" * 6]),
        ("Customer Relationship Management Platform Suite", ["Customer Relationship", "Management Platform Sui…"]),
    ],
)
def test_names_wrap_onto_two_lines_and_only_the_second_is_cut(name, lines):
    assert render._wrap(name) == lines


def test_a_heatmap_is_written_beside_the_view_with_a_counting_legend(repo):
    views = repo / "docs" / "views"
    before = {p.name: p.read_bytes() for p in views.iterdir()}
    assert cli.main(["render", "--root", str(repo), "--heatmap", "timeDisposition"]) == 0
    for name, content in before.items():
        assert (views / name).read_bytes() == content, "a heatmap never overwrites the committed view"
    svg = (views / "capability-realization.heatmap-timeDisposition.svg").read_text(encoding="utf-8")
    assert "Capability Realization — timeDisposition" in svg
    assert "Migrate (1)" in svg and "no value (3)" in svg
    assert "stroke-dasharray='4,3'" in svg, "an element with no value is drawn dashed"


def test_a_value_keeps_its_colour_across_views(example_root):
    model, _documents, _config = dsl.load(example_root, "approved")
    colours = render.heatmap_colours(model, "timeDisposition")
    # The closed vocabulary assigns by schema order, so the palette does not depend on
    # which values one view happens to hold.
    assert list(colours) == list(genschema.TIME_DISPOSITIONS)
    first = render.render_view(model, model.views["capability-realization"], "timeDisposition")
    second = render.render_view(model, model.views["layered-overview"], "timeDisposition")
    for value in ("Migrate", "Invest"):
        fill = colours[value]
        assert fill in first and fill in second


# --------------------------------------------------------------------------- serve


EXPECTED_TOOLS = {
    "validate", "kpi", "trend", "staleness", "debt", "roadmap", "readiness", "impact", "exposure",
    "query", "diff_plateaus", "diff_since", "context", "rtm", "glossary",
    "dora_register", "ai_act_register", "gdpr_register",
}
WRITING_COMMANDS = {
    "promote", "propose", "intake-csv", "intake-doc", "import", "compile", "render", "docs",
    "gen-schema", "pin-oracle", "pin-reference", "chunk",
}


def _session(root: Path) -> serve.Server:
    server = serve.Server(root)
    response = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}}}
    )
    assert response["result"]["protocolVersion"] == "2025-11-25"
    return server


def test_the_tool_table_is_the_allowlist_and_every_tool_says_it_is_read_only():
    names = {tool.name for tool in serve.TOOLS}
    assert names == EXPECTED_TOOLS
    assert not {n.replace("_", "-") for n in names} & WRITING_COMMANDS
    assert all(tool.definition()["annotations"]["readOnlyHint"] is True for tool in serve.TOOLS)


ARGUMENTS = {
    "impact": {"scope": "app-wms"},
    "context": {"scope": "app-wms"},
    "diff_plateaus": {"from": "plateau-2026-baseline", "to": "plateau-2028-wms-cloud"},
    "diff_since": {"ref": "HEAD"},
    "query": {"types": ["ApplicationComponent"]},
}


def test_every_tool_answers_and_no_file_changes(repo):
    server = _session(repo)
    before = _tree(repo)
    for tool in serve.TOOLS:
        response = server.handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool.name, "arguments": ARGUMENTS.get(tool.name, {})}}
        )
        result = response["result"]
        text = result["content"][0]["text"]
        assert text and "\x1b[" not in text, f"{tool.name}: empty or coloured output"
        if tool.name != "diff_since":  # the copy is not a git repository: a named refusal
            assert result["isError"] is False, f"{tool.name}: {text}"
        else:
            assert result["isError"] is True and "git" in text
    assert _tree(repo) == before, "serve wrote to the repository"


def test_protocol_negotiation_and_errors(repo):
    server = serve.Server(repo)
    early = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert early["error"]["code"] == serve.INVALID_REQUEST
    unknown_version = server.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}}
    )
    assert unknown_version["result"]["protocolVersion"] == serve.PROTOCOL_VERSIONS[0]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    assert server.handle({"jsonrpc": "2.0", "id": 4, "method": "server/discover"})["error"]["code"] == serve.METHOD_NOT_FOUND
    call = {"jsonrpc": "2.0", "id": 5, "method": "tools/call"}
    assert server.handle({**call, "params": {"name": "promote"}})["error"]["code"] == serve.INVALID_PARAMS
    bad = server.handle({**call, "params": {"name": "impact", "arguments": {"scope": 3}}})["result"]
    assert bad["isError"] and "invalid arguments" in bad["content"][0]["text"]
    missing = server.handle({**call, "params": {"name": "impact", "arguments": {"scope": "nope"}}})["result"]
    assert missing["isError"] and "nope" in missing["content"][0]["text"]
    gone = server.handle({"jsonrpc": "2.0", "id": 6, "method": "resources/read", "params": {"uri": "easkills://nope"}})
    assert gone["error"]["code"] == serve.RESOURCE_NOT_FOUND


def test_resources_serve_the_description_and_context_packs(example_root):
    server = _session(example_root)
    listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list"})["result"]["resources"]
    uris = [r["uri"] for r in listed]
    assert uris[0] == serve.DESCRIPTION_URI and serve.CONTEXT_PREFIX + "app-wms" in uris
    read = server.handle({"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": serve.DESCRIPTION_URI}})
    committed = (example_root / "docs" / "architecture-description.md").read_text(encoding="utf-8")
    assert read["result"]["contents"][0]["text"] == committed, "the same description docs writes"
    templates = server.handle({"jsonrpc": "2.0", "id": 4, "method": "resources/templates/list"})["result"]
    assert templates["resourceTemplates"][0]["uriTemplate"] == serve.CONTEXT_PREFIX + "{id}"


def test_registers_come_back_as_the_document_with_its_notice():
    server = _session(FINCO)
    result = server.handle(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "gdpr_register", "arguments": {"asOf": "2026-07-30"}}}
    )["result"]
    assert "structuredContent" not in result, "a host preferring JSON would drop the notice and the gaps"
    assert result["content"][0]["text"].startswith("# ")


def test_stdio_framing_is_one_json_message_per_line_and_nothing_else(example_root):
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "validate"}},
    ]
    stdin = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in lines) + b"not json\n")
    stdout = io.BytesIO()
    assert serve.serve(example_root / "model", stdin=stdin, stdout=stdout) == 0
    raw = stdout.getvalue()
    assert b"\r" not in raw
    replies = [json.loads(line) for line in raw.splitlines()]
    assert [r.get("id") for r in replies] == [1, 2, None]
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert replies[2]["error"]["code"] == serve.PARSE_ERROR


def test_the_root_is_found_upwards_and_defaults_to_the_project_dir(example_root, monkeypatch, tmp_path):
    assert serve.find_root(example_root / "model" / "approved") == example_root
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert serve.default_root() == tmp_path
    monkeypatch.delenv("CLAUDE_PROJECT_DIR")
    assert serve.default_root() == Path.cwd()


def test_the_plugin_registers_the_server_through_the_wrapper(repo_root):
    manifest = json.loads((repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    server = manifest["mcpServers"]["easkills"]
    assert server["args"] == ["${CLAUDE_PLUGIN_ROOT}/bin/easkills", "serve"]
    # Not a root .mcp.json: in this repository that file would also be read as the
    # project's own MCP configuration, where the plugin root is not defined.
    assert not (repo_root / ".mcp.json").exists()
