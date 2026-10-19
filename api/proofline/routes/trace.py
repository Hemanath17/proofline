from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.db.connection import get_session
from proofline.db.repository import list_adjustments
from proofline.packet import ExtractedValue, Packet, ReturnVersion, load_packet
from proofline.provenance.resolver import UnresolvedReferenceError
from proofline.provenance.tracing import (
    DocumentTrace,
    ExcludedDocument,
    LineTrace,
    OtherSource,
    trace_document,
    trace_line,
)
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor
from proofline.security.redact import redact_for_actor

router = APIRouter()


def _excluded_dict(excluded: ExcludedDocument) -> dict:
    return {"document_id": excluded.document_id, "reason": excluded.reason}


def _other_source_dict(other: OtherSource) -> dict:
    return {"ref": other.ref, "kind": other.kind}


def _position_dict(value: ExtractedValue) -> dict | None:
    if value.position is None:
        return None
    return {
        "x0": value.position.x0,
        "y0": value.position.y0,
        "x1": value.position.x1,
        "y1": value.position.y1,
    }


def _highlighted_sources(
    packet: Packet, rv: ReturnVersion, line_key: str
) -> list[dict]:
    """Document sources grouped by document then page, each with the
    extracted values this line actually used, numbered in source order
    (docs/UX.md S4: "every field this line used highlighted and
    numbered"). Only `ev-` refs carry a position to highlight; an `asset:`
    ref's nested sources are not expanded here -- the asset itself is
    traced separately if a caller follows it."""
    line = rv.line(line_key)
    by_document: dict[str, dict[int, list[dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    tag = 0
    for ref in line.sources:
        if not ref.startswith("ev-"):
            continue
        value = packet.extracted_value(ref)
        tag += 1
        by_document[value.document_id][value.page].append(
            {
                "ev_id": value.id,
                "field": value.field,
                "label": value.label,
                "tag": tag,
                "position": _position_dict(value),
            }
        )
    sources = []
    for document_id, pages in by_document.items():
        document = packet.document(document_id)
        sources.append(
            {
                "document_id": document_id,
                "title": document.title,
                "pages": [
                    {"page": page_number, "highlights": highlights}
                    for page_number, highlights in sorted(pages.items())
                ],
            }
        )
    return sources


def _line_trace_dict(
    packet: Packet, trace: LineTrace, claim_adjustments: dict[str, object]
) -> dict:
    rv = packet.return_version(trace.version)
    # CONTRACTS.md C3: engine v3 plus any approved adjustment, carried
    # forward exactly along R-SUM/R-CARRY. `workpaper_value` is the one
    # function every rendered number should go through -- `trace.value`/
    # `trace.label` (the line's *own* human label, e.g. "Short-term from
    # Form 8949 box B") stay separate from this provenance labeling.
    computed = workpaper_value(packet, rv, trace.line_key, claim_adjustments)
    return {
        "line_key": trace.line_key,
        "version": trace.version,
        "value": computed.value,
        "provenance": computed.label,
        "label": trace.label,
        "rule": trace.rule,
        "inputs": list(trace.inputs),
        "used_by": list(trace.used_by),
        "primary_sources": sorted(trace.primary_sources),
        "sources": _highlighted_sources(packet, rv, trace.line_key),
        "other_sources": [_other_source_dict(o) for o in trace.other_sources],
        "excluded": [_excluded_dict(e) for e in trace.excluded],
        "note": trace.note,
        "adjustment": computed.adjustment.to_dict() if computed.adjustment else None,
    }


def _document_trace_dict(trace: DocumentTrace) -> dict:
    return {
        "document_id": trace.document_id,
        "version": trace.version,
        "lines_using": list(trace.lines_using),
        "used": trace.used,
        "note": trace.note,
    }


@router.get("/trace/line/{line_key}")
def get_trace_line(
    line_key: str,
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    try:
        trace = trace_line(packet, line_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="line not found") from None
    except UnresolvedReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    claim_adjustments = adjustments_by_claim(list_adjustments(session))
    return redact_for_actor(
        actor, packet, _line_trace_dict(packet, trace, claim_adjustments)
    )


@router.get("/trace/document/{document_id}")
def get_trace_document(
    document_id: str, actor: Actor = Depends(get_current_actor)
) -> dict:
    packet = load_packet()
    try:
        packet.document(document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found") from None
    trace = trace_document(packet, document_id)
    return redact_for_actor(actor, packet, _document_trace_dict(trace))
