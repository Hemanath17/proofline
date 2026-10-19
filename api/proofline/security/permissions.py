"""One place for every permission rule, so every refusal is a 403 that
names the rule (acceptance test I3), never a bare 403 with no reason.
Enforced here, in the API -- never only in the UI (CONTRACTS.md).
"""

from __future__ import annotations

from typing import Literal

from proofline.security.actors import Actor

ActionName = Literal[
    "add_review_note",
    "respond_review_note",
    "resolve_review_note",
    "reveal_sensitive_value",
    "record_check_run",
]


class PermissionDenied(Exception):
    """`rule` is exactly what the 403's `detail` should say."""

    def __init__(self, rule: str):
        self.rule = rule
        super().__init__(rule)


def check_permission(
    actor: Actor, action: ActionName, *, opened_by: str | None = None
) -> None:
    """Raises `PermissionDenied` if `actor` may not take `action`.
    `opened_by` is the review note's current author -- only needed (and
    only checked) for `resolve_review_note`.
    """
    if action == "add_review_note":
        if actor.role not in {"reviewer", "partner", "quality_reviewer"}:
            raise PermissionDenied(
                "only a reviewer, partner or quality reviewer may raise a review note"
            )
    elif action == "respond_review_note":
        if not actor.is_staff:
            raise PermissionDenied(
                "staff only: clients and the AI assistant may not respond to a "
                "review note"
            )
    elif action == "resolve_review_note":
        # Checked in two steps so a non-staff actor gets a rule about not
        # being staff at all, rather than a confusing "you're not the
        # author" that implies they could ever have been.
        if not actor.is_staff:
            raise PermissionDenied(
                "staff only: clients and the AI assistant may not resolve a review note"
            )
        if actor.id != opened_by and actor.role != "partner":
            raise PermissionDenied(
                "only the reviewer who raised a note, or the partner, may clear it"
            )
    elif action == "reveal_sensitive_value":
        if not actor.clearance:
            raise PermissionDenied("no clearance")
    elif action == "record_check_run":
        if not actor.is_staff:
            raise PermissionDenied("staff only")
    else:
        raise ValueError(f"unknown action {action!r}")
