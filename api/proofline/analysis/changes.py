"""Since you last looked (docs/UX.md): whether an entity changed after
the acting actor last opened it, and a one-line summary of what changed.
Both are computed from `last_seen` (plain UI-state table) compared against
the entity's own `updated_at` / latest relevant event -- never stored
themselves, so there's nothing to keep in sync.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from proofline.db.models import Case
from proofline.db.repository import list_case_proposals
from proofline.security.actors import Actor

_OPEN_STATUSES = {
    "open",
    "investigating",
    "waiting_on_client",
    "in_review",
    "awaiting_partner",
}


def cases_needing_actor(
    cases: list[Case], session: Session, actor: Actor
) -> list[Case]:
    """Role-aware "needs me" filter (docs/UX.md S1), shared by the queue
    (`routes/cases.py`) and the notifications feed (`analysis/
    notifications.py`) so the two screens never disagree about what counts
    as needing this actor's attention."""
    if actor.role == "preparer":
        return [
            c
            for c in cases
            if c.status == "open"
            or (c.status == "investigating" and c.assignee_id == actor.id)
        ]
    if actor.role in ("reviewer", "quality_reviewer"):
        result = []
        for c in cases:
            if c.status != "in_review":
                continue
            proposals = list_case_proposals(session, c.case_id)
            if proposals and proposals[-1].proposed_by == actor.id:
                continue
            result.append(c)
        return result
    if actor.role == "partner":
        return [c for c in cases if c.status == "awaiting_partner"]
    return [
        c for c in cases if c.status in _OPEN_STATUSES and c.assignee_id == actor.id
    ]


def changed_since_last_seen(
    entity_updated_at: datetime, last_seen_at: datetime | None
) -> bool:
    if last_seen_at is None:
        return False
    return entity_updated_at > last_seen_at


def case_change_summary(case, last_proposal, last_decision) -> str | None:
    """A one-line summary of the most recent thing that happened to a
    case, in the style of docs/UX.md's example ("revision 2 submitted by
    Priya; tax effect now 15,536 estimate"). `last_proposal` and
    `last_decision` are the most recent `CaseProposal`/`CaseDecision` rows,
    or None."""
    candidates: list[tuple[datetime, str]] = []
    if last_proposal is not None:
        summary = (
            f"revision {last_proposal.revision_number} submitted by "
            f"{last_proposal.proposed_by}"
        )
        candidates.append((last_proposal.proposed_at, summary))
    if last_decision is not None:
        candidates.append(
            (
                last_decision.decided_at,
                f"{last_decision.decision} by {last_decision.decided_by}",
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[-1][1]
