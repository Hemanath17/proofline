"""A2 (docs/ACCEPTANCE.md): a corrected brokerage statement, end to end.

Investments, Business and Tax computation are all signed at v1 (the
return as it stood on D30). D31 then arrives, correcting D30: the
provenance resolver finds the 24 lines that depended on D30, of which
three claims changed (M6, M9, M14) and 21 are identical in every field
they relied on. Investments shows "signed, change pending" and needs a
carry-over confirmation before it can be signed again; Business is
unaffected and stays signed; Tax computation shows a pending change (its
own line values shifted) with no document to carry over. The reviewer
confirms the carry-over once and signs investments again: v2 exists,
and v1 is still there.
"""

from collections.abc import Iterator

import pytest
from proofline.actions.errors import ActionConflict
from proofline.actions.service import perform
from proofline.analysis.signoff import (
    compare_document_dependents,
    document_replacements,
)
from proofline.db.models import Base
from proofline.db.repository import list_sign_offs
from proofline.packet import load_packet
from proofline.provenance.claim_identity import lot_1099b
from proofline.security.actors import Actor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

DANIEL = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
HELEN = Actor(id="st-03", name="Helen", role="partner", clearance=True)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _sign_off(session: Session, actor: Actor, scope: str, version: str) -> None:
    packet = load_packet()
    perform(
        session,
        actor,
        "sign_off",
        payload={"scope": scope, "version": version},
        packet=packet,
    )


def test_corrected_1099_full_lifecycle(session: Session) -> None:
    packet = load_packet()
    v1 = packet.return_version("v1")
    v2 = packet.return_version("v2")

    # Investments is signed at v1 using D30; Business and Tax computation
    # are signed at v1 too, as part of the same initial close-out.
    _sign_off(session, DANIEL, "investments", "v1")
    _sign_off(session, DANIEL, "business", "v1")
    _sign_off(session, HELEN, "tax_computation", "v1")

    # D31 arrives. The provenance resolver finds the 24 lines that
    # depended on D30: three claims changed, 21 are identical in every
    # field they relied on.
    assert document_replacements(packet, v2) == {"D30": "D31"}
    comparison = compare_document_dependents(packet, v1, v2, "D30")
    assert len(comparison.unchanged) + len(comparison.changed) == 24
    assert len(comparison.changed) == 3
    assert len(comparison.unchanged) == 21
    changed_keys = {c.comparison_key for c in comparison.changed}
    assert changed_keys == {
        "1099b_lot:Meridian Brokerage:M6",
        "1099b_lot:Meridian Brokerage:M9",
        "1099b_lot:Meridian Brokerage:M14",
    }

    # M14 keeps its identity even though its line key moves from box A to
    # box D.
    m14 = next(
        c
        for c in comparison.changed
        if c.comparison_key == str(lot_1099b("Meridian Brokerage", "M14"))
    )
    assert m14.old_line_key == "F8949.A.M14"
    assert m14.new_line_key == "F8949.D.M14"
    assert m14.old_value == m14.new_value == 855.0

    # Investments shows "signed, change pending": re-signing at v2
    # without confirming the carry-over first is refused.
    with pytest.raises(ActionConflict, match="confirm the carry-over"):
        _sign_off(session, DANIEL, "investments", "v2")

    # Business stays signed: nothing about its own sign-off is disturbed,
    # and it isn't asked to confirm any carry-over for a document it
    # never relied on.
    perform(
        session,
        DANIEL,
        "sign_off",
        payload={"scope": "business", "version": "v2"},
        packet=packet,
    )
    business_sign_offs = list_sign_offs(session, "business")
    assert [s.version for s in business_sign_offs] == [1, 2]

    # Tax computation shows a pending change too (its own line values
    # moved), with nothing to carry over -- re-signing it needs no
    # confirm_carryover step.
    perform(
        session,
        HELEN,
        "sign_off",
        payload={"scope": "tax_computation", "version": "v2"},
        packet=packet,
    )

    # The reviewer confirms the carry-over once and signs investments
    # again: v2 exists, and v1 is still there.
    perform(
        session,
        DANIEL,
        "confirm_carryover",
        payload={
            "scope": "investments",
            "old_document_id": "D30",
            "new_document_id": "D31",
        },
        packet=packet,
    )
    result = perform(
        session,
        DANIEL,
        "sign_off",
        payload={"scope": "investments", "version": "v2"},
        packet=packet,
    )
    assert result.current_state.version == 2
    investments_sign_offs = list_sign_offs(session, "investments")
    assert [s.version for s in investments_sign_offs] == [1, 2]
    assert investments_sign_offs[0].engine_version == "v1"
    assert investments_sign_offs[1].engine_version == "v2"
