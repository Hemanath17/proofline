"""Four read-only tools for the Evidence Investigator. Each one is a thin
wrapper over the EXACT SAME function the API's own read routes call --
tracing, case-reading, masking and document search are enforced once,
there, never reimplemented here (CLAUDE.md: "Permissions get enforced
once, in that shared code, not twice"). Every call takes the calling
`Actor` explicitly and passes it straight through, the same as any other
actor -- in practice this is always the synthetic `ai-assistant` actor
(`proofline.security.actors.AI_ASSISTANT_ID`), which has `clearance=False`,
so every one of these comes back masked exactly as it would for an
uncleared staff member like Marcus.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from proofline.packet import Packet, load_packet
from proofline.provenance.resolver import UnresolvedReferenceError, resolve
from proofline.routes.cases import get_case_detail
from proofline.routes.documents import get_document_detail, get_document_page
from proofline.routes.search import search_route
from proofline.routes.trace import get_trace_document, get_trace_line
from proofline.security.actors import Actor

_DOCUMENT_ID_RE = re.compile(r"^D\d{2}$")


def open_case(actor: Actor, session: Session, case_id: str) -> dict:
    """The case under investigation, its proposals and decisions -- the
    exact function `routes/cases.py`'s `GET /api/cases/{case_id}` calls."""
    return get_case_detail(case_id, actor=actor, session=session)


def trace_claim(
    actor: Actor, session: Session, claim_id: str, version: str = "v3"
) -> dict:
    """Both directions of the provenance resolver for one claim identity
    (CONTRACTS.md "Claim identity"): a line key traces its own inputs and
    dependents, a document id traces which lines use it, and an asset
    claim traces every line that cites it. Calls `routes/trace.py`'s own
    `get_trace_line`/`get_trace_document` directly -- never a second
    tracing implementation."""
    packet = load_packet()
    try:
        resolved = resolve(claim_id, packet, version)
    except UnresolvedReferenceError as exc:
        raise ValueError(
            f"{claim_id!r} is not a traceable claim, line or document id: {exc}"
        ) from None

    if resolved.kind == "line":
        return get_trace_line(claim_id, actor=actor, session=session)
    if resolved.kind == "document":
        return get_trace_document(claim_id, actor=actor)
    if resolved.kind == "asset":
        rv = packet.return_version(version)
        lines = [
            get_trace_line(line.key, actor=actor, session=session)
            for line in rv.lines
            if claim_id in line.sources
        ]
        if not lines:
            raise ValueError(
                f"{claim_id!r} is not used by any line in return version {version}"
            )
        return {"asset_id": claim_id, "lines": lines}
    raise ValueError(
        f"{claim_id!r} resolves to a {resolved.kind}, which trace_claim doesn't "
        "trace directly -- try read_evidence for its underlying document instead"
    )


def _document_id_for_claim(packet: Packet, claim_id: str) -> str:
    if _DOCUMENT_ID_RE.match(claim_id):
        return claim_id
    try:
        resolved = resolve(claim_id, packet)
    except UnresolvedReferenceError as exc:
        raise ValueError(f"can't find a document behind {claim_id!r}: {exc}") from None
    if resolved.kind == "extracted_value":
        return resolved.value.document_id
    if resolved.kind == "document":
        return claim_id
    raise ValueError(
        f"{claim_id!r} resolves to a {resolved.kind}, not a single document -- "
        "try trace_claim first to find the document(s) behind it"
    )


def read_evidence(
    actor: Actor,
    session: Session,
    *,
    document_id: str | None = None,
    claim_id: str | None = None,
) -> dict:
    """A document's own metadata and page text, masked exactly as
    `redact_for_actor` masks it for an uncleared staff actor -- never raw
    packet content. Looks up by document id directly, or resolves a claim/
    evidence ref to the document behind it first."""
    if document_id is None and claim_id is None:
        raise ValueError("read_evidence needs either document_id or claim_id")
    if document_id is None:
        document_id = _document_id_for_claim(load_packet(), claim_id)  # type: ignore[arg-type]
    detail = get_document_detail(document_id, actor=actor, session=session)
    pages = [
        get_document_page(document_id, page_number, actor=actor, session=session)
        for page_number in detail["pages"]
    ]
    return {**detail, "page_content": pages}


def find_related_documents(actor: Actor, session: Session, query: str) -> dict:
    """Exact-id lookup first, then Step 9's full-text search -- the exact
    function `routes/search.py`'s `GET /api/search` calls for the second
    part."""
    packet = load_packet()
    results: list[dict] = []
    try:
        document = packet.document(query.strip())
    except KeyError:
        document = None
    if document is not None:
        results.append(
            {
                "type": "document",
                "id": document.id,
                "title": document.title,
                "snippet": document.title,
            }
        )
    body = search_route(q=query, actor=actor, session=session)
    seen = {(r["type"], r["id"]) for r in results}
    for result in body["results"]:
        key = (result["type"], result["id"])
        if key not in seen:
            results.append(result)
            seen.add(key)
    return {"results": results}
