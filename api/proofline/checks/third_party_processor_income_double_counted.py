"""THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED

Rule: when a gross-receipts line adds a books total and a 1099-K's gross
amount together, and the books' own transaction detail shows that the same
payment processor's receipts were already deposited and recorded in the
books, the 1099-K's amount for that processor is double-counted.
"""

from __future__ import annotations

from decimal import Decimal

from proofline.checks.models import CheckResult, TaxEffect
from proofline.packet import Packet
from proofline.provenance.claim_identity import return_total

CHECK_ID = "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED"
CHECK_VERSION = 1


def _processor_token(issuer: str) -> str:
    return issuer.split()[0].lower()


def _books_overlap_value(packet: Packet, processor_token: str):
    for candidate in packet.extracted_values:
        if candidate.label is None:
            continue
        if processor_token not in candidate.label.lower():
            continue
        document = packet.document(candidate.document_id)
        if document.document_type == "books_transaction_detail":
            return candidate
    return None


def run(packet: Packet) -> list[CheckResult]:
    current = packet.return_versions[-1]
    rate = current.tax_effect_rates.get("schc_profit")

    findings: list[CheckResult] = []
    for line in current.lines:
        books_value = None
        processor_values = []
        for ref in line.sources:
            if not ref.startswith("ev-"):
                continue
            value = packet.extracted_value(ref)
            document = packet.document(value.document_id)
            if document.document_type == "books_profit_loss":
                books_value = value
            elif document.document_type == "1099-K":
                processor_values.append(value)

        if books_value is None or not processor_values:
            continue

        for processor_value in processor_values:
            processor_document = packet.document(processor_value.document_id)
            token = _processor_token(processor_document.issuer)
            overlap_value = _books_overlap_value(packet, token)
            if overlap_value is None:
                continue
            overlap_amount = Decimal(str(overlap_value.value))
            if overlap_amount <= 0:
                continue

            tax_effect = None
            if rate is not None:
                tax_effect = TaxEffect(
                    federal=(overlap_amount * rate.federal_per_dollar).quantize(
                        Decimal("0.01")
                    ),
                    california=(overlap_amount * rate.california_per_dollar).quantize(
                        Decimal("0.01")
                    ),
                    kind="estimate",
                )

            findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="business",
                    scope="return",
                    finding_type="error",
                    severity="tax_amount",
                    evidence_refs=[
                        line.key,
                        books_value.id,
                        processor_value.id,
                        overlap_value.id,
                    ],
                    claims=[return_total(line.key)],
                    observed=(
                        f"{line.key} adds the full {processor_document.issuer} 1099-K amount "
                        "on top of the books total, but the books' own transaction detail "
                        f"shows {overlap_amount} of that processor's receipts were already "
                        "deposited and recorded in the books."
                    ),
                    expected=(
                        "A payment processor's 1099-K income that's already reflected in "
                        "the books shouldn't be added again."
                    ),
                    tax_effect=tax_effect,
                    impact_unknown=tax_effect is None,
                    limitations=(
                        "Matches the 1099-K issuer's name against the books' own "
                        "transaction-detail labels; relies on that label naming the processor."
                    ),
                    recommended_action=(
                        "Reduce gross receipts by the amount already recorded in the books "
                        "through this processor before filing."
                    ),
                )
            )

    return findings
