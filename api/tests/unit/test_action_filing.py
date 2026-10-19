"""`authorize_filing` and `submit_filing`, through `perform()`
(CONTRACTS.md C5, acceptance test A3)."""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionConflict, ActionValidationError
from proofline.actions.service import perform
from proofline.db.models import Base
from proofline.db.repository import list_filed_records
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.permissions import PermissionDenied
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

REVIEWER = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
CLIENT = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)
AI_ASSISTANT = Actor(
    id="ai-assistant", name="AI assistant", role="ai_assistant", clearance=False
)

_PINS = {"taxpayer": "41207", "spouse": "88310"}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _authorize(session: Session) -> str:
    packet = load_packet()
    result = perform(
        session, CLIENT, "authorize_filing", payload={"pins": _PINS}, packet=packet
    )
    return result.current_state["package_reference"]


def test_authorize_filing_records_the_package_and_fingerprints(
    session: Session,
) -> None:
    packet = load_packet()
    result = perform(
        session, CLIENT, "authorize_filing", payload={"pins": _PINS}, packet=packet
    )
    current = result.current_state
    assert current["simulated"] is True
    assert current["package_reference"]
    assert current["amounts_fingerprint"]
    assert current["identity_fingerprint"]


def test_authorize_filing_denied_for_the_ai_assistant(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(PermissionDenied):
        perform(
            session,
            AI_ASSISTANT,
            "authorize_filing",
            payload={"pins": _PINS},
            packet=packet,
        )


def test_authorize_filing_needs_the_packet(session: Session) -> None:
    with pytest.raises(ActionValidationError, match="needs the packet"):
        perform(session, CLIENT, "authorize_filing", payload={"pins": _PINS})


def test_authorize_filing_requires_pins_at_all(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="pins"):
        perform(session, CLIENT, "authorize_filing", payload={}, packet=packet)


def test_authorize_filing_requires_pins_for_every_signing_role(
    session: Session,
) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="pins must cover exactly"):
        perform(
            session,
            CLIENT,
            "authorize_filing",
            payload={"pins": {"taxpayer": "41207"}},
            packet=packet,
        )


def test_authorize_filing_rejects_a_blank_pin(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="pin for"):
        perform(
            session,
            CLIENT,
            "authorize_filing",
            payload={"pins": {"taxpayer": "41207", "spouse": "   "}},
            packet=packet,
        )


def test_submit_filing_requires_a_prior_authorization(session: Session) -> None:
    packet = load_packet()
    with pytest.raises(ActionValidationError, match="never been authorized"):
        perform(
            session,
            REVIEWER,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": "sha-does-not-exist",
                "status": "rejected",
            },
            packet=packet,
        )


def test_submit_filing_refuses_a_package_reference_that_is_not_the_latest_authorization(
    session: Session,
) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    with pytest.raises(ActionConflict, match="authorize_filing again"):
        perform(
            session,
            REVIEWER,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": "a-stale-reference",
                "status": "accepted",
            },
            packet=packet,
        )
    assert package_reference  # the real one is unaffected


def test_submit_filing_rejected_writes_no_filed_record(session: Session) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    result = perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": package_reference,
            "status": "rejected",
            "codes": [{"code": "R0000-504-02", "message": "mismatch"}],
        },
        packet=packet,
    )
    assert result.current_state["filed_record_id"] is None
    assert list_filed_records(session) == []


def test_submit_filing_accepted_writes_exactly_one_filed_record(
    session: Session,
) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    result = perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": package_reference,
            "status": "accepted",
        },
        packet=packet,
    )
    assert result.current_state["filed_record_id"] is not None
    records = list_filed_records(session)
    assert len(records) == 1
    assert records[0].jurisdiction == "federal"
    assert records[0].package_reference == package_reference


def test_submit_filing_accepted_twice_for_the_same_jurisdiction_is_refused(
    session: Session,
) -> None:
    """I6: a filed record is written once. Amendments aren't built yet
    (Step 9+), so once a jurisdiction has a filed record, accepting it
    again -- even for the same package -- is refused rather than
    silently writing a second row."""
    packet = load_packet()
    package_reference = _authorize(session)
    perform(
        session,
        REVIEWER,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": package_reference,
            "status": "accepted",
        },
        packet=packet,
    )
    with pytest.raises(ActionConflict, match="already has a filed record"):
        perform(
            session,
            REVIEWER,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": package_reference,
                "status": "accepted",
            },
            packet=packet,
        )
    assert len(list_filed_records(session, jurisdiction="federal")) == 1


def test_submit_filing_denied_for_the_client(session: Session) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    with pytest.raises(PermissionDenied):
        perform(
            session,
            CLIENT,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": package_reference,
                "status": "accepted",
            },
            packet=packet,
        )


def test_submit_filing_rejects_an_unknown_jurisdiction(session: Session) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    with pytest.raises(ActionValidationError, match="jurisdiction must be one of"):
        perform(
            session,
            REVIEWER,
            "submit_filing",
            payload={
                "jurisdiction": "texas",
                "package_reference": package_reference,
                "status": "accepted",
            },
            packet=packet,
        )


def test_submit_filing_rejects_an_unknown_status(session: Session) -> None:
    packet = load_packet()
    package_reference = _authorize(session)
    with pytest.raises(ActionValidationError, match="status must be one of"):
        perform(
            session,
            REVIEWER,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": package_reference,
                "status": "pending",
            },
            packet=packet,
        )
