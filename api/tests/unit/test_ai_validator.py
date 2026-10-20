"""`proofline/ai/validator.py`: pure deterministic validation, no model
calls. Built against the real packet and the real evidence_refs/claims
two of the existing confirmed-check fixtures already produce
(`api/fixtures/DEPENDENT_SSN_INDEPENDENT_SOURCE.json`,
`api/fixtures/THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED.json`), not
invented packet facts.
"""

from __future__ import annotations

from decimal import Decimal

from proofline.ai.schema import InvestigatorSuggestion
from proofline.ai.validator import validate_suggestion
from proofline.db.models import Case
from proofline.packet import load_packet


def _ssn_case(status: str = "investigating") -> Case:
    return Case(
        case_id="case-ssn-test",
        root_cause_key="test:ssn",
        origin="check",
        scope="return",
        claims=["household:theo:ssn"],
        severity="blocks_filing",
        status=status,
        revision=1,
        evidence_refs=[
            "household:theo",
            "ev-1080",
            "py:/return_2024/dependents/1",
            "agency:/efile/0",
        ],
        impact_unknown=False,
    )


def _processor_case() -> Case:
    return Case(
        case_id="case-processor-test",
        root_cause_key="test:processor",
        origin="check",
        scope="return",
        claims=["SchC.1"],
        severity="tax_amount",
        status="investigating",
        revision=1,
        evidence_refs=["SchC.1", "ev-0103", "ev-0109", "ev-0127"],
        tax_effect_federal=Decimal("4402.00"),
        tax_effect_california=Decimal("384.40"),
        impact_unknown=False,
    )


def test_a_well_cited_suggestion_passes() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="Theo's household SSN disagrees with his Social Security card.",
        cited_claim_ids=["household:theo:ssn"],
        cited_document_ids=["D71"],
        numbers_cited=[],
        proposed_resolution_type="adjust_number",
        proposed_fields={
            "adjustments": [
                {
                    "claim": "household:theo:ssn",
                    "old_value": "666743309",
                    "new_value": "666743390",
                }
            ]
        },
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(), suggestion)
    assert result.ok, result.reasons


def test_citing_a_claim_outside_the_case_fails() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["SchC.1"],  # belongs to a different case entirely
        proposed_resolution_type="mark_legitimate",
        proposed_fields={"reason": "expected"},
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(), suggestion)
    assert not result.ok
    assert any("doesn't belong to case" in reason for reason in result.reasons)


def test_citing_a_document_not_behind_this_cases_evidence_fails() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["household:theo:ssn"],
        cited_document_ids=["D01"],  # real document, not this case's evidence
        proposed_resolution_type="mark_legitimate",
        proposed_fields={"reason": "expected"},
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(), suggestion)
    assert not result.ok
    assert any("D01" in reason for reason in result.reasons)


def test_an_invented_number_fails() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["SchC.1"],
        cited_document_ids=["D14"],
        numbers_cited=[Decimal("999999.99")],
        proposed_resolution_type="adjust_number",
        proposed_fields={
            "adjustments": [
                {"claim": "SchC.1", "old_value": "163700.00", "new_value": "151300.00"}
            ]
        },
        confidence="supported",
    )
    result = validate_suggestion(packet, _processor_case(), suggestion)
    assert not result.ok
    assert any("999999.99" in reason for reason in result.reasons)


def test_the_cases_own_tax_effect_counts_as_evidence() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["SchC.1"],
        cited_document_ids=["D14"],
        numbers_cited=[Decimal("4402.00")],
        proposed_resolution_type="adjust_number",
        proposed_fields={
            "adjustments": [
                {"claim": "SchC.1", "old_value": "163700.00", "new_value": "151300.00"}
            ]
        },
        confidence="supported",
    )
    result = validate_suggestion(packet, _processor_case(), suggestion)
    assert result.ok, result.reasons


def test_a_resolution_type_that_doesnt_fit_its_own_fields_fails() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["household:theo:ssn"],
        proposed_resolution_type="resolve_evidence_conflict",
        proposed_fields={},  # missing evidence_a/evidence_b/chosen/reason
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(), suggestion)
    assert not result.ok


def test_a_case_not_investigating_fails_the_state_check() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        cited_claim_ids=["household:theo:ssn"],
        cited_document_ids=["D71"],
        proposed_resolution_type="mark_legitimate",
        proposed_fields={"reason": "expected"},
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(status="resolved"), suggestion)
    assert not result.ok
    assert any("not investigating" in reason for reason in result.reasons)


def test_a_non_judgment_resolution_needs_some_evidence() -> None:
    packet = load_packet()
    suggestion = InvestigatorSuggestion(
        summary="x",
        proposed_resolution_type="mark_legitimate",
        proposed_fields={"reason": "expected"},
        confidence="supported",
    )
    result = validate_suggestion(packet, _ssn_case(), suggestion)
    assert not result.ok
    assert any("supporting evidence" in reason for reason in result.reasons)
