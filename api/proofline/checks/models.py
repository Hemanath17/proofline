"""CheckResult, per .claude/rules/checks.md. Every check returns a list of
these; nothing else defines the shape of a finding."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from proofline.provenance.claim_identity import ClaimIdentity

Area = Literal[
    "identity",
    "wages",
    "investments",
    "business",
    "rentals",
    "pass_throughs",
    "deductions_credits",
    "california",
    "tax_computation",
]

Scope = Literal["document", "extracted_value", "transaction", "asset", "return"]

FindingType = Literal["error", "possible_discrepancy"]

Severity = Literal["blocks_filing", "penalty_risk", "tax_amount", "info"]


Direction = Literal["overstated", "understated"]


class TaxEffect(BaseModel):
    federal: Decimal
    california: Decimal
    kind: Literal["exact", "estimate"]
    direction: Direction


class CheckResult(BaseModel):
    check_id: str
    check_version: int
    area: Area
    scope: Scope
    finding_type: FindingType
    severity: Severity
    evidence_refs: list[str] = []
    claims: list[ClaimIdentity] = []
    observed: str
    expected: str
    tax_effect: TaxEffect | None
    impact_unknown: bool = False
    limitations: str
    recommended_action: str


class CheckFailure(BaseModel):
    """A check module that raised instead of returning findings. The runner
    records one of these and keeps running the other checks, rather than
    letting one broken check take down the whole run."""

    check_id: str
    error: str
