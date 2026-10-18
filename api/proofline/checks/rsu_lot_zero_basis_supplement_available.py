"""RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE

Rule: a noncovered 1099-B lot reporting basis 0.00 should use the issuing
employer's own stock-plan cost-basis supplement when one is available,
matched to the lot by its acquisition date, rather than carrying 0.
"""

from __future__ import annotations

from decimal import Decimal

from proofline.checks.models import CheckResult, TaxEffect
from proofline.packet import ExtractedValue, Packet
from proofline.provenance.claim_identity import lot_1099b

CHECK_ID = "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE"
CHECK_VERSION = 1


def _lot_fields(
    packet: Packet, line_key: str, sources: list[str]
) -> dict[str, ExtractedValue]:
    """Every extracted value for this lot's prefix on its source document --
    not just the ones the line's own `sources` lists, since a line only
    lists the fields its rule actually used to compute the line's value
    (proceeds and basis), not descriptive fields like term or covered."""
    prefix = line_key.split(".")[-1]

    document_id = None
    for ref in sources:
        if ref.startswith("ev-"):
            document_id = packet.extracted_value(ref).document_id
            break
    if document_id is None:
        return {}

    fields: dict[str, ExtractedValue] = {}
    for value in packet.extracted_values:
        if value.document_id == document_id and value.field.startswith(f"{prefix}_"):
            fields[value.field[len(prefix) + 1 :]] = value
    return fields


def _stock_plan_supplement_basis(
    packet: Packet, acquired_date: str
) -> tuple[str, Decimal] | None:
    for value in packet.extracted_values:
        if not value.field.endswith("_adjusted_basis"):
            continue
        document = packet.document(value.document_id)
        if document.document_type != "stock_plan_supplement":
            continue
        prefix = value.field[: -len("_adjusted_basis")]
        acquired_field = f"{prefix}_acquired"
        sibling = next(
            (
                other
                for other in packet.extracted_values
                if other.document_id == value.document_id
                and other.field == acquired_field
            ),
            None,
        )
        if sibling is not None and str(sibling.value) == acquired_date:
            return value.id, Decimal(str(value.value))
    return None


def run(packet: Packet) -> list[CheckResult]:
    current = packet.return_versions[-1]
    rates = current.tax_effect_rates

    matched_lots: list[dict] = []
    for line in current.lines:
        if line.form != "F8949":
            continue
        fields = _lot_fields(packet, line.key, line.sources)
        if "basis" not in fields or "covered" not in fields or "acquired" not in fields:
            continue
        if fields["covered"].value:
            continue
        if Decimal(str(fields["basis"].value)) != 0:
            continue

        supplement = _stock_plan_supplement_basis(packet, str(fields["acquired"].value))
        if supplement is None:
            continue
        supplement_ev_id, supplement_basis = supplement

        issuer = packet.document(fields["basis"].document_id).issuer
        term = str(fields["term"].value) if "term" in fields else None
        rate_key = "stcg" if term == "short" else "ltcg"

        matched_lots.append(
            {
                "line_key": line.key,
                "lot_id": line.key.split(".")[-1],
                "issuer": issuer,
                "basis_change": supplement_basis,
                "rate": rates.get(rate_key),
                "evidence": [
                    fields["basis"].id,
                    fields["acquired"].id,
                    supplement_ev_id,
                ],
            }
        )

    if not matched_lots:
        return []

    federal_total = Decimal("0")
    california_total = Decimal("0")
    evidence_refs: list[str] = []
    claims = []
    for lot in matched_lots:
        rate = lot["rate"]
        if rate is not None:
            federal_total += lot["basis_change"] * rate.federal_per_dollar
            california_total += lot["basis_change"] * rate.california_per_dollar
        evidence_refs.extend(lot["evidence"])
        claims.append(lot_1099b(lot["issuer"], lot["lot_id"]))

    lot_descriptions = ", ".join(
        f"{lot['lot_id']} ({lot['line_key']})" for lot in matched_lots
    )

    return [
        CheckResult(
            check_id=CHECK_ID,
            check_version=CHECK_VERSION,
            area="investments",
            scope="transaction",
            finding_type="error",
            severity="tax_amount",
            evidence_refs=sorted(set(evidence_refs)),
            claims=claims,
            observed=(
                f"Noncovered lots {lot_descriptions} report basis 0.00, but the issuing "
                "employer's own stock plan supplement gives a nonzero adjusted cost basis "
                "for each, matched to the lot by acquisition date."
            ),
            expected=(
                "A noncovered RSU lot's basis should use the issuing employer's own "
                "cost-basis records when available, not 0."
            ),
            tax_effect=TaxEffect(
                federal=federal_total.quantize(Decimal("0.01")),
                california=california_total.quantize(Decimal("0.01")),
                kind="estimate",
            ),
            impact_unknown=False,
            limitations=(
                "Estimated from tax_effect_rates, not a recomputation of the engine; "
                "assumes the supplement's basis applies in full."
            ),
            recommended_action=(
                "Apply each lot's adjusted cost basis from the employer's stock plan "
                "supplement and correct Form 8949 before filing."
            ),
        )
    ]
