"""The CONTRACTS.md claim identity table, checked against the real packet
for the two cases that matter most: a corrected document that moves a lot
across boxes, and a lot whose fields are split across two documents."""

from proofline.packet import load_packet
from proofline.provenance import claim_identity as ci


def test_household_fact_key_format() -> None:
    assert ci.household_fact("ada", "ssn").key == "household:ada:ssn"


def test_depreciation_asset_key_matches_asset_ref_format() -> None:
    assert ci.depreciation_asset("SAC-BLDG").key == "asset:SAC-BLDG"


def test_return_total_key_is_the_bare_line_key() -> None:
    assert ci.return_total("F1040.1z").key == "F1040.1z"


def test_lot_1099b_requires_lot_id_or_full_fallback_tuple() -> None:
    import pytest

    with pytest.raises(ValueError):
        ci.lot_1099b("Some Broker")


def test_lot_1099b_fallback_tuple_when_no_lot_id() -> None:
    key = ci.lot_1099b(
        "Some Broker",
        security="XYZ",
        acquired="2025-01-01",
        sold="2025-06-01",
        quantity="10",
    ).key
    assert key == "1099b_lot:Some Broker:XYZ:2025-01-01:2025-06-01:10"


def test_w2_box_key_format() -> None:
    assert (
        ci.w2_box("12-3456789", "employee-1", 2025, "1").key
        == "w2_box:12-3456789:employee-1:2025:1"
    )


def test_digital_asset_lot_key_format() -> None:
    assert (
        ci.digital_asset_lot("Coinhaven", "C6").key == "digital_asset_lot:Coinhaven:C6"
    )


def test_form_amount_key_format() -> None:
    assert (
        ci.form_amount("Payer Inc.", "taxpayer", "1").key
        == "form_amount:Payer Inc.:taxpayer:1"
    )


def test_k1_item_key_format() -> None:
    assert (
        ci.k1_item("12-3456789", "partner-1", "2").key
        == "k1_item:12-3456789:partner-1:2"
    )


def test_rental_line_key_format() -> None:
    assert ci.rental_line("123 Main St", "3").key == "rental_line:123 Main St:3"


def test_carryover_key_format() -> None:
    assert (
        ci.carryover("minimum_tax_credit_from_2025_amt").key
        == "carryover:minimum_tax_credit_from_2025_amt"
    )


def test_corrected_document_keeps_lot_identity_across_a_box_move() -> None:
    """D30 -> D31 is a corrected Meridian Brokerage statement. The M14 lot
    moves from Form 8949 box A (v1) to box D (v2, v3), but it's the same
    issuer and the same lot id, so CONTRACTS.md says it's the same claim."""
    packet = load_packet()

    v1_line = packet.return_version("v1").line("F8949.A.M14")
    v3_line = packet.return_version("v3").line("F8949.D.M14")

    v1_issuer = packet.document(
        packet.extracted_value(v1_line.sources[0]).document_id
    ).issuer
    v3_issuer = packet.document(
        packet.extracted_value(v3_line.sources[0]).document_id
    ).issuer

    assert v1_issuer == v3_issuer == "Meridian Brokerage"
    assert ci.lot_1099b(v1_issuer, "M14") == ci.lot_1099b(v3_issuer, "M14")


def test_lot_split_across_two_documents_shares_one_identity() -> None:
    """Coinhaven's lot C1 gets asset/sold/proceeds from D34 (a 1099-DA) and
    acquired/basis from D35 (a transaction export) -- same issuer, same lot
    id, one claim, regardless of which document a given field came from."""
    packet = load_packet()
    line = packet.return_version("v3").line("F8949.K.C1")

    issuers = {
        packet.document(packet.extracted_value(ref).document_id).issuer
        for ref in line.sources
    }
    assert issuers == {"Coinhaven Exchange, Inc."}

    keys = {ci.lot_1099b(issuer, "C1") for issuer in issuers}
    assert len(keys) == 1
