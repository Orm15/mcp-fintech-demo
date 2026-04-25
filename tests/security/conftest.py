"""
Security test fixtures — black-box tests against the running compose stack.

These tests assume `docker compose up -d` is running and the MCP server
is reachable at http://localhost:8000/mcp/. CI brings the stack up
before invoking pytest with `-m security`.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

MCP_URL = os.getenv("MCP_URL", "http://localhost:8000/mcp/")
USER_KEY = "usr-maria-garcia-a3f9k2"
ADMIN_KEY = "adm-fintech-x9p2m7k1"


def _is_stack_up() -> bool:
    try:
        r = httpx.post(
            MCP_URL,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "probe", "version": "1"},
                },
            },
            timeout=2.0,
        )
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _is_stack_up(),
    reason="Stack no levantado en " + MCP_URL + " — corré `docker compose up -d` primero",
)


def _parse_sse(body: str) -> dict:
    """SSE → dict del primer event 'data:'."""
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise ValueError(f"no SSE data in: {body[:200]}")


@pytest.fixture
def mcp_session():
    """Crea una sesión MCP inicializada y devuelve un caller."""
    init = httpx.post(
        MCP_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        timeout=5.0,
    )
    sid = init.headers.get("mcp-session-id")
    assert sid, f"no session id in init response: {dict(init.headers)}"

    httpx.post(
        MCP_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Session-Id": sid,
        },
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=5.0,
    )

    def call(tool: str, args: dict, api_key: str | None = USER_KEY) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Session-Id": sid,
        }
        if api_key:
            headers["X-API-Key"] = api_key
        r = httpx.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
            timeout=10.0,
        )
        data = _parse_sse(r.text)
        # Tool result viene en {result:{content:[{text:"json...."}]}}
        text = data["result"]["content"][0]["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    return call
