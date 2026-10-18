"""RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE

Rule: a noncovered 1099-B lot reporting basis 0.00 (or blank, which is
treated the same) should use the issuing employer's own stock-plan
cost-basis supplement when one is available for that same security --
matched on the acquired date *and* the security itself, not the date alone,
since two different employers' stock plans could coincidentally vest on the
same day. The security match is the supplement issuer's own ticker/CUSIP
when the packet has one, or else every distinctive word of the supplement
issuer's name appearing in the lot's own description -- matching on a
single word two unrelated issuers happen to share (both named "... Systems
..."  or "... Group", for instance) is exactly the false match this
guards against. When the supplement states a smaller quantity than the
lot's own (a partial sale), the basis is prorated. A noncovered lot at zero
or blank basis with no matching supplement at all is a lead for a human to
chase, not something this check can confirm -- it's a possible
discrepancy, not an error. A lot whose "covered" flag can't be read as a
clear yes or no is also a possible discrepancy, not silently skipped as if
it were covered.
"""

from __future__ import annotations

import re
from decimal import Decimal

from proofline.checks.models import CheckResult, TaxEffect
from proofline.checks.money import parse_bool, parse_money
from proofline.packet import ExtractedValue, Packet
from proofline.provenance.claim_identity import lot_1099b

CHECK_ID = "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE"
CHECK_VERSION = 3

_GENERIC_WORDS = {
    # Corporate suffixes.
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "llc",
    "ltd",
    "limited",
    # Descriptive words too common to tell one business from another --
    # sharing one of these alone is not evidence of a match.
    "systems",
    "technologies",
    "group",
    "holdings",
    "international",
    "global",
    "capital",
    "partners",
    "services",
    "solutions",
}
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(name: str) -> set[str]:
    """Lowercase words from a name, with a trailing parenthetical (e.g.
    "(RSU)") dropped."""
    without_parens = _PARENTHETICAL_RE.sub("", name)
    return set(_WORD_RE.findall(without_parens.lower()))


def _distinctive_words(name: str) -> list[str]:
    """The leading run of a name's words, stopping at the first corporate
    suffix or generic/descriptive word -- "Corvane Systems equity plan
    administrator" becomes ["corvane"], not a scattered set that keeps
    "equity"/"plan"/"administrator" while dropping "systems". This is what
    actually identifies one business, usable to check a lot's own
    description for it without hardcoding any name."""
    without_parens = _PARENTHETICAL_RE.sub("", name)
    words = _WORD_RE.findall(without_parens.lower())
    distinctive: list[str] = []
    for word in words:
        if word in _GENERIC_WORDS:
            break
        distinctive.append(word)
    return distinctive


def _matches_by_name(description: str, issuer: str) -> bool:
    distinctive = _distinctive_words(issuer)
    if not distinctive:
        return False
    description_words = _words(description)
    return all(word in description_words for word in distinctive)


def _security_id(fields: dict[str, ExtractedValue]) -> str | None:
    """A ticker or CUSIP, when the packet's extraction gives one -- an
    unambiguous identifier that doesn't depend on word-matching a printed
    name at all."""
    for field_name in ("ticker", "cusip"):
        value = fields.get(field_name)
        if value is not None and value.value:
            return str(value.value).strip().upper()
    return None


def _lot_fields(
    packet: Packet, line_key: str, sources: list[str]
) -> dict[str, ExtractedValue]:
    """Every extracted value for this lot's prefix on its source document --
    not just the ones the line's own `sources` lists, since a line only
    lists the fields its rule actually used to compute the line's value
    (proceeds and basis), not descriptive fields like term, covered,
    description or quantity."""
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


def _sibling_field(
    packet: Packet, document_id: str, field: str
) -> ExtractedValue | None:
    return next(
        (
            other
            for other in packet.extracted_values
            if other.document_id == document_id and other.field == field
        ),
        None,
    )


def _supplement_lots(packet: Packet) -> list[dict]:
    """Every lot on a stock-plan supplement document: its adjusted basis,
    acquired date, the supplement document's issuer, and -- when the
    supplement happens to state one -- the lot's own quantity (used to
    prorate a partial sale; most supplements don't carry this field, in
    which case the basis applies in full)."""
    lots: list[dict] = []
    for value in packet.extracted_values:
        if not value.field.endswith("_adjusted_basis"):
            continue
        document = packet.document(value.document_id)
        if document.document_type != "stock_plan_supplement":
            continue
        prefix = value.field[: -len("_adjusted_basis")]

        acquired = _sibling_field(packet, value.document_id, f"{prefix}_acquired")
        if acquired is None:
            continue
        quantity_ev = _sibling_field(packet, value.document_id, f"{prefix}_quantity")
        lot_fields = {
            field_name: sibling
            for field_name in ("ticker", "cusip")
            if (
                sibling := _sibling_field(
                    packet, value.document_id, f"{prefix}_{field_name}"
                )
            )
            is not None
        }

        lots.append(
            {
                "basis_ev": value,
                "basis": parse_money(value.value),
                "acquired_ev": acquired,
                "acquired": str(acquired.value),
                "issuer": document.issuer,
                "quantity": parse_money(quantity_ev.value)
                if quantity_ev is not None
                else None,
                "security_id": _security_id(lot_fields),
            }
        )
    return lots


def _matching_supplement_lot(
    supplement_lots: list[dict],
    description: str,
    acquired_date: str,
    security_id: str | None,
) -> dict | None:
    for lot in supplement_lots:
        if lot["acquired"] != acquired_date:
            continue
        if security_id is not None and lot["security_id"] is not None:
            if security_id == lot["security_id"]:
                return lot
            continue
        if _matches_by_name(description, lot["issuer"]):
            return lot
    return None


