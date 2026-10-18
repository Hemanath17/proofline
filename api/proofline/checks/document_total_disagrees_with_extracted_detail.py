"""DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL

Rule: for a partially-extracted document actually used by the current
return version, if one of its own summary totals disagrees with the sum of
its own matching line-level detail, that's a sign the unread page holds an
item the summary already counts but the detail doesn't.
"""

from __future__ import annotations

from decimal import Decimal

from proofline.checks.models import CheckResult
from proofline.packet import Packet

CHECK_ID = "DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL"
CHECK_VERSION = 1


def run(packet: Packet) -> list[CheckResult]:
    current = packet.return_versions[-1]
    findings: list[CheckResult] = []

    for document_id in current.documents_used:
        document = packet.document(document_id)
        if document.extraction.status != "partial":
            continue

        document_values = [
            v for v in packet.extracted_values if v.document_id == document_id
        ]
        summary_values = [v for v in document_values if "_summary_" in v.field.lower()]

        for summary_value in summary_values:
            _, suffix = summary_value.field.split("_summary_", 1)
            detail_values = [
                v
                for v in document_values
                if v.field.endswith(f"_{suffix}") and "summary" not in v.field.lower()
            ]
            if not detail_values:
                continue

            try:
                summary_amount = Decimal(str(summary_value.value))
                detail_total = sum(
                    (Decimal(str(v.value)) for v in detail_values), Decimal("0")
                )
            except (TypeError, ValueError):
                continue

            difference = summary_amount - detail_total
            if difference == 0:
                continue

            findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="investments",
                    scope="document",
                    finding_type="error",
                    severity="tax_amount",
                    evidence_refs=[document_id, summary_value.id]
                    + [v.id for v in detail_values],
                    claims=[],
                    observed=(
                        f"{document_id}'s own {summary_value.label or summary_value.field} "
                        f"is {summary_amount}, but the sum of its extracted {suffix} detail "
                        f"is {detail_total} -- a difference of {difference}. "
                        f"{document.extraction.reason or ''}"
                    ).strip(),
                    expected=(
                        "A document's own summary total should equal the sum of its own "
                        "extracted line-level detail."
                    ),
                    tax_effect=None,
                    impact_unknown=True,
                    limitations=(
                        "Only compares the document's own summary and detail; doesn't know "
                        "what the missing page's item actually is."
                    ),
                    recommended_action=(
                        f"Read the unread page of {document_id} and add the missing "
                        "transaction before filing."
                    ),
                )
            )

    return findings
