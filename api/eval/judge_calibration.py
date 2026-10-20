"""Ten hand-labeled cases, used to confirm a DeepEval judge model actually
agrees with a human before it's trusted for anything real (docs/PLAN.md
Step 10, Part 4 point 5). All ten are grounded in this packet's own real
facts (the same ones `golden_cases.py` already uses) -- four summaries
that clearly assert something the evidence does NOT support, and six that
clearly say only what the evidence does support. None of this is
synthetic/invented packet data; the four "unsupported" ones are real
summaries written to overstate real evidence, not fictional scenarios.

Hand-labeled by a human (not generated) before any judge model sees them,
same discipline as the golden set itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationCase:
    summary: str
    retrieval_context: tuple[str, ...]
    has_unsupported_claim: bool


CALIBRATION_CASES: tuple[CalibrationCase, ...] = (
    # -- Four that clearly contain an unsupported claim --
    CalibrationCase(
        summary="Theo's household-record SSN matches the SSN on his Social Security card.",
        retrieval_context=(
            "Household record SSN for Theo Lindqvist-Okafor: 666-74-3309.",
            "Social Security card on file for Theo Lindqvist-Okafor (D71, ev-1080): 666-74-3390.",
        ),
        has_unsupported_claim=True,
    ),
    CalibrationCase(
        summary=(
            "Northlake lots N1, N3 and N4's basis of $0.00 is confirmed correct by "
            "the broker's own 1099-B, with no supplement on file suggesting otherwise."
        ),
        retrieval_context=(
            "Northlake Securities 1099-B reports lots N1, N3, N4 as noncovered, basis 0.00.",
            (
                "Corvane Systems stock plan supplement gives adjusted cost basis 19,100.00 "
                "for the lot acquired on N1's date, 19,100.00 for N3's date, and 9,420.00 "
                "for N4's date."
            ),
        ),
        has_unsupported_claim=True,
    ),
    CalibrationCase(
        summary=(
            "SchC.1's $163,700 in gross receipts is fully independent of the "
            "Paywell Payments 1099-K; there is no overlap between the two."
        ),
        retrieval_context=(
            "SchC.1 gross receipts 163,700 = books income 151,300 + Form 1099-K 12,400.",
            (
                "Books transaction detail: 12,400 of Paywell Payments' 1099-K amount was "
                "already deposited and recorded in the books."
            ),
        ),
        has_unsupported_claim=True,
    ),
    CalibrationCase(
        summary=(
            "Erik supplied a bank statement confirming digital asset lot C6's cost "
            "basis of about 3,050."
        ),
        retrieval_context=(
            (
                'Client message (msg-07): "that BTC was bought on another exchange in '
                "March 2021 for about 3,050 ... I only have a bank statement line showing "
                "3,050 to 'CryptoNorth' on 03/15/2021.\""
            ),
            "No bank statement document is on file for this lot.",
        ),
        has_unsupported_claim=True,
    ),
    # -- Six that clearly do NOT contain an unsupported claim --
    CalibrationCase(
        summary=(
            "The household record's SSN for Theo doesn't match the SSN on his Social "
            "Security card on file."
        ),
        retrieval_context=(
            "Household record SSN for Theo Lindqvist-Okafor: 666-74-3309.",
            "Social Security card on file for Theo Lindqvist-Okafor (D71, ev-1080): 666-74-3390.",
        ),
        has_unsupported_claim=False,
    ),
    CalibrationCase(
        summary=(
            "Noncovered RSU lots N1, N3 and N4 report basis 0.00, but the employer's "
            "own stock plan supplement gives a nonzero adjusted cost basis for each, "
            "totaling an estimated $15,535.56 federal, $1,619.08 California."
        ),
        retrieval_context=(
            "Northlake Securities 1099-B reports lots N1, N3, N4 as noncovered, basis 0.00.",
            (
                "Corvane Systems stock plan supplement gives adjusted cost basis 19,100.00, "
                "19,100.00 and 9,420.00 for the matching acquisition dates."
            ),
            "Estimated tax effect: federal 15,535.56, California 1,619.08.",
        ),
        has_unsupported_claim=False,
    ),
    CalibrationCase(
        summary=(
            "SchC.1 adds the full Paywell Payments 1099-K amount on top of the books "
            "total, but the books' own transaction detail shows that processor's "
            "receipts were already deposited and recorded in the books."
        ),
        retrieval_context=(
            "SchC.1 gross receipts 163,700 = books income 151,300 + Form 1099-K 12,400.",
            (
                "Books transaction detail: 12,400 of Paywell Payments' 1099-K amount was "
                "already deposited and recorded in the books."
            ),
        ),
        has_unsupported_claim=False,
    ),
    CalibrationCase(
        summary=(
            "D31's own summary proceeds total of 71,965.00 disagrees with the sum of "
            "its own extracted detail; an unread page is the likely cause."
        ),
        retrieval_context=(
            "D31 (1099-B) summary proceeds total: 71,965.00 (ev-0703).",
            "D31's extracted line-level proceeds detail sums to 71,715.00.",
            "D31 page 32 ('Additional transactions') was not read by the extraction pipeline.",
        ),
        has_unsupported_claim=False,
    ),
    CalibrationCase(
        summary=(
            "Digital asset lot C6 has no basis on file; the engine used zero. The "
            "client states a basis of about 3,050, supported only by his own message "
            "so far, with no bank statement on file yet."
        ),
        retrieval_context=(
            "Coinhaven lot C6 (0.05 BTC, proceeds 5,325.00): basis blank, engine used 0.00.",
            (
                'Client message (msg-07): "bought ... for about 3,050 ... I only have a '
                'bank statement line showing 3,050 ... "'
            ),
            "No bank statement document is on file for this lot.",
        ),
        has_unsupported_claim=False,
    ),
    CalibrationCase(
        summary=(
            "D64, a handwritten donation receipt, reads ambiguously as either 1,500 "
            "or 7,500. The client confirmed 1,500 by phone, matching a bank check, and "
            "that's the amount the return already uses."
        ),
        retrieval_context=(
            "D64 (handwritten donation receipt): extracted value 1,500.00 at confidence 0.41.",
            (
                'Client message (msg-08): "St. Brigid confirmed by phone the gift was '
                '1,500 - matches our bank statement (check #2207, 12/21/2025)."'
            ),
        ),
        has_unsupported_claim=False,
    ),
)
