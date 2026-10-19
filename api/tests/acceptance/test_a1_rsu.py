"""A1 (docs/ACCEPTANCE.md): the RSU basis correction, end to end.

The check finds three zero-basis RSU lots (N1, N3, N4) with a matching
employer cost-basis supplement (D11) and opens one case. Priya proposes a
revision, Daniel returns it for better evidence, Priya resubmits citing
D11 directly, Daniel approves (tax effect over 1,000 sends it to the
partner), Helen partner-approves and it resolves. D11's own
`adjusted_basis` fields (`ev-0066`/`ev-0068`/`ev-0070`) give the corrected
basis for each lot by matching acquisition date -- the same thing the
check itself already confirmed, read directly from the packet here rather
than re-deriving it, since this test proves the case *lifecycle*, not the
check's own matching logic (that's
`test_check_rsu_lot_zero_basis_supplement_available.py`'s job).
"""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.actions.cases import validate_resolution_fields
from proofline.actions.errors import ActionValidationError
from proofline.actions.service import perform
from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.checks.runner import run_all_checks
from proofline.db.models import Base
from proofline.db.repository import (
    list_adjustments,
    list_case_decisions,
    list_case_proposals,
    list_cases,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PRIYA = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
DANIEL = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
HELEN = Actor(id="st-03", name="Helen", role="partner", clearance=True)

_CHECK_ID = "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE"
# (claim, corrected gain) -- proceeds minus D11's adjusted_basis for the
# lot acquired on the matching date: N1 19240-19100=140, N3 18480-19100=
# -620, N4 15300-9420=5880.
_CORRECTED_GAINS = {
    "1099b_lot:Northlake Securities:N1": "140",
    "1099b_lot:Northlake Securities:N3": "-620",
    "1099b_lot:Northlake Securities:N4": "5880",
}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _adjustments_payload(claim_keys: list[str]) -> dict:
    return {
        "adjustments": [
            {
                "claim": claim_key,
                "old_value": "0",
                "new_value": _CORRECTED_GAINS[claim_key],
            }
            for claim_key in claim_keys
        ]
    }


def test_rsu_basis_correction_full_lifecycle(session: Session) -> None:
    packet = load_packet()

    # The check finds three lots and opens one case.
    run_result = run_all_checks(packet)
    rsu_finding = next(f for f in run_result.findings if f.check_id == _CHECK_ID)
    assert {str(c) for c in rsu_finding.claims} == set(_CORRECTED_GAINS)

    perform(session, DANIEL, "sync_cases", packet=packet)
    case = next(c for c in list_cases(session) if c.check_id == _CHECK_ID)
    assert case.status == "open"
    assert set(case.claims) == set(_CORRECTED_GAINS)

    # Priya picks it up and proposes revision 1, citing only the broker's
    # own 1099-B fields -- not yet the employer's cost-basis supplement.
    case = perform(
        session,
        PRIYA,
        "pick_up",
        entity_id=case.case_id,
        expected_revision=case.revision,
    ).current_state
    case = perform(
        session,
        PRIYA,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": _adjustments_payload(["1099b_lot:Northlake Securities:N1"]),
            "evidence_refs": ["ev-0493"],
        },
        packet=packet,
    ).current_state
    assert case.status == "in_review"

    # Daniel returns it: incomplete (only one of three lots) and not
    # citing the supplement that actually justifies the new basis.
    case = perform(
        session,
        DANIEL,
        "return",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "cite D11 directly, and cover all three lots"},
        packet=packet,
    ).current_state
    assert case.status == "investigating"

    # Priya resubmits revision 2, citing D11 (the stock-plan supplement)
    # and all three lots.
    case = perform(
        session,
        PRIYA,
        "submit_proposal",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": _adjustments_payload(sorted(_CORRECTED_GAINS)),
            "evidence_refs": ["D11"],
        },
        packet=packet,
    ).current_state
    assert case.status == "in_review"

    # Daniel approves revision 2; the effect is over 1,000, so it goes to
    # the partner rather than straight to resolved.
    case = perform(
        session,
        DANIEL,
        "approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={"note": "agree with the correction"},
        packet=packet,
    ).current_state
    assert case.status == "awaiting_partner"

    # Helen partner-approves; the case resolves and the adjustments land.
    case = perform(
        session,
        HELEN,
        "partner_approve",
        entity_id=case.case_id,
        expected_revision=case.revision,
        payload={},
        packet=packet,
    ).current_state
    assert case.status == "resolved"

    # Revision 1, both decisions and the original engine values are all
    # still readable.
    proposals = list_case_proposals(session, case.case_id)
    assert [p.revision_number for p in proposals] == [1, 2]
    assert proposals[0].evidence_refs == ["ev-0493"]

    decisions = list_case_decisions(session, case.case_id)
    assert [d.decision for d in decisions] == ["return", "approve", "partner_approve"]

    rv = packet.return_version("v3")
    assert rv.line("F8949.B.N1").value == 19240
    assert rv.line("F8949.B.N3").value == 18480
    assert rv.line("F8949.E.N4").value == 15300

    # Schedule D line 2 shows -480, labelled exact. The tax effect shows
    # about 15,536 federal, labelled estimate.
    adjustments = adjustments_by_claim(list_adjustments(session))
    assert len(adjustments) == 3
    sched_d = workpaper_value(packet, rv, "SchD.2", adjustments)
    assert sched_d.value == Decimal(-480)
    assert sched_d.label == "exact"

    assert case.tax_effect_kind == "estimate"
    assert round(case.tax_effect_federal) == Decimal(15536)


def test_adjust_number_resolution_validates_its_shape() -> None:
    # Exercised directly, since the lifecycle test above never submits a
    # malformed proposal -- A1's own narrative never hits this path.
    with pytest.raises(ActionValidationError):
        validate_resolution_fields("adjust_number", {"adjustments": []})
