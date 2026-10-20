"""B14, B26: the notifications feed. Polling, not a websocket, matching
docs/UX.md's existing "since you last looked" pattern -- built entirely
from events, cases and `last_seen`, which already exist from Steps 5-8.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.analysis.changes import cases_needing_actor, changed_since_last_seen
from proofline.db.repository import (
    get_document_disposition,
    get_last_seen,
    list_cases,
    list_last_seen_entity_ids,
)
from proofline.packet import Packet
from proofline.security.actors import Actor


def _case_summary(case) -> dict[str, Any]:
    return {
        "entity_type": "case",
        "entity_id": case.case_id,
        "label": case.observed or case.case_id,
        "scope": case.scope,
        "status": case.status,
    }


def _needs_me_items(session: Session, actor: Actor) -> list[dict[str, Any]]:
    cases = list_cases(session)
    return [_case_summary(c) for c in cases_needing_actor(cases, session, actor)]


def _changed_items(session: Session, actor: Actor) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for case in list_cases(session):
        last_seen = get_last_seen(session, actor.id, "case", case.case_id)
        if last_seen is None:
            continue
        if changed_since_last_seen(case.updated_at, last_seen):
            changed.append(
                {**_case_summary(case), "changed_at": case.updated_at.isoformat()}
            )
    for document in list_last_seen_entity_ids(session, actor.id, "document"):
        disposition = get_document_disposition(session, document)
        if disposition is None or disposition.confirmed_at is None:
            continue
        last_seen = get_last_seen(session, actor.id, "document", document)
        if last_seen is not None and disposition.confirmed_at > last_seen:
            changed.append(
                {
                    "entity_type": "document",
                    "entity_id": document,
                    "label": document,
                    "changed_at": disposition.confirmed_at.isoformat(),
                }
            )
    return changed


def _deadline_items(packet: Packet, today: date) -> list[dict[str, Any]]:
    items = []
    for deadline in packet.firm.deadlines:
        try:
            due = date.fromisoformat(deadline.date)
        except ValueError:
            continue
        items.append(
            {
                "label": deadline.what,
                "date": deadline.date,
                "days_remaining": (due - today).days,
                "overdue": due < today,
            }
        )
    return sorted(items, key=lambda item: item["date"])


def notifications_report(
    session: Session, packet: Packet, actor: Actor, *, today: date | None = None
) -> dict[str, Any]:
    return {
        "needs_me": _needs_me_items(session, actor),
        "changed": _changed_items(session, actor),
        "deadlines": _deadline_items(packet, today or datetime.now().date()),
    }
