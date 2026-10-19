"""A3 (docs/ACCEPTANCE.md): the e-file rejection and the 2028 examination,
end to end against the real packet.

Package F1 is authorized and submitted, then rejected with the packet's
own R0000-504-02 (Theo's SSN not matching the e-file database, E1). F1 is
kept -- readable from the event log -- and never counts as filed. The
SSN is corrected from D71 (the same case-resolution pipeline every other
case uses). Package F2 has the same amounts fingerprint and a new
identity fingerprint, since nothing about a line's own value changed.
F2 is accepted for both jurisdictions, and the filed record is written
once per jurisdiction. Later, the Schedule C gross-receipts double count
(E3) is resolved while preparing the response to the 2028 Letter 566,
and the pack's reconciliation reads the now-adjusted workpaper value --
151,300 -- not a fresh 142,000 + 12,400.
"""

from collections.abc import Iterator
from decimal import Decimal

import pytest
from proofline.actions.errors import ActionConflict
from proofline.actions.service import perform
from proofline.analysis.calculation import adjustments_by_claim
from proofline.analysis.filing import letter_566_pack
from proofline.db.models import Base
from proofline.db.repository import (
    list_adjustments,
    list_cases,
    list_events_for_entity,
    list_filed_records,
)
from proofline.packet import load_packet
from proofline.security.actors import Actor
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PRIYA = Actor(id="st-01", name="Priya", role="preparer", clearance=True)
DANIEL = Actor(id="st-02", name="Daniel", role="reviewer", clearance=True)
HELEN = Actor(id="st-03", name="Helen", role="partner", clearance=True)
NGOZI = Actor(id="cu-01", name="Ngozi", role="client", clearance=False)

_PINS = {"taxpayer": "41207", "spouse": "88310"}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _resolve_case(
    session: Session,
    case_id: str,
    revision: int,
    claim: str,
    old_value,
    new_value,
    evidence_refs,
) -> None:
    perform(
        session,
        PRIYA,
        "pick_up",
        entity_id=case_id,
        expected_revision=revision,
        packet=load_packet(),
    )
    case = next(c for c in list_cases(session) if c.case_id == case_id)
    perform(
        session,
        PRIYA,
        "submit_proposal",
        entity_id=case_id,
        expected_revision=case.revision,
        payload={
            "resolution_type": "adjust_number",
            "fields": {
                "adjustments": [
                    {
                        "claim": claim,
                        "old_value": str(old_value),
                        "new_value": str(new_value),
                    }
                ]
            },
            "evidence_refs": evidence_refs,
        },
        packet=load_packet(),
    )


