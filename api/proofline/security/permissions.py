"""One place for every permission rule, so every refusal is a 403 that
names the rule (acceptance test I3), never a bare 403 with no reason.
Enforced here, in the API -- never only in the UI (CONTRACTS.md).
"""

from __future__ import annotations

from typing import Literal

from proofline.security.actors import STAFF_ROLES, Actor

ActionName = Literal[
    "add_review_note",
    "respond_review_note",
    "resolve_review_note",
    "reveal_sensitive_value",
    "record_check_run",
    # Step 5: C1 case transitions
    "open_case_by_hand",
    "sync_cases",
    "pick_up",
    "ask_client",
    "client_answered",
    "submit_proposal",
    "return",
    "approve",
    "partner_approve",
    "partner_return",
    "reopen",
    "reassign",
    # Step 7: C2 sign-off, C4 disposition, bulk verify
    "sign_off",
    "confirm_carryover",
    "confirm_disposition",
    "bulk_verify",
    "undo_bulk_verify",
    # Step 8: C5 readiness attestation, package authorization, submission
    "confirm_readiness_item",
    "authorize_filing",
    "submit_filing",
    # Step 9: time against budget, judgments/elections, outside filings
    "log_time",
    "record_judgment_election",
    "confirm_outside_filing",
    # Step 10: the Evidence Investigator -- staff only, same as every other
    # write here; the AI never triggers an investigation of itself, and
    # never reviews its own suggestion (CLAUDE.md: "the AI... can read and
    # propose" -- triggering and reviewing are both staff actions)
    "trigger_investigation",
    "review_ai_suggestion",
]

_REVIEWER_ROLES = {"reviewer", "partner", "quality_reviewer"}


class PermissionDenied(Exception):
    """`rule` is exactly what the 403's `detail` should say."""

    def __init__(self, rule: str):
        self.rule = rule
        super().__init__(rule)


_DETAIL_REVIEW_ROLES = {"preparer", "reviewer", "partner", "quality_reviewer"}


def check_permission(
    actor: Actor,
    action: ActionName,
    *,
    opened_by: str | None = None,
    scope: str | None = None,
) -> None:
    """Raises `PermissionDenied` if `actor` may not take `action`.
    `opened_by` is the review note's current author -- only needed (and
    only checked) for `resolve_review_note`. `scope` is the C2 area being
    signed -- only needed (and only checked) for `sign_off`, since Tax
    computation needs the partner while every other scope needs only a
    reviewer (CONTRACTS.md C2: "Reviewers sign areas, and the partner
    signs Tax computation and the final return").
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
    elif action == "open_case_by_hand":
        if not actor.is_staff:
            raise PermissionDenied(
                "staff only: a case opened by hand needs a staff member"
            )
    elif action == "sync_cases":
        if not actor.is_staff:
            raise PermissionDenied("staff only")
    elif action in ("pick_up", "ask_client", "submit_proposal"):
        if actor.role != "preparer":
            raise PermissionDenied("preparer only")
    elif action == "client_answered":
        if actor.role not in {"client", "system"}:
            raise PermissionDenied("only the client or the system may record an answer")
    elif action in ("return", "approve"):
        if actor.role not in _REVIEWER_ROLES:
            raise PermissionDenied(
                "only a reviewer, partner or quality reviewer may decide on a proposal"
            )
    elif action in ("partner_approve", "partner_return"):
        if actor.role != "partner":
            raise PermissionDenied("partner only")
    elif action == "reopen":
        if actor.role not in {"system", *_REVIEWER_ROLES}:
            raise PermissionDenied("only the system or a reviewer may reopen a case")
    elif action == "reassign":
        if actor.role not in {"preparer", "reviewer", "firm_administrator"}:
            raise PermissionDenied(
                "only a preparer, reviewer or admin may reassign a case"
            )
    elif action == "sign_off":
        if scope == "tax_computation":
            if actor.role != "partner":
                raise PermissionDenied("only the partner may sign tax computation")
        elif actor.role not in _REVIEWER_ROLES:
            raise PermissionDenied(
                "only a reviewer, partner or quality reviewer may sign an area"
            )
    elif action == "confirm_carryover":
        if actor.role not in _REVIEWER_ROLES:
            raise PermissionDenied(
                "only a reviewer, partner or quality reviewer may confirm a carry-over"
            )
    elif action == "confirm_disposition":
        if actor.role != "preparer":
            raise PermissionDenied(
                "only the preparer may confirm a document disposition"
            )
    elif action in ("bulk_verify", "undo_bulk_verify"):
        if actor.role not in _DETAIL_REVIEW_ROLES:
            raise PermissionDenied(
                "only a preparer, reviewer, partner or quality reviewer may verify detail"
            )
    elif action == "confirm_readiness_item":
        if not actor.is_staff:
            raise PermissionDenied("staff only")
    elif action == "authorize_filing":
        if actor.role not in {"client", *STAFF_ROLES}:
            raise PermissionDenied(
                "only the client, or staff recording on the client's behalf, may "
                "authorize filing"
            )
    elif action in (
        "submit_filing",
        "log_time",
        "record_judgment_election",
        "confirm_outside_filing",
        "trigger_investigation",
        "review_ai_suggestion",
    ):
        if not actor.is_staff:
            raise PermissionDenied("staff only")
    else:
        raise ValueError(f"unknown action {action!r}")
