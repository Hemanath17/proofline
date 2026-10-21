from __future__ import annotations

import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.db.connection import get_session
from proofline.db.repository import list_adjustments
from proofline.packet import ExtractedValue, Packet, ReturnVersion, load_packet
from proofline.provenance.resolver import Resolved, UnresolvedReferenceError, resolve
from proofline.provenance.tracing import (
    DocumentTrace,
    ExcludedDocument,
    LineTrace,
    OtherSource,
    trace_document,
    trace_line,
)
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
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
    actor: Actor = Depends(require_non_client),
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
    document_id: str, actor: Actor = Depends(require_non_client)
) -> dict:
    packet = load_packet()
    try:
        packet.document(document_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found") from None
    trace = trace_document(packet, document_id)
    return redact_for_actor(actor, packet, _document_trace_dict(trace))


_DOC_PAGE_REF_RE = re.compile(r"^doc:(D\d{2})#page(\d+)$")

_TYPED_REFERENCE_LABELS = {
    "prior_years": "Prior-year record",
    "tax_agency_records": "Tax agency record",
    "asset": "Asset record",
    "household_person": "Household fact",
    "engine_parameter": "Engine parameter",
    "fx_rate": "Exchange rate",
    "timeline_event": "Timeline event",
    "return_version": "Return version",
    "line": "Return line",
}


def _evidence_preview_dict(packet: Packet, resolved: Resolved) -> dict:
    """One evidence reference (any format docs/PACKET.md names), shaped
    into the small closed set of cards the Case Detail evidence section
    and the Trace drawer's evidence view render (docs/UX.md S2 "Evidence:
    one card per evidence reference... a click opens the Trace drawer",
    S4 "non-document sources render as typed cards"). Built directly on
    `resolve()` -- the same resolver `trace_line`/`trace_document` already
    use -- so this is not a second tracing implementation, just a second
    *shape* for the one resolver's output."""
    ref, kind, value = resolved.ref, resolved.kind, resolved.value

    if kind == "extracted_value":
        document = packet.document(value.document_id)
        return {
            "kind": "document_field",
            "ref": ref,
            "document_id": value.document_id,
            "document_title": document.title,
            "page": value.page,
            "field": value.field,
            "label": value.label,
            "value": value.value,
            "text_as_read": value.text_as_read,
            "position": _position_dict(value),
        }

    if kind == "document":
        return {
            "kind": "document",
            "ref": ref,
            "document_id": value.id,
            "title": value.title,
            "document_type": value.document_type,
            "issuer": value.issuer,
        }

    if kind == "document_page":
        match = _DOC_PAGE_REF_RE.match(ref)
        document_id = match.group(1) if match else None
        document = packet.document(document_id) if document_id else None
        return {
            "kind": "document_page",
            "ref": ref,
            "document_id": document_id,
            "document_title": document.title if document else None,
            "page": value.page,
        }

    if kind == "questionnaire_item":
        return {
            "kind": "questionnaire_item",
            "ref": ref,
            "question": value.question,
            "answer": value.answer,
            "answered_by": value.answered_by,
            "answered_at": value.answered_at,
        }

    if kind == "message":
        return {
            "kind": "message",
            "ref": ref,
            "from": value.from_,
            "to": value.to,
            "sent_at": value.sent_at,
            "text": value.text,
        }

    if kind == "call_note":
        return {
            "kind": "call_note",
            "ref": ref,
            "date": value.date,
            "participants": list(value.participants),
            "notes": list(value.notes),
        }

    label = _TYPED_REFERENCE_LABELS.get(kind, kind.replace("_", " "))
    dumped = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return {"kind": "typed", "ref": ref, "label": label, "value": dumped}


@router.get("/trace/evidence")
def get_trace_evidence(
    ref: str = Query(...),
    actor: Actor = Depends(require_non_client),
) -> dict:
    """A clickable preview for one evidence reference, of any format
    docs/PACKET.md names -- used by the Case Detail evidence section and
    the proposal's evidence picker (docs/UX.md S2), reusing the Trace
    drawer shell on the frontend. `ref` is a query param rather than a
    path segment so refs containing `:`, `/` or `#` (e.g. `doc:D01#page3`,
    `py:/asset_records/0`) never collide with path routing."""
    packet = load_packet()
    try:
        resolved = resolve(ref, packet)
    except UnresolvedReferenceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return redact_for_actor(actor, packet, _evidence_preview_dict(packet, resolved))
