"""C4 document disposition (docs/CONTRACTS.md C4): rules propose
(`proofline.analysis.disposition.propose_disposition`), the preparer
confirms via `confirm_disposition`. Every document already has a
disposition row -- created lazily, defaulting to `pending` -- so this is
a plain compare-and-set like a case transition, not a log-only action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError, require
from proofline.actions.results import ActionResult
from proofline.db.models import DocumentDisposition
from proofline.db.repository import (
    apply_revision_cas,
    get_or_create_document_disposition,
    insert_event,
)
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission

_VALID_DISPOSITIONS = frozenset(
    {
        "used",
        "duplicate_of",
        "superseded_by",
        "reference",
        "identity_and_engagement",
        "agency_record",
        "excluded",
        "pending",
    }
)
_REASON_REQUIRED_FOR = frozenset({"excluded", "superseded_by", "duplicate_of"})


def confirm_disposition(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "confirm_disposition")
    document_id = entity_id
    if document_id is None:
        raise ActionValidationError("entity_id (the document_id) is required")
    disposition = require(payload, "disposition")
    if disposition not in _VALID_DISPOSITIONS:
        raise ActionValidationError(
            f"disposition must be one of {sorted(_VALID_DISPOSITIONS)}"
        )
    reason = payload.get("reason")
    if disposition in _REASON_REQUIRED_FOR and not (reason or "").strip():
        raise ActionValidationError(
            f"reason is required for disposition {disposition!r}"
        )
    if expected_revision is None:
        raise ActionValidationError("expected_revision is required")

    get_or_create_document_disposition(session, document_id)
    when = occurred_at or datetime.now(UTC)
    updated = apply_revision_cas(
        session,
        DocumentDisposition,
        document_id,
        expected_revision,
        {
            "disposition": disposition,
            "reason": reason,
            "confirmed_by": actor.id,
            "confirmed_at": when,
        },
    )
    event = insert_event(
        session,
        "document_disposition_confirmed",
        {"disposition": disposition, "reason": reason},
        actor_id=actor.id,
        entity_type="document_disposition",
        entity_id=document_id,
        revision=updated.revision,
        occurred_at=when,
    )
    return ActionResult(event=event, current_state=updated)
