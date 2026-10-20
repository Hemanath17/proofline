"""Sanity-checks the golden set itself (`api/eval/golden_cases.py`)
against `proofline.ai.validator` and the real packet -- no model call, so
this runs in the normal suite, not under `eval`. If this fails, the
golden set's own facts are wrong, not the investigator's.
"""

from __future__ import annotations

import pytest
from eval.golden_cases import GOLDEN_CASES, GoldenCase
from proofline.ai.schema import InvestigatorSuggestion
from proofline.ai.validator import validate_suggestion
from proofline.db.models import Case
from proofline.packet import load_packet


def _case_row(golden: GoldenCase) -> Case:
    return Case(
        case_id=f"case-golden-{golden.error_id}",
        root_cause_key=f"golden:{golden.error_id}",
        origin=golden.origin,
        scope=golden.scope,
        claims=list(golden.claims),
        severity=golden.severity,
        finding_type=golden.finding_type,
        status="investigating",
        revision=1,
        evidence_refs=list(golden.case_evidence_refs),
        tax_effect_federal=golden.tax_effect_federal,
        tax_effect_california=golden.tax_effect_california,
        impact_unknown=golden.impact_unknown,
    )


def _correct_suggestion(golden: GoldenCase) -> InvestigatorSuggestion:
    return InvestigatorSuggestion(
        summary=golden.observed,
        cited_claim_ids=list(golden.required_claim_citations),
        cited_document_ids=list(golden.required_document_citations),
        numbers_cited=list(golden.required_numbers),
        proposed_resolution_type=golden.correct_resolution_type,
        proposed_fields=golden.correct_fields,
        confidence="supported",
    )


@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_the_correct_suggestion_passes_validation(golden: GoldenCase) -> None:
    packet = load_packet()
    result = validate_suggestion(packet, _case_row(golden), _correct_suggestion(golden))
    assert result.ok, (golden.error_id, result.reasons)


@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_citing_a_distractor_document_fails(golden: GoldenCase) -> None:
    if not golden.distractor_documents:
        pytest.skip("no distractor documents recorded for this case")
    packet = load_packet()
    suggestion = _correct_suggestion(golden).model_copy(
        update={
            "cited_document_ids": [
                *golden.required_document_citations,
                *golden.distractor_documents,
            ]
        }
    )
    result = validate_suggestion(packet, _case_row(golden), suggestion)
    assert not result.ok
    assert any(
        distractor in reason
        for reason in result.reasons
        for distractor in golden.distractor_documents
    )


@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_required_documents_actually_exist(golden: GoldenCase) -> None:
    packet = load_packet()
    for document_id in golden.required_document_citations:
        packet.document(document_id)  # raises KeyError if it doesn't exist


@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g.error_id)
def test_distractor_documents_are_real_but_excluded(golden: GoldenCase) -> None:
    packet = load_packet()
    for document_id in golden.distractor_documents:
        packet.document(document_id)  # must be real
        assert document_id not in golden.case_evidence_refs