def test_efile_rejection_correction_and_2028_examination(session: Session) -> None:
    packet = load_packet()

    # Priya syncs the queue; the SSN mismatch (E1) and the gross-receipts
    # double-count (E3) are both findable from the real packet.
    perform(session, DANIEL, "sync_cases", packet=packet)
    cases = list_cases(session)
    e1_case = next(c for c in cases if c.check_id == "DEPENDENT_SSN_INDEPENDENT_SOURCE")
    e3_case = next(
        c for c in cases if c.check_id == "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED"
    )
    assert e3_case.tax_effect_federal > 1000  # needs the partner, below

    # Package F1 is authorized (the Form 8879/FTB 8879 signature, tl-20's
    # own PINs) and submitted -- then rejected with the packet's own
    # R0000-504-02.
    auth1 = perform(
        session, NGOZI, "authorize_filing", payload={"pins": _PINS}, packet=packet
    )
    f1_reference = auth1.current_state["package_reference"]
    f1_identity_fp = auth1.current_state["identity_fingerprint"]
    f1_amounts_fp = auth1.current_state["amounts_fingerprint"]

    rejection = packet.tax_agency_records.efile[0]
    assert rejection["jurisdiction"] == "federal"
    assert rejection["status"] == "rejected"
    rejection_code = rejection["errors"][0]["code"]
    assert rejection_code == "R0000-504-02"

    submit_f1 = perform(
        session,
        DANIEL,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": f1_reference,
            "status": "rejected",
            "codes": rejection["errors"],
            "submission_id": rejection.get("submission_id"),
        },
        packet=packet,
    )
    assert submit_f1.current_state["filed_record_id"] is None

    california_hold = packet.tax_agency_records.efile[1]
    assert california_hold["jurisdiction"] == "california"
    perform(
        session,
        DANIEL,
        "submit_filing",
        payload={
            "jurisdiction": "california",
            "package_reference": f1_reference,
            "status": "not_transmitted",
            "codes": california_hold["errors"],
        },
        packet=packet,
    )

    # F1 is kept, never filed.
    assert list_filed_records(session) == []
    federal_history = [
        e.payload["status"]
        for e in list_events_for_entity(session, "filing_submission", "federal")
    ]
    assert federal_history == ["rejected"]

    # The SSN is corrected from D71 -- same case-resolution pipeline as
    # every other finding, through to an approved adjustment.
    theo = next(p for p in packet.household.people if p.id == "theo")
    corrected_ssn = packet.extracted_value("ev-1080").value
    _resolve_case(
        session,
        e1_case.case_id,
        e1_case.revision,
        claim=f"household:{theo.id}:ssn",
        old_value=theo.ssn,
        new_value=corrected_ssn,
        evidence_refs=["D71", "ev-1080"],
    )
    e1_case = next(c for c in list_cases(session) if c.case_id == e1_case.case_id)
    approve_e1 = perform(
        session,
        DANIEL,
        "approve",
        entity_id=e1_case.case_id,
        expected_revision=e1_case.revision,
        payload={},
        packet=packet,
    )
    assert (
        approve_e1.current_state.status == "resolved"
    )  # no partner needed: no tax effect

    # Package F2 has the same amounts fingerprint and a new identity
    # fingerprint -- no line's value changed, only Theo's SSN.
    auth2 = perform(
        session, NGOZI, "authorize_filing", payload={"pins": _PINS}, packet=packet
    )
    f2_reference = auth2.current_state["package_reference"]
    assert f2_reference != f1_reference
    assert auth2.current_state["amounts_fingerprint"] == f1_amounts_fp
    assert auth2.current_state["identity_fingerprint"] != f1_identity_fp

    # The old (F1) package reference can no longer be submitted.
    with pytest.raises(ActionConflict):
        perform(
            session,
            DANIEL,
            "submit_filing",
            payload={
                "jurisdiction": "federal",
                "package_reference": f1_reference,
                "status": "accepted",
            },
            packet=packet,
        )

    # F2 is accepted for both jurisdictions, and the filed record is
    # written once per jurisdiction.
    submit_f2_federal = perform(
        session,
        DANIEL,
        "submit_filing",
        payload={
            "jurisdiction": "federal",
            "package_reference": f2_reference,
            "status": "accepted",
        },
        packet=packet,
    )
    submit_f2_california = perform(
        session,
        DANIEL,
        "submit_filing",
        payload={
            "jurisdiction": "california",
            "package_reference": f2_reference,
            "status": "accepted",
        },
        packet=packet,
    )
    assert submit_f2_federal.current_state["filed_record_id"] is not None
    assert submit_f2_california.current_state["filed_record_id"] is not None

    filed_records = list_filed_records(session)
    assert {r.jurisdiction for r in filed_records} == {"federal", "california"}
    assert all(r.package_reference == f2_reference for r in filed_records)
    assert len(filed_records) == 2  # written once each, not duplicated

    federal_history = [
        e.payload["status"]
        for e in list_events_for_entity(session, "filing_submission", "federal")
    ]
    assert federal_history == ["rejected", "accepted"]

    # The 2028 Letter 566 (noncash contributions, and the gross-receipts
    # reconciliation) drives resolving E3 -- approved, then partner
    # approved, since its estimated tax effect is over 1,000.
    books_total = packet.extracted_value("ev-0103").value
    schc1_engine_value = packet.return_versions[-1].line("SchC.1").value
    _resolve_case(
        session,
        e3_case.case_id,
        e3_case.revision,
        claim="SchC.1",
        old_value=schc1_engine_value,
        new_value=books_total,
        evidence_refs=["D14", "ev-0103", "D21", "ev-0127", "D15"],
    )
    e3_case = next(c for c in list_cases(session) if c.case_id == e3_case.case_id)
    approve_e3 = perform(
        session,
        DANIEL,
        "approve",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        payload={},
        packet=packet,
    )
    assert approve_e3.current_state.status == "awaiting_partner"
    e3_case = next(c for c in list_cases(session) if c.case_id == e3_case.case_id)
    partner_approve_e3 = perform(
        session,
        HELEN,
        "partner_approve",
        entity_id=e3_case.case_id,
        expected_revision=e3_case.revision,
        payload={},
        packet=packet,
    )
    assert partner_approve_e3.current_state.status == "resolved"

    # The Letter 566 pack uses the filed values and shows the receipts
    # reconciliation coming to 151,300 -- not 142,000 + 12,400.
    adjustments = adjustments_by_claim(list_adjustments(session))
    pack = letter_566_pack(packet, adjustments)
    assert pack["notice"]["id"] == "N-2025-L566"
    gross_receipts_item = next(
        item for item in pack["items"] if "reconciliation" in item
    )
    reconciliation = gross_receipts_item["reconciliation"]
    assert Decimal(reconciliation["workpaper_value"]) == Decimal(151300)
    forms_named = {
        entry["form"]: entry["amount"] for entry in reconciliation["forms_named"]
    }
    assert Decimal(forms_named["1099-NEC"]) + Decimal(forms_named["1099-K"]) == Decimal(
        154400
    )
    assert Decimal(forms_named["1099-NEC"]) + Decimal(forms_named["1099-K"]) != Decimal(
        reconciliation["workpaper_value"]
    )
