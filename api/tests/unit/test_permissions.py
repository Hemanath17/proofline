import pytest
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied, check_permission

PREPARER = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
PARTNER = Actor(id="st-03", name="Helen", role="partner", clearance=True)
MARCUS = Actor(id="st-04", name="Marcus", role="preparer", clearance=False)
FIRM_ADMIN = Actor(id="st-05", name="Jo", role="firm_administrator", clearance=True)
QUALITY_REVIEWER = Actor(
    id="st-06", name="Sam", role="quality_reviewer", clearance=True
)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)
AI_ASSISTANT = Actor(
    id="ai-assistant", name="AI assistant", role="ai_assistant", clearance=False
)

ALL_ACTORS = [
    PREPARER,
    REVIEWER,
    PARTNER,
    MARCUS,
    FIRM_ADMIN,
    QUALITY_REVIEWER,
    CLIENT,
    AI_ASSISTANT,
]


@pytest.mark.parametrize("actor", [REVIEWER, PARTNER, QUALITY_REVIEWER])
def test_add_review_note_allowed_for_reviewer_partner_quality_reviewer(
    actor: Actor,
) -> None:
    check_permission(actor, "add_review_note")  # must not raise


@pytest.mark.parametrize("actor", [PREPARER, MARCUS, FIRM_ADMIN, CLIENT, AI_ASSISTANT])
def test_add_review_note_denied_for_everyone_else(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "add_review_note")
    assert exc_info.value.rule == (
        "only a reviewer, partner or quality reviewer may raise a review note"
    )


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_respond_review_note_allowed_for_any_staff(actor: Actor) -> None:
    check_permission(actor, "respond_review_note")  # must not raise


@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_respond_review_note_denied_for_client_and_ai_assistant(actor: Actor) -> None:
    with pytest.raises(PermissionDenied):
        check_permission(actor, "respond_review_note")


def test_resolve_review_note_allowed_for_its_own_author() -> None:
    check_permission(REVIEWER, "resolve_review_note", opened_by=REVIEWER.id)


def test_resolve_review_note_allowed_for_the_partner_even_if_not_the_author() -> None:
    check_permission(PARTNER, "resolve_review_note", opened_by=REVIEWER.id)


def test_resolve_review_note_denied_for_a_different_staff_member() -> None:
    """This is the acceptance test I3 example named in CLAUDE.md: a 403
    that names the rule, 'own work'."""
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(PREPARER, "resolve_review_note", opened_by=REVIEWER.id)

    assert exc_info.value.rule == (
        "only the reviewer who raised a note, or the partner, may clear it"
    )


def test_resolve_review_note_denied_for_another_reviewer_who_did_not_open_it() -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(QUALITY_REVIEWER, "resolve_review_note", opened_by=REVIEWER.id)

    assert exc_info.value.rule == (
        "only the reviewer who raised a note, or the partner, may clear it"
    )


@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_resolve_review_note_denied_for_client_and_ai_assistant(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "resolve_review_note", opened_by=REVIEWER.id)
    assert exc_info.value.rule == (
        "staff only: clients and the AI assistant may not resolve a review note"
    )


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_reveal_sensitive_value_allowed_when_cleared(actor: Actor) -> None:
    check_permission(actor, "reveal_sensitive_value")


@pytest.mark.parametrize("actor", [MARCUS, CLIENT, AI_ASSISTANT])
def test_reveal_sensitive_value_denied_without_clearance(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "reveal_sensitive_value")
    assert exc_info.value.rule == "no clearance"


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_record_check_run_allowed_for_any_staff(actor: Actor) -> None:
    check_permission(actor, "record_check_run")


@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_record_check_run_denied_for_client_and_ai_assistant(actor: Actor) -> None:
    with pytest.raises(PermissionDenied):
        check_permission(actor, "record_check_run")


def test_unknown_action_raises_value_error() -> None:
    with pytest.raises(ValueError):
        check_permission(PARTNER, "no_such_action")  # type: ignore[arg-type]


@pytest.mark.parametrize("actor", [REVIEWER, PARTNER, QUALITY_REVIEWER])
def test_sign_off_an_area_allowed_for_reviewer_partner_quality_reviewer(
    actor: Actor,
) -> None:
    check_permission(actor, "sign_off", scope="investments")


@pytest.mark.parametrize("actor", [PREPARER, MARCUS, FIRM_ADMIN, CLIENT, AI_ASSISTANT])
def test_sign_off_an_area_denied_for_everyone_else(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "sign_off", scope="investments")
    assert exc_info.value.rule == (
        "only a reviewer, partner or quality reviewer may sign an area"
    )


def test_sign_off_tax_computation_allowed_only_for_partner() -> None:
    check_permission(PARTNER, "sign_off", scope="tax_computation")


@pytest.mark.parametrize("actor", [REVIEWER, QUALITY_REVIEWER, PREPARER])
def test_sign_off_tax_computation_denied_for_a_reviewer(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "sign_off", scope="tax_computation")
    assert exc_info.value.rule == "only the partner may sign tax computation"


@pytest.mark.parametrize("actor", [REVIEWER, PARTNER, QUALITY_REVIEWER])
def test_confirm_carryover_allowed_for_reviewer_partner_quality_reviewer(
    actor: Actor,
) -> None:
    check_permission(actor, "confirm_carryover")


@pytest.mark.parametrize("actor", [PREPARER, MARCUS, FIRM_ADMIN, CLIENT, AI_ASSISTANT])
def test_confirm_carryover_denied_for_everyone_else(actor: Actor) -> None:
    with pytest.raises(PermissionDenied):
        check_permission(actor, "confirm_carryover")


