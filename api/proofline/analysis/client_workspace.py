"""S5: the client workspace's own small surface -- a summary, "your
questions" (projected from case `ask_client`/`client_answered` threads,
not the case machinery around them), and "your documents" (found from the
packet's own `uploaded_by`, never guessed). Signing itself reuses Step 8's
`authorize_filing`/`build_package` -- nothing here writes anything.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.analysis.changes import changed_since_last_seen
from proofline.analysis.filing import build_package
from proofline.db.repository import (
    get_last_seen,
    get_latest_filed_record,
    list_cases,
    list_events_for_entity,
)
from proofline.packet import Packet
from proofline.provenance.resolver import UnresolvedReferenceError, resolve
from proofline.security.actors import Actor


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def client_summary(session: Session, packet: Packet) -> dict[str, Any]:
    rv = packet.return_versions[-1]
    result = {}
    for jurisdiction, summary in (
        ("federal", rv.summary.federal),
        ("california", rv.summary.california),
    ):
        filed = get_latest_filed_record(session, jurisdiction)
        result[jurisdiction] = {
            "balance_due": summary.balance_due,
            "label": "Filed" if filed is not None else f"Engine {rv.version}",
        }
    return result


def _resolve_answer_text(packet: Packet, ref: str | None) -> str | None:
    if not ref:
        return None
    try:
        resolved = resolve(ref, packet)
    except UnresolvedReferenceError:
        return ref
    value = resolved.value
    if resolved.kind == "questionnaire_item":
        return str(value.answer)
    if resolved.kind == "message":
        return value.text
    if resolved.kind == "call_note":
        return " ".join(value.notes)
    return str(value)


def client_questions(session: Session, packet: Packet) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    for case in list_cases(session):
        events = list_events_for_entity(session, "case", case.case_id)
        pending_question: str | None = None
        pending_asked_at = None
        for event in events:
            if event.event_type == "case_client_asked":
                pending_question = event.payload.get("question")
                pending_asked_at = event.occurred_at
            elif event.event_type == "case_client_answered" and pending_question:
                threads.append(
                    {
                        "case_id": case.case_id,
                        "question": pending_question,
                        "asked_at": _iso(pending_asked_at),
                        "answer": _resolve_answer_text(
                            packet, event.payload.get("evidence_ref")
                        ),
                        "answered_at": _iso(event.occurred_at),
                    }
                )
                pending_question = None
        if pending_question:
            threads.append(
                {
                    "case_id": case.case_id,
                    "question": pending_question,
                    "asked_at": _iso(pending_asked_at),
                    "answer": None,
                    "answered_at": None,
                }
            )
    return threads


def client_documents(session: Session, packet: Packet) -> list[dict[str, Any]]:
    documents = [
        {
            "id": document.id,
            "title": document.title,
            "document_type": document.document_type,
            "issuer": document.issuer,
            "received_at": document.received_at,
            "kind": "uploaded",
        }
        for document in packet.documents
        if document.uploaded_by == "client"
    ]
    for jurisdiction in ("federal", "california"):
        filed = get_latest_filed_record(session, jurisdiction)
        if filed is not None:
            documents.append(
                {
                    "id": filed.id,
                    "title": f"Filed copy -- {jurisdiction}",
                    "document_type": "filed_record",
                    "issuer": None,
                    "received_at": _iso(filed.accepted_at),
                    "kind": "filed",
                }
            )
    return documents


def client_changes(
    session: Session, packet: Packet, actor: Actor
) -> list[dict[str, Any]]:
    """ "What changed since you last looked", scoped to what a client may
    see (B14/B26, reused rather than rebuilt) -- only cases that have a
    client-facing question thread at all."""
    thread_case_ids = {
        thread["case_id"] for thread in client_questions(session, packet)
    }
    changed = []
    for case in list_cases(session):
        if case.case_id not in thread_case_ids:
            continue
        last_seen = get_last_seen(session, actor.id, "case", case.case_id)
        if last_seen is not None and changed_since_last_seen(
            case.updated_at, last_seen
        ):
            changed.append(
                {
                    "case_id": case.case_id,
                    "label": case.observed,
                    "changed_at": _iso(case.updated_at),
                }
            )
    return changed


def client_package_summary(session: Session, packet: Packet) -> dict[str, Any]:
    """A plain-language stand-in for "show the client the package's two
    fingerprints... before they sign" (docs/PLAN.md, W4) -- reuses
    `build_package` rather than a second summary scheme."""
    rv = packet.return_versions[-1]
    package = build_package(session, packet, rv)
    return {
        "reference": package.reference,
        "amounts_fingerprint": package.amounts_fingerprint,
        "identity_fingerprint": package.identity_fingerprint,
        "engine_version": package.engine_version,
        "summary": client_summary(session, packet),
    }
