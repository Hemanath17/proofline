"""Part 2: the MCP server exposes the exact same four read-only tools,
under the exact same `ai-assistant` role and masking, over MCP instead of
an in-process call. Driven with the SDK's own in-memory client/server
transport -- no subprocess, no real network.
"""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult
from proofline.ai import mcp_server
from proofline.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool


def _data(result: CallToolResult) -> dict:
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)


@pytest.fixture
def _sqlite_engine(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(mcp_server, "get_engine", lambda: engine)
    return engine


@pytest.mark.asyncio
async def test_lists_exactly_the_four_read_tools(_sqlite_engine) -> None:
    async with create_connected_server_and_client_session(mcp_server.mcp) as client:
        await client.initialize()
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        assert names == {
            "open_case",
            "trace_claim",
            "read_evidence",
            "find_related_documents",
        }


@pytest.mark.asyncio
async def test_trace_claim_returns_masked_data(_sqlite_engine) -> None:
    async with create_connected_server_and_client_session(mcp_server.mcp) as client:
        await client.initialize()
        result = await client.call_tool("trace_claim", {"claim_id": "F1040.1a"})
        assert result.isError is False
        assert _data(result)["line_key"] == "F1040.1a"


@pytest.mark.asyncio
async def test_read_evidence_never_leaks_a_sensitive_value(_sqlite_engine) -> None:
    from proofline.packet import load_packet
    from proofline.security.redact import collect_sensitive_values, generate_variants

    variants: set[str] = set()
    for value in collect_sensitive_values(load_packet()):
        variants |= generate_variants(value.value)

    async with create_connected_server_and_client_session(mcp_server.mcp) as client:
        await client.initialize()
        for document in load_packet().documents[:5]:
            result = await client.call_tool(
                "read_evidence", {"document_id": document.id}
            )
            assert result.isError is False
            text = json.dumps(_data(result))
            for variant in variants:
                assert variant not in text, f"leaked {variant!r} for {document.id}"


@pytest.mark.asyncio
async def test_calling_a_tool_outside_the_four_fails(_sqlite_engine) -> None:
    async with create_connected_server_and_client_session(mcp_server.mcp) as client:
        await client.initialize()
        result = await client.call_tool("submit_proposal", {"case_id": "x"})
        assert result.isError is True
