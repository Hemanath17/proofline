"""The golden set for the Evidence Investigator (Step 10, Part 4): one
case per confirmed error (E1-E4) plus two of the "possible" ones (E5, E9),
all from docs/ERRORS.md, built from the real evidence those errors are
already on record as resting on -- `api/fixtures/baseline_expectations.json`
and each check's own fixture for E1-E4 (never re-derived from the packet
by hand), and the exact ids/values packet-explorer confirmed for E5/E9
(see docs/DECISIONS.md for how those two were chosen and confirmed).

Written BEFORE the investigator is ever run against it
(`api/eval/test_investigator_eval.py`), same discipline as any golden set.

Each case records:
- `claims`: the claim identity keys this case's finding is about.
- `case_evidence_refs`: this case's own `evidence_refs`, exactly the shape
  `Case.evidence_refs` carries -- this is what `proofline.ai.validator`
  checks every citation against.
- `required_claim_citations`/`required_document_citations`: at least one
  of each must appear in a correct investigation's citations.
- `required_numbers`: numbers a correct summary must state (each must
  actually be verifiable against the case's own evidence -- see
  `proofline.ai.validator._evidence_numbers`).
- `correct_resolution_type`/`correct_fields`: what a correct proposal
  would look like.
- `distractor_documents`: documents that exist in the packet, and may
  even share the same return line, but do NOT belong to this specific
  case's own evidence -- the investigator must not cite these.

E4 and E5's `correct_resolution_type` are judgment calls rather than
clean fits (neither is a dollar discrepancy on the return itself): E4 is
a documentation gap (the engine already used the document's own summary
total; what's missing is confirmation of one unread page), so the
realistic next step is a recorded judgment to proceed pending that page,
not an invented adjustment amount. E9 is a resolved OCR ambiguity (the
engine already used the client-confirmed amount), so the realistic
resolution is choosing the client's phone confirmation over the
handwritten receipt's own low-confidence read.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class GoldenCase:
    error_id: str
    check_id: str | None
    area: str
    scope: str
    severity: str
    finding_type: str
    origin: str
    claims: tuple[str, ...]
    case_evidence_refs: tuple[str, ...]
    required_claim_citations: tuple[str, ...]
    required_document_citations: tuple[str, ...]
    required_numbers: tuple[Decimal, ...]
    correct_resolution_type: str
    correct_fields: dict[str, Any]
    distractor_documents: tuple[str, ...] = ()
    tax_effect_federal: Decimal | None = None
    tax_effect_california: Decimal | None = None
    impact_unknown: bool = False
    observed: str = ""
    expected: str = ""


GOLDEN_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        error_id="E1",
        check_id="DEPENDENT_SSN_INDEPENDENT_SOURCE",
        area="identity",
        scope="return",
        severity="blocks_filing",
        finding_type="error",
        origin="check",
        claims=("household:theo:ssn",),
        case_evidence_refs=(
            "household:theo",
            "ev-1080",
            "py:/return_2024/dependents/1",
            "agency:/efile/0",
        ),
        required_claim_citations=("household:theo:ssn",),
        required_document_citations=("D71",),
        required_numbers=(),
        correct_resolution_type="adjust_number",
        correct_fields={
            "adjustments": [
                {
                    "claim": "household:theo:ssn",
                    "old_value": "666743309",
                    "new_value": "666743390",
                }
            ]
        },
        distractor_documents=("D01",),
        observed=(
            "The household record's SSN for Theo doesn't match the SSN on his "
            "Social Security card."
        ),
        expected="A person's SSN matches their own independent source.",
    ),
    GoldenCase(
        error_id="E2",
        check_id="RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE",
        area="investments",
        scope="transaction",
        severity="tax_amount",
        finding_type="error",
        origin="check",
        claims=(
            "1099b_lot:Northlake Securities:N1",
            "1099b_lot:Northlake Securities:N3",
            "1099b_lot:Northlake Securities:N4",
        ),
        case_evidence_refs=(
            "ev-0066",
            "ev-0067",
            "ev-0068",
            "ev-0069",
            "ev-0070",
            "ev-0071",
            "ev-0493",
            "ev-0495",
            "ev-0498",
            "ev-0511",
            "ev-0513",
            "ev-0516",
            "ev-0520",
            "ev-0522",
            "ev-0525",
        ),
        required_claim_citations=(
            "1099b_lot:Northlake Securities:N1",
            "1099b_lot:Northlake Securities:N3",
            "1099b_lot:Northlake Securities:N4",
        ),
        required_document_citations=("D28", "D11"),
        required_numbers=(Decimal("15535.56"),),
        correct_resolution_type="adjust_number",
        correct_fields={
            "adjustments": [
                {
                    "claim": "1099b_lot:Northlake Securities:N1",
                    "old_value": "0.00",
                    "new_value": "19100.00",
                },
                {
                    "claim": "1099b_lot:Northlake Securities:N3",
                    "old_value": "0.00",
                    "new_value": "19100.00",
                },
                {
                    "claim": "1099b_lot:Northlake Securities:N4",
                    "old_value": "0.00",
                    "new_value": "9420.00",
                },
            ]
        },
        distractor_documents=("D01",),
        tax_effect_federal=Decimal("15535.56"),
        tax_effect_california=Decimal("1619.08"),
        observed=(
            "Noncovered RSU lots N1, N3, N4 report basis 0.00, but the employer's "
            "own stock plan supplement gives a nonzero adjusted cost basis for each."
        ),
        expected="A noncovered lot's basis should use the employer's own records when available.",
    ),
    GoldenCase(
        error_id="E3",
        check_id="THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED",
        area="business",
        scope="return",
        severity="tax_amount",
        finding_type="error",
        origin="check",
        claims=("SchC.1",),
        case_evidence_refs=("SchC.1", "ev-0103", "ev-0109", "ev-0127"),
        required_claim_citations=("SchC.1",),
        required_document_citations=("D14", "D21"),
        required_numbers=(Decimal("4402.00"),),
        correct_resolution_type="adjust_number",
        correct_fields={
            "adjustments": [
                {"claim": "SchC.1", "old_value": "163700.00", "new_value": "151300.00"}
            ]
        },
        distractor_documents=("D01",),
        tax_effect_federal=Decimal("4402.00"),
        tax_effect_california=Decimal("384.40"),
        observed=(
            "SchC.1 adds the full Paywell 1099-K amount on top of the books total, "
            "but the books' own transaction detail shows that processor's receipts "
            "were already deposited and recorded."
        ),
        expected="A payment processor's 1099-K income already in the books shouldn't be added again.",
    ),
    GoldenCase(
        error_id="E4",
        check_id="DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL",
        area="investments",
        scope="document",
        severity="tax_amount",
        finding_type="error",
        origin="check",
        claims=(),
        case_evidence_refs=(
            "D31",
            "ev-0703",
            "ev-0708",
            "ev-0717",
            "ev-0726",
            "ev-0735",
            "ev-0744",
            "ev-0753",
            "ev-0762",
            "ev-0771",
            "ev-0780",
            "ev-0789",
            "ev-0798",
            "ev-0807",
            "ev-0816",
            "ev-0825",
            "ev-0834",
            "ev-0843",
            "ev-0852",
        ),
        required_claim_citations=(),
        required_document_citations=("D31",),
        required_numbers=(Decimal("71965.00"),),
        correct_resolution_type="record_judgment",
        correct_fields={
            "reasoning": (
                "D31 page 32 (an unread page) accounts for the full $250 gap "
                "between the document's own summary and its extracted detail; "
                "the summary total is already what the return uses, so no number "
                "on the return needs adjusting pending that page being read."
            ),
            "authority": "the firm's own document-completeness review",
            "approved_by": "reviewing CPA",
        },
        distractor_documents=("D01",),
        impact_unknown=True,
        observed=(
            "D31's own summary proceeds total disagrees with the sum of its own "
            "extracted detail -- an unread page is the likely cause."
        ),
        expected="A document's own summary should equal the sum of its own extracted detail.",
    ),
    GoldenCase(
        error_id="E5",
        check_id=None,
        area="investments",
        scope="transaction",
        severity="tax_amount",
        finding_type="possible_discrepancy",
        origin="document",
        claims=("digital_asset_lot:Coinhaven Exchange, Inc.:C6",),
        case_evidence_refs=("ev-0918", "ev-0919", "msg-07", "F8949.H.C6"),
        required_claim_citations=("digital_asset_lot:Coinhaven Exchange, Inc.:C6",),
        required_document_citations=("D35",),
        required_numbers=(Decimal("5325.00"),),
        correct_resolution_type="record_judgment",
        correct_fields={
            "reasoning": (
                "Erik states lot C6 (0.05 BTC) was bought in March 2021 for about "
                "3,050 on an exchange that has since closed, with only a bank "
                "statement line as support -- the client's own statement alone "
                "doesn't verify this, so accepting the 3,050 basis is a recorded "
                "judgment pending the bank statement itself."
            ),
            "authority": "client statement (msg-07), pending bank statement",
            "approved_by": "reviewing CPA",
        },
        distractor_documents=("D01",),
        impact_unknown=True,
        observed=(
            "Coinhaven digital asset lot C6 has no basis on file; the engine used "
            "zero. The client states a basis of about 3,050, supported only by his "
            "own message so far."
        ),
        expected="A disposed digital asset lot's basis should be supported by evidence, not left at zero by default.",
    ),
    GoldenCase(
        error_id="E9",
        check_id=None,
        area="deductions_credits",
        scope="document",
        severity="info",
        finding_type="possible_discrepancy",
        origin="document",
        claims=("SchA.11",),
        # Deliberately excludes D63/ev-1047/ev-1048 -- those are a DIFFERENT
        # donation receipt that also feeds SchA.11, but have nothing to do
        # with D64's OCR ambiguity. They're the distractor below, not part
        # of this case's own evidence.
        case_evidence_refs=("ev-1049", "msg-08"),
        required_claim_citations=("SchA.11",),
        required_document_citations=("D64",),
        required_numbers=(Decimal("1500.00"),),
        correct_resolution_type="resolve_evidence_conflict",
        correct_fields={
            "evidence_a": "ev-1049",
            "evidence_b": "msg-08",
            "chosen": "b",
            "reason": "client confirmed by phone, matching the bank check",
        },
        distractor_documents=("D63",),
        impact_unknown=True,
        observed=(
            "D64, a handwritten donation receipt, reads ambiguously as either "
            "1,500 or 7,500 (OCR confidence 0.41). The client confirmed 1,500 by "
            "phone, matching a bank check, and that's the amount already used."
        ),
        expected="A low-confidence read should be confirmed by independent evidence before being relied on.",
    ),
)


def golden_case_by_error_id(error_id: str) -> GoldenCase:
    return next(case for case in GOLDEN_CASES if case.error_id == error_id)
