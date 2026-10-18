import json
from decimal import Decimal
from pathlib import Path

from proofline.checks.third_party_processor_income_double_counted import run
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
    / "THIRD_PARTY_PROCESSOR_INCOME_DOUBLE_COUNTED.json"
)


def test_real_packet_matches_fixture() -> None:
    packet = load_packet()
    findings = run(packet)

    actual = [f.model_dump(mode="json") for f in findings]
    expected = json.loads(_FIXTURE_PATH.read_text())

    assert actual == expected


def _document(document_id: str, document_type: str, issuer: str) -> Document:
    return Document(
        id=document_id,
        title="Test document",
        document_type=document_type,
        issuer=issuer,
        page_count=1,
        extraction=Extraction(status="extracted", values=0),
    )


def test_no_overlapping_processor_detail_is_not_flagged() -> None:
    """A books total plus a 1099-K with no matching processor mention in
    the books' own transaction detail isn't something this check can
    confirm as double-counted."""
    documents = [
        _document("D01", "books_profit_loss", "Test Business"),
        _document("D02", "1099-K", "SomeProcessor Inc."),
        _document("D03", "books_transaction_detail", "Test Business"),
    ]
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="total_income",
            value=50000.0,
            value_type="money",
            confidence=0.99,
        ),
        ExtractedValue(
            id="ev-0002",
            document_id="D02",
            page=1,
            field="box1a",
            value=5000.0,
            value_type="money",
            confidence=0.99,
        ),
        ExtractedValue(
            id="ev-0003",
            document_id="D03",
            page=1,
            field="unrelated_deposit",
            label="Deposits unrelated to any processor",
            value=1000.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    line = Line(
        key="SchC.1",
        jurisdiction="federal",
        form="SchC",
        line="1",
        label="Gross receipts",
        value=55000,
        rule="R-SUM",
        sources=["ev-0001", "ev-0002"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    assert run(packet) == []


def _ev(
    document_id: str, field: str, value, index: int, label: str | None = None
) -> ExtractedValue:
    return ExtractedValue(
        id=f"ev-{index:04d}",
        document_id=document_id,
        page=1,
        field=field,
        label=label,
        value=value,
        value_type="money",
        confidence=0.99,
    )


def test_matching_on_the_full_issuer_name_avoids_a_generic_first_word() -> None:
    """The 1099-K issuer's first word alone ("Pay") is too generic to match
    on safely -- it would also match an unrelated "Payroll liabilities" books
    row. Matching on the full normalized issuer name ("pay falcon") finds
    only the row that actually names the processor."""
    documents = [
        _document("D01", "books_profit_loss", "Test Business"),
        _document("D02", "1099-K", "Pay Falcon, Inc."),
        _document("D03", "books_transaction_detail", "Test Business"),
    ]
    extracted_values = [
        _ev("D01", "total_income", 50000.0, 1),
        _ev("D02", "box1a", 5000.0, 2),
        _ev("D03", "payroll", 9999.0, 3, label="Payroll liabilities"),
        _ev(
            "D03",
            "paywell_deposit",
            5000.0,
            4,
            label="Deposits via Pay Falcon processor",
        ),
    ]
    line = Line(
        key="SchC.1",
        jurisdiction="federal",
        form="SchC",
        line="1",
        label="Gross receipts",
        value=55000,
        rule="R-SUM",
        sources=["ev-0001", "ev-0002"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run(packet)

    assert len(findings) == 1
    assert "ev-0003" not in findings[0].evidence_refs
    assert "ev-0004" in findings[0].evidence_refs


def test_sums_all_matching_books_rows() -> None:
    """Two books rows both naming the processor should be summed, not just
    the first one found."""
    documents = [
        _document("D01", "books_profit_loss", "Test Business"),
        _document("D02", "1099-K", "Paywell Payments, Inc."),
        _document("D03", "books_transaction_detail", "Test Business"),
    ]
    extracted_values = [
        _ev("D01", "total_income", 50000.0, 1),
        _ev("D02", "box1a", 10000.0, 2),
        _ev("D03", "batch_1", 3000.0, 3, label="Paywell batch 1"),
        _ev("D03", "batch_2", 2000.0, 4, label="Paywell batch 2"),
    ]
    line = Line(
        key="SchC.1",
        jurisdiction="federal",
        form="SchC",
        line="1",
        label="Gross receipts",
        value=60000,
        rule="R-SUM",
        sources=["ev-0001", "ev-0002"],
    )
    rv = minimal_return_version(
        lines=[line],
        tax_effect_rates={
            "schc_profit": TaxEffectRate(
                federal_per_dollar=Decimal("0.30"),
                california_per_dollar=Decimal("0.10"),
            )
        },
    )
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run(packet)

    assert len(findings) == 1
    # Summed overlap is 3000 + 2000 = 5000, under the 1099-K's 10000, so the
    # cap doesn't bind here.
    assert findings[0].tax_effect.federal == Decimal("1500.00")
    assert findings[0].tax_effect.california == Decimal("500.00")
    assert set(findings[0].evidence_refs) >= {"ev-0003", "ev-0004"}


def test_caps_the_double_count_at_the_1099k_amount() -> None:
    """The books' own overlap total can exceed the 1099-K's reported amount
    (if the 1099-K covers only part of what the books recorded for that
    processor) -- the double count can never be more than the 1099-K
    itself."""
    documents = [
        _document("D01", "books_profit_loss", "Test Business"),
        _document("D02", "1099-K", "Paywell Payments, Inc."),
        _document("D03", "books_transaction_detail", "Test Business"),
    ]
    extracted_values = [
        _ev("D01", "total_income", 50000.0, 1),
        _ev("D02", "box1a", 5000.0, 2),
        _ev("D03", "batch_1", 5000.0, 3, label="Paywell batch 1"),
        _ev("D03", "batch_2", 3000.0, 4, label="Paywell batch 2"),
    ]
    line = Line(
        key="SchC.1",
        jurisdiction="federal",
        form="SchC",
        line="1",
        label="Gross receipts",
        value=55000,
        rule="R-SUM",
        sources=["ev-0001", "ev-0002"],
    )
    rv = minimal_return_version(
        lines=[line],
        tax_effect_rates={
            "schc_profit": TaxEffectRate(
                federal_per_dollar=Decimal("0.30"),
                california_per_dollar=Decimal("0.10"),
            )
        },
    )
    packet = minimal_packet(
        documents=documents, extracted_values=extracted_values, return_versions=[rv]
    )

    findings = run(packet)

    assert len(findings) == 1
    # Books overlap is 5000 + 3000 = 8000, but the 1099-K itself is only
    # 5000, so the double count is capped at 5000.
    assert findings[0].tax_effect.federal == Decimal("1500.00")
    assert findings[0].tax_effect.california == Decimal("500.00")
