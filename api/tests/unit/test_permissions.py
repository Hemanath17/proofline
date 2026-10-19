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
