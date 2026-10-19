from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from proofline.packet import load_packet
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


def _line_trace_dict(trace: LineTrace) -> dict:
    return {
        "line_key": trace.line_key,
        "version": trace.version,
        "primary_sources": sorted(trace.primary_sources),
        "other_sources": [_other_source_dict(o) for o in trace.other_sources],
        "excluded": [_excluded_dict(e) for e in trace.excluded],
        "note": trace.note,
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
def get_trace_line(line_key: str, actor: Actor = Depends(get_current_actor)) -> dict:
    packet = load_packet()
    try:
        trace = trace_line(packet, line_key)
    except KeyError:
        raise HTTPException(status_code=404, detail="line not found") from None
    except UnresolvedReferenceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return redact_for_actor(actor, packet, _line_trace_dict(trace))


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
