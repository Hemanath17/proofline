import json
from decimal import Decimal
from pathlib import Path

from proofline.checks.rsu_lot_zero_basis_supplement_available import run
from proofline.packet import (
    Document,
    ExtractedValue,
    Extraction,
    Line,
    TaxEffectRate,
    load_packet,
)

from tests.unit.factories import minimal_packet, minimal_return_version

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE.json"
)


def test_real_packet_matches_fixture() -> None:
    packet = load_packet()
    findings = run(packet)

    actual = [f.model_dump(mode="json") for f in findings]
    expected = json.loads(_FIXTURE_PATH.read_text())

    assert actual == expected


def _ev(
    document_id: str, field: str, value, value_type: str, index: int
) -> ExtractedValue:
    return ExtractedValue(
        id=f"ev-{index:04d}",
        document_id=document_id,
        page=1,
        field=field,
        value=value,
        value_type=value_type,
        confidence=0.99,
    )


def _supplement_document(document_id: str, issuer: str) -> Document:
    return Document(
        id=document_id,
        title="Stock plan supplement",
        document_type="stock_plan_supplement",
        issuer=issuer,
        page_count=1,
        extraction=Extraction(status="extracted", values=0),
    )


def _brokerage_document(document_id: str = "D99") -> Document:
    return Document(
        id=document_id,
        title="Brokerage 1099-B",
        document_type="1099-composite",
        issuer="Some Broker",
        page_count=1,
        extraction=Extraction(status="extracted", values=0),
    )


def test_noncovered_zero_basis_lot_with_no_supplement_is_a_possible_discrepancy() -> (
    None
):
    """A noncovered, zero-basis lot with no matching stock plan supplement
    on file is a lead for a human to chase -- it should be raised as a
    possible_discrepancy, not an error, and not silently dropped either."""
    extracted_values = [
        _ev("D99", "X1_acquired", "2025-01-01", "date", 1),
        _ev("D99", "X1_basis", 0.0, "money", 2),
        _ev("D99", "X1_covered", False, "boolean", 3),
        _ev("D99", "X1_term", "short", "code", 4),
    ]
    line = Line(
        key="F8949.A.X1",
        jurisdiction="federal",
        form="F8949",
        line="A.X1",
        label="Some Broker (acquired 2025-01-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0001", "ev-0002", "ev-0003", "ev-0004"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(
        documents=[_brokerage_document()],
        extracted_values=extracted_values,
        return_versions=[rv],
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "possible_discrepancy"
    assert findings[0].check_id == "RSU_LOT_ZERO_BASIS_SUPPLEMENT_AVAILABLE"


def test_covered_zero_basis_lot_is_not_flagged() -> None:
    """Basis 0 on a *covered* lot isn't the gap this check is about."""
    extracted_values = [
        _ev("D99", "X1_acquired", "2025-01-01", "date", 1),
        _ev("D99", "X1_basis", 0.0, "money", 2),
        _ev("D99", "X1_covered", True, "boolean", 3),
        _ev("D99", "X1_term", "short", "code", 4),
    ]
    line = Line(
        key="F8949.A.X1",
        jurisdiction="federal",
        form="F8949",
        line="A.X1",
        label="Some Broker (acquired 2025-01-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0001", "ev-0002", "ev-0003", "ev-0004"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(extracted_values=extracted_values, return_versions=[rv])

    assert run(packet) == []


def test_blank_basis_is_treated_the_same_as_zero() -> None:
    """A blank (None) basis on a noncovered lot should be treated the same
    as a printed 0.00 -- both are "no basis on file", not "not applicable"."""
    extracted_values = [
        _ev("D99", "X1_description", "Acme Corp (RSU)", "text", 1),
        _ev("D99", "X1_acquired", "2025-01-01", "date", 2),
        _ev("D99", "X1_basis", None, "money", 3),
        _ev("D99", "X1_covered", False, "boolean", 4),
        _ev("D99", "X1_term", "short", "code", 5),
    ]
    line = Line(
        key="F8949.A.X1",
        jurisdiction="federal",
        form="F8949",
        line="A.X1",
        label="Some Broker (acquired 2025-01-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0001", "ev-0002", "ev-0003", "ev-0004", "ev-0005"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(
        documents=[_brokerage_document()],
        extracted_values=extracted_values,
        return_versions=[rv],
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "possible_discrepancy"
    assert "blank" in findings[0].observed


def test_coincidental_date_match_across_different_employers_does_not_fire() -> None:
    """A supplement lot that happens to vest on the same date as an
    unrelated lot from a different employer must not be matched just
    because the dates agree -- the security/issuer has to agree too."""
    documents = [
        _supplement_document("D11", "Acme Corp equity plan administrator"),
        _brokerage_document(),
    ]
    extracted_values = [
        _ev("D11", "RSU-1_adjusted_basis", 5000.0, "money", 1),
        _ev("D11", "RSU-1_acquired", "2025-01-01", "date", 2),
        _ev("D99", "X1_description", "Zenith Systems Inc (RSU)", "text", 3),
        _ev("D99", "X1_acquired", "2025-01-01", "date", 4),
        _ev("D99", "X1_basis", 0.0, "money", 5),
        _ev("D99", "X1_covered", False, "boolean", 6),
        _ev("D99", "X1_term", "short", "code", 7),
    ]
    line = Line(
        key="F8949.A.X1",
        jurisdiction="federal",
        form="F8949",
        line="A.X1",
        label="Some Broker (acquired 2025-01-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0003", "ev-0004", "ev-0005", "ev-0006", "ev-0007"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run(packet)

    assert len(findings) == 1
    assert findings[0].finding_type == "possible_discrepancy"
    assert "ev-0001" not in findings[0].evidence_refs
    assert "ev-0002" not in findings[0].evidence_refs


def test_partial_sale_prorates_the_supplement_basis() -> None:
    """When the supplement states a quantity larger than the lot's own
    (sold), the basis is prorated to the fraction actually sold."""
    documents = [
        _supplement_document("D11", "Acme Corp equity plan administrator"),
        _brokerage_document(),
    ]
    extracted_values = [
        _ev("D11", "RSU-1_adjusted_basis", 10000.0, "money", 1),
        _ev("D11", "RSU-1_acquired", "2025-03-01", "date", 2),
        _ev("D11", "RSU-1_quantity", 200.0, "money", 3),
        _ev("D99", "X1_description", "Acme Corp (RSU)", "text", 4),
        _ev("D99", "X1_acquired", "2025-03-01", "date", 5),
        _ev("D99", "X1_quantity", 50.0, "money", 6),
        _ev("D99", "X1_basis", 0.0, "money", 7),
        _ev("D99", "X1_covered", False, "boolean", 8),
        _ev("D99", "X1_term", "long", "code", 9),
    ]
    line = Line(
        key="F8949.E.X1",
        jurisdiction="federal",
        form="F8949",
        line="E.X1",
        label="Some Broker (acquired 2025-03-01)",
        value=Decimal(100),
        rule="R-8949-LOT",
        sources=["ev-0004", "ev-0005", "ev-0006", "ev-0007", "ev-0008", "ev-0009"],
    )
    rv = minimal_return_version(
        lines=[line],
        tax_effect_rates={
            "ltcg": TaxEffectRate(
                federal_per_dollar=Decimal("0.20"),
                california_per_dollar=Decimal("0.05"),
            )
        },
    )
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run(packet)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "error"
    # Prorated basis: 10000 * (50 / 200) = 2500.
    assert finding.tax_effect.federal == Decimal("500.00")
    assert finding.tax_effect.california == Decimal("125.00")
    assert finding.tax_effect.direction == "overstated"
