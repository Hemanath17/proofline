"""Since you last looked (docs/UX.md): whether an entity changed after
the acting actor last opened it, and a one-line summary of what changed.
Both are computed from `last_seen` (plain UI-state table) compared against
the entity's own `updated_at` / latest relevant event -- never stored
themselves, so there's nothing to keep in sync.
"""

from __future__ import annotations

from datetime import datetime


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
