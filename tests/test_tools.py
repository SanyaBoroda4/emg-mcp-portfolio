"""Offline tests for the MCP server: tool registry, write safety, docstrings, bridge errors.
No network: every HTTP call goes to an httpx.MockTransport."""
import asyncio
import importlib
import json

import httpx
import pytest

import emg_mcp

WRITE_TOOLS = {"create_activity"}


@pytest.fixture(scope="module")
def tools():
    return {t.name: t for t in asyncio.run(emg_mcp.mcp.list_tools())}


@pytest.fixture
def bridge(monkeypatch):
    """Route the server's HTTP client to a fake bridge and record every request."""
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(emg_mcp, "http", httpx.Client(transport=httpx.MockTransport(handler)))
    return seen


def test_registers_40_tools(tools):
    assert len(tools) == 40


def test_create_activity_is_the_only_write_tool(tools):
    with_dry_run = {n for n, t in tools.items() if "dry_run" in t.inputSchema.get("properties", {})}
    assert with_dry_run == WRITE_TOOLS


def test_write_tools_default_to_dry_run(tools):
    for name in WRITE_TOOLS:
        assert tools[name].inputSchema["properties"]["dry_run"]["default"] is True


@pytest.mark.parametrize("name", sorted(
    t.name for t in asyncio.run(emg_mcp.mcp.list_tools()) if t.name not in WRITE_TOOLS))
def test_read_tool_docstring_says_read_only(tools, name):
    assert "READ-ONLY" in tools[name].description


def test_create_activity_sends_a_preview_unless_told_otherwise(bridge):
    emg_mcp.create_activity(job_id=101, activity_type="Template", start_date="2026-01-05")
    (req,) = bridge
    assert req.method == "POST"
    assert req.url.path == "/api/scheduler/create-activity"
    assert json.loads(req.content)["dryRun"] is True


def test_create_activity_writes_only_with_explicit_dry_run_false(bridge):
    emg_mcp.create_activity(job_id=101, activity_type="Template", start_date="2026-01-05", dry_run=False)
    assert json.loads(bridge[0].content)["dryRun"] is False


def test_requests_go_to_the_configured_bridge(bridge):
    emg_mcp.cache_status()
    assert str(bridge[0].url).startswith(emg_mcp.BASE + "/api/")


def test_unreachable_bridge_becomes_an_error_code(monkeypatch):
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(emg_mcp, "http", httpx.Client(transport=httpx.MockTransport(down)))
    out = emg_mcp.job_overview(job_id=101)
    assert out["ErrorCode"] == "BRIDGE_UNAVAILABLE"


def test_non_json_reply_becomes_an_error_code(monkeypatch):
    monkeypatch.setattr(emg_mcp, "http", httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(502, text="Bad Gateway"))))
    out = emg_mcp.job_overview(job_id=101)
    assert out["ErrorCode"] == "BRIDGE_UNAVAILABLE"
    assert "502" in out["Error"]


def test_bridge_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("EMG_BRIDGE_URL", "https://bridge.test.invalid/")
    try:
        assert importlib.reload(emg_mcp).BASE == "https://bridge.test.invalid"
    finally:
        monkeypatch.delenv("EMG_BRIDGE_URL")
        importlib.reload(emg_mcp)


def test_bridge_url_defaults_to_a_placeholder():
    assert emg_mcp.BASE == "https://bridge.example.com"
