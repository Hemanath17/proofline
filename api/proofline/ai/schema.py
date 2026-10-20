"""The Evidence Investigator's output shape. Pydantic AI validates every
model response against this before any of our own code sees it -- a
response that doesn't fit (wrong types, an invented `proposed_resolution_
type`) is rejected and retried by Pydantic AI itself, free of charge
(CLAUDE.md: AI output "is a typed Pydantic object" that "goes through the
validator" -- this is the type half of that; `proofline.ai.validator` is
the evidence half).

`SCHEMA_VERSION` is carried in every `ai_suggestion_recorded` event
(`proofline.ai.events`) so a stored suggestion can always be read back
against the shape it was written with -- bump it whenever this schema
changes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from proofline.actions.cases import _RESOLUTION_TYPES

SCHEMA_VERSION = 1


class InvestigatorSuggestion(BaseModel):
    summary: str
    cited_claim_ids: list[str] = Field(default_factory=list)
    cited_document_ids: list[str] = Field(default_factory=list)
    numbers_cited: list[Decimal] = Field(default_factory=list)
    proposed_resolution_type: str
    proposed_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: Literal["supported", "uncertain"]

    @field_validator("proposed_resolution_type")
    @classmethod
    def _known_resolution_type(cls, value: str) -> str:
        if value not in _RESOLUTION_TYPES:
            raise ValueError(
                f"proposed_resolution_type must be one of {sorted(_RESOLUTION_TYPES)}, "
                f"got {value!r}"
            )
        return value
