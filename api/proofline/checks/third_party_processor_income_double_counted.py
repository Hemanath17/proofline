"""THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED

Rule: when a gross-receipts line adds a books total and a 1099-K's gross
amount together, and the books' own transaction detail shows that the same
payment processor's receipts were already deposited and recorded in the
books, the 1099-K's amount for that processor is double-counted. The
double-counted amount is the books' own total for that processor, capped at
what the 1099-K itself reports (the 1099-K can't be double-counted by more
than its own face amount).
"""

from __future__ import annotations

import re
from decimal import Decimal

from proofline.checks.models import CheckResult, TaxEffect
from proofline.checks.money import parse_money
from proofline.packet import Packet
from proofline.provenance.claim_identity import return_total

CHECK_ID = "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED"
CHECK_VERSION = 2

_CORPORATE_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "payments",
    "payment",
    "the",
    "ltd",
    "llc",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize_processor_name(issuer: str) -> str:
    """The full issuer name, lowercased, with punctuation and common
    corporate-suffix words stripped -- "Paywell Payments, Inc." becomes
    "paywell". Matching on the whole remaining phrase (not just its first
    word) avoids both a false miss, when the distinctive word isn't first,
    and a false match, when a generic first word is shared by two issuers."""
    words = [
        w for w in _WORD_RE.findall(issuer.lower()) if w not in _CORPORATE_SUFFIXES
    ]
    return " ".join(words)


def _books_overlap_values(packet: Packet, processor_name: str) -> list:
    matches = []
    for candidate in packet.extracted_values:
        if candidate.label is None:
            continue
        if processor_name not in candidate.label.lower():
            continue
        document = packet.document(candidate.document_id)
        if document.document_type == "books_transaction_detail":
            matches.append(candidate)
    return matches


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
            processor_name = _normalize_processor_name(processor_document.issuer)
            if not processor_name:
                continue
            overlap_values = _books_overlap_values(packet, processor_name)
            if not overlap_values:
                continue
            overlap_total = sum(
                (parse_money(v.value) or Decimal(0) for v in overlap_values),
                Decimal(0),
            )
            if overlap_total <= 0:
                continue

            processor_amount = parse_money(processor_value.value) or Decimal(0)
            double_counted = min(overlap_total, processor_amount)
            if double_counted <= 0:
                continue

            tax_effect = None
            if rate is not None:
                tax_effect = TaxEffect(
                    federal=(double_counted * rate.federal_per_dollar).quantize(
                        Decimal("0.01")
                    ),
                    california=(double_counted * rate.california_per_dollar).quantize(
                        Decimal("0.01")
                    ),
                    kind="estimate",
                    direction="overstated",
                )

            findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="business",
                    scope="return",
                    finding_type="error",
                    severity="tax_amount",
                    evidence_refs=sorted(
                        {
                            line.key,
                            books_value.id,
                            processor_value.id,
                            *(v.id for v in overlap_values),
                        }
                    ),
                    claims=[return_total(line.key)],
                    observed=(
                        f"{line.key} adds the full {processor_document.issuer} 1099-K amount "
                        "on top of the books total, but the books' own transaction detail "
                        f"shows {double_counted} of that processor's receipts were already "
                        "deposited and recorded in the books."
                    ),
                    expected=(
                        "A payment processor's 1099-K income that's already reflected in "
                        "the books shouldn't be added again."
                    ),
                    tax_effect=tax_effect,
                    impact_unknown=tax_effect is None,
                    limitations=(
                        "Matches the 1099-K issuer's normalized name against the books' own "
                        "transaction-detail labels; relies on that label naming the "
                        "processor, and caps the double count at the 1099-K's own amount."
                    ),
                    recommended_action=(
                        "Reduce gross receipts by the amount already recorded in the books "
                        "through this processor before filing."
                    ),
                )
            )

    return findings