def run(packet: Packet) -> list[CheckResult]:
    current = packet.return_versions[-1]
    rates = current.tax_effect_rates
    supplement_lots = _supplement_lots(packet)

    matched_lots: list[dict] = []
    possible_findings: list[CheckResult] = []

    for line in current.lines:
        if line.form != "F8949":
            continue
        fields = _lot_fields(packet, line.key, line.sources)
        if "basis" not in fields or "covered" not in fields or "acquired" not in fields:
            continue

        lot_id = line.key.split(".")[-1]
        issuer = packet.document(fields["basis"].document_id).issuer

        covered = parse_bool(fields["covered"].value)
        if covered is True:
            continue
        if covered is None:
            possible_findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="investments",
                    scope="transaction",
                    finding_type="possible_discrepancy",
                    severity="tax_amount",
                    evidence_refs=[fields["covered"].id],
                    claims=[lot_1099b(issuer, lot_id)],
                    observed=(
                        f"Lot {lot_id} ({line.key})'s covered/noncovered flag "
                        f"({fields['covered'].value!r}) couldn't be read as a clear "
                        "yes or no."
                    ),
                    expected=(
                        "A lot's covered status should be a clear yes or no before "
                        "this check can decide whether a missing basis applies to it."
                    ),
                    tax_effect=None,
                    impact_unknown=True,
                    limitations=(
                        "The covered/noncovered value wasn't recognized as a boolean, "
                        "a 0/1, or yes/no text, so it was neither treated as covered "
                        "nor as noncovered."
                    ),
                    recommended_action=(
                        f"Confirm whether lot {lot_id} ({line.key}) is covered or "
                        "noncovered before filing."
                    ),
                )
            )
            continue

        basis = parse_money(fields["basis"].value)
        if basis is not None and basis != 0:
            continue

        acquired_date = str(fields["acquired"].value)
        description = fields.get("description")
        security_id = _security_id(fields)

        supplement = None
        if description is not None:
            supplement = _matching_supplement_lot(
                supplement_lots, str(description.value), acquired_date, security_id
            )

        evidence_refs = [fields["basis"].id, fields["acquired"].id]
        if description is not None:
            evidence_refs.append(description.id)

        if supplement is None:
            possible_findings.append(
                CheckResult(
                    check_id=CHECK_ID,
                    check_version=CHECK_VERSION,
                    area="investments",
                    scope="transaction",
                    finding_type="possible_discrepancy",
                    severity="tax_amount",
                    evidence_refs=sorted(set(evidence_refs)),
                    claims=[lot_1099b(issuer, lot_id)],
                    observed=(
                        f"Noncovered lot {lot_id} ({line.key}) reports basis "
                        f"{'blank' if basis is None else '0.00'}, with no stock plan "
                        "supplement on file matching it by security and acquisition date."
                    ),
                    expected=(
                        "A noncovered lot's basis should be supported by the issuing "
                        "employer's own cost-basis records when available."
                    ),
                    tax_effect=None,
                    impact_unknown=True,
                    limitations=(
                        "No stock plan supplement on file matches this lot; the correct "
                        "basis, if any, is unknown."
                    ),
                    recommended_action=(
                        f"Ask the client whether lot {lot_id} ({line.key}) has an "
                        "employer-issued cost-basis supplement, or confirm the basis is "
                        "genuinely zero, before filing."
                    ),
                )
            )
            continue

        supplement_basis = supplement["basis"]
        lot_quantity_ev = fields.get("quantity")
        if (
            lot_quantity_ev is not None
            and supplement["quantity"] is not None
            and supplement["quantity"] > 0
        ):
            lot_quantity = parse_money(lot_quantity_ev.value)
            if lot_quantity is not None and lot_quantity < supplement["quantity"]:
                supplement_basis = (
                    supplement_basis * lot_quantity / supplement["quantity"]
                )

        evidence_refs.append(supplement["basis_ev"].id)
        evidence_refs.append(supplement["acquired_ev"].id)

        term = str(fields["term"].value) if "term" in fields else None
        rate_key = "stcg" if term == "short" else "ltcg"

        matched_lots.append(
            {
                "line_key": line.key,
                "lot_id": lot_id,
                "issuer": issuer,
                "basis_change": supplement_basis,
                "rate": rates.get(rate_key),
                "evidence": evidence_refs,
            }
        )

    if not matched_lots:
        return possible_findings

    federal_total = Decimal(0)
    california_total = Decimal(0)
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

    error_finding = CheckResult(
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
            "for each, matched to the lot by security and acquisition date."
        ),
        expected=(
            "A noncovered RSU lot's basis should use the issuing employer's own "
            "cost-basis records when available, not 0."
        ),
        tax_effect=TaxEffect(
            federal=federal_total.quantize(Decimal("0.01")),
            california=california_total.quantize(Decimal("0.01")),
            kind="estimate",
            direction="overstated",
        ),
        impact_unknown=False,
        limitations=(
            "Estimated from tax_effect_rates, not a recomputation of the engine; assumes "
            "the supplement's basis applies in full unless the supplement states a "
            "smaller quantity than the lot sold."
        ),
        recommended_action=(
            "Apply each lot's adjusted cost basis from the employer's stock plan "
            "supplement and correct Form 8949 before filing."
        ),
    )

    return [error_finding, *possible_findings]
