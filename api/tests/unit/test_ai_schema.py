"""`proofline/ai/schema.py`: anything that doesn't fit the shape never
reaches the validator or the caller -- Pydantic's own validation rejects
it first (CLAUDE.md)."""

from __future__ import annotations

import pytest
from proofline.ai.schema import InvestigatorSuggestion
from pydantic import ValidationError


def test_a_valid_suggestion_parses() -> None:
    suggestion = InvestigatorSuggestion(
        summary="The household SSN disagrees with an identity document.",
        cited_claim_ids=["household:theo:ssn"],
        cited_document_ids=["D71"],
        numbers_cited=[],
        proposed_resolution_type="adjust_number",
        proposed_fields={
            "adjustments": [
                {
                    "claim": "household:theo:ssn",
                    "old_value": "666-74-3309",
                    "new_value": "666-74-3390",
                }
            ]
        },
        confidence="supported",
    )
    assert suggestion.confidence == "supported"


def test_an_unknown_resolution_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InvestigatorSuggestion(
            summary="x",
            proposed_resolution_type="close_the_case",
            confidence="uncertain",
        )