def test_confirm_disposition_allowed_only_for_preparer() -> None:
    check_permission(PREPARER, "confirm_disposition")


def test_confirm_disposition_allowed_for_a_preparer_without_clearance() -> None:
    # Confirming a disposition is a role rule, not a clearance rule --
    # Marcus (preparer, no clearance) may still confirm one; redaction on
    # the response is a separate concern (W2), handled by redact_for_actor.
    check_permission(MARCUS, "confirm_disposition")


@pytest.mark.parametrize(
    "actor", [REVIEWER, PARTNER, QUALITY_REVIEWER, FIRM_ADMIN, CLIENT]
)
def test_confirm_disposition_denied_for_everyone_else(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "confirm_disposition")
    assert exc_info.value.rule == "only the preparer may confirm a document disposition"


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, QUALITY_REVIEWER, MARCUS]
)
@pytest.mark.parametrize("action", ["bulk_verify", "undo_bulk_verify"])
def test_bulk_verify_allowed_for_any_detail_reviewer(actor: Actor, action: str) -> None:
    check_permission(actor, action)  # type: ignore[arg-type]


@pytest.mark.parametrize("actor", [FIRM_ADMIN, CLIENT, AI_ASSISTANT])
@pytest.mark.parametrize("action", ["bulk_verify", "undo_bulk_verify"])
def test_bulk_verify_denied_for_everyone_else(actor: Actor, action: str) -> None:
    with pytest.raises(PermissionDenied):
        check_permission(actor, action)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_confirm_readiness_item_allowed_for_any_staff(actor: Actor) -> None:
    check_permission(actor, "confirm_readiness_item")


@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_confirm_readiness_item_denied_for_client_and_ai_assistant(
    actor: Actor,
) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "confirm_readiness_item")
    assert exc_info.value.rule == "staff only"


@pytest.mark.parametrize(
    "actor",
    [CLIENT, PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER],
)
def test_authorize_filing_allowed_for_client_or_staff(actor: Actor) -> None:
    check_permission(actor, "authorize_filing")


def test_authorize_filing_denied_for_ai_assistant() -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(AI_ASSISTANT, "authorize_filing")
    assert exc_info.value.rule == (
        "only the client, or staff recording on the client's behalf, may "
        "authorize filing"
    )


@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_submit_filing_allowed_for_any_staff(actor: Actor) -> None:
    check_permission(actor, "submit_filing")


@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_submit_filing_denied_for_client_and_ai_assistant(actor: Actor) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, "submit_filing")
    assert exc_info.value.rule == "staff only"


@pytest.mark.parametrize(
    "action",
    ["log_time", "record_judgment_election", "confirm_outside_filing"],
)
@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_step9_log_only_actions_allowed_for_any_staff(
    actor: Actor, action: str
) -> None:
    check_permission(actor, action)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "action",
    ["log_time", "record_judgment_election", "confirm_outside_filing"],
)
@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_step9_log_only_actions_denied_for_client_and_ai_assistant(
    actor: Actor, action: str
) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, action)  # type: ignore[arg-type]
    assert exc_info.value.rule == "staff only"


# Step 10, Part 1 point 7: "the AI can never..." is supposed to come from
# the role and the action service, never the prompt (CLAUDE.md) -- this
# proves it explicitly, for `ai_assistant`, against EVERY write action in
# `permissions.py`'s `ActionName`, not just the ones a prior step happened
# to test. Every one of these is already denied by the existing role
# checks above (no gap found -- see docs/DECISIONS.md); `sign_off` and
# `resolve_review_note` need extra kwargs and are already covered for
# `ai_assistant` further up this file, so they're not repeated here.
_EVERY_OTHER_WRITE_ACTION_AND_ITS_RULE = [
    ("open_case_by_hand", "staff only: a case opened by hand needs a staff member"),
    ("sync_cases", "staff only"),
    ("pick_up", "preparer only"),
    ("ask_client", "preparer only"),
    (
        "client_answered",
        "only the client or the system may record an answer",
    ),
    ("submit_proposal", "preparer only"),
    ("return", "only a reviewer, partner or quality reviewer may decide on a proposal"),
    (
        "approve",
        "only a reviewer, partner or quality reviewer may decide on a proposal",
    ),
    ("partner_approve", "partner only"),
    ("partner_return", "partner only"),
    ("reopen", "only the system or a reviewer may reopen a case"),
    ("reassign", "only a preparer, reviewer or admin may reassign a case"),
    ("confirm_disposition", "only the preparer may confirm a document disposition"),
]


@pytest.mark.parametrize("action, rule", _EVERY_OTHER_WRITE_ACTION_AND_ITS_RULE)
def test_ai_assistant_denied_every_other_write_action(action: str, rule: str) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(AI_ASSISTANT, action)  # type: ignore[arg-type]
    assert exc_info.value.rule == rule


@pytest.mark.parametrize("action", ["trigger_investigation", "review_ai_suggestion"])
@pytest.mark.parametrize(
    "actor", [PREPARER, REVIEWER, PARTNER, MARCUS, FIRM_ADMIN, QUALITY_REVIEWER]
)
def test_investigator_actions_allowed_for_any_staff(actor: Actor, action: str) -> None:
    check_permission(actor, action)  # type: ignore[arg-type]


@pytest.mark.parametrize("action", ["trigger_investigation", "review_ai_suggestion"])
@pytest.mark.parametrize("actor", [CLIENT, AI_ASSISTANT])
def test_investigator_actions_denied_for_client_and_ai_assistant(
    actor: Actor, action: str
) -> None:
    with pytest.raises(PermissionDenied) as exc_info:
        check_permission(actor, action)  # type: ignore[arg-type]
    assert exc_info.value.rule == "staff only"
