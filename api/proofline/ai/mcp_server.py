"""An MCP server exposing the Evidence Investigator's four read-only
tools to an outside agent, over the Model Context Protocol instead of an
in-process Python call. Same four tools (`proofline.ai.tools`), same
`ai-assistant` role and the same masking -- a different transport for the
same tools, never a second surface with its own rules (CLAUDE.md). There
is no actor header here: every call this server makes runs as the one
synthetic `ai-assistant` actor, the same as the in-process agent.

Run as its own entrypoint:
    python -m proofline.ai.mcp_server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from sqlalchemy.orm import Session

from proofline.ai import tools as ai_tools
from proofline.db.connection import get_engine
from proofline.packet import load_packet
from proofline.security.actors import AI_ASSISTANT_ID, Actor, load_actors

mcp = FastMCP(
    name="proofline-evidence-investigator",
    instructions=(
        "Read-only access to one tax workpaper: open_case, trace_claim, "
        "read_evidence, find_related_documents. All reads are masked as an "
        "uncleared staff member would see them. No write access exists."
    ),
)


def _actor() -> Actor:
    return load_actors(load_packet())[AI_ASSISTANT_ID]


@mcp.tool()
def open_case(case_id: str) -> dict:
    """Read one case: its status, claims, evidence_refs, proposals and decisions."""
    with Session(get_engine()) as session:
        return ai_tools.open_case(_actor(), session, case_id)


@mcp.tool()
def trace_claim(claim_id: str) -> dict:
    """Trace one claim, line or document identity in both directions: its
    inputs, what uses it, and the documents behind it."""
    with Session(get_engine()) as session:
        return ai_tools.trace_claim(_actor(), session, claim_id)


@mcp.tool()
def read_evidence(document_id: str | None = None, claim_id: str | None = None) -> dict:
    """Read a document's own masked text and fields, by document id or by
    a claim/evidence ref that resolves to one."""
    with Session(get_engine()) as session:
        return ai_tools.read_evidence(
            _actor(), session, document_id=document_id, claim_id=claim_id
        )


@mcp.tool()
def find_related_documents(query: str) -> dict:
    """Find documents by exact id or full-text search."""
    with Session(get_engine()) as session:
        return ai_tools.find_related_documents(_actor(), session, query)


if __name__ == "__main__":
    mcp.run()
