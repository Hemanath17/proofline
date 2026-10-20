"""B19: a structured judgment/election record -- separate from (but
linkable to) a case's own `record_judgment` resolution type (CONTRACTS.md
C1). Log-only, like every other append-only fact in Step 9 (the authority
relied on and who approved it are never edited, only superseded by a new
record), read back by replaying `judgment_election_recorded` events.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from proofline.db.repository import list_events_by_type


@dataclass(frozen=True)
class Judgment:
    id: str
    recorded_by: str | None
    authority: str
    approved_by: str
    reasoning: str
    claim_key: str | None
    is_election: bool
    what_if_id: str | None
    case_id: str | None
    occurred_at: str | None


def list_judgments(session: Session) -> list[Judgment]:
    judgments = []
    for event in list_events_by_type(session, "judgment_election_recorded"):
        payload = event.payload
        judgments.append(
            Judgment(
                id=event.entity_id,
                recorded_by=event.actor_id,
                authority=payload.get("authority"),
                approved_by=payload.get("approved_by"),
                reasoning=payload.get("reasoning"),
                claim_key=payload.get("claim_key"),
                is_election=bool(payload.get("is_election", False)),
                what_if_id=payload.get("what_if_id"),
                case_id=payload.get("case_id"),
                occurred_at=event.occurred_at.isoformat()
                if event.occurred_at
                else None,
            )
        )
    return judgments
