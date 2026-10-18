import json
from pathlib import Path

from proofline.checks.third_party_processor_income_double_counted import run
from proofline.packet import Document, Extraction, ExtractedValue, Line, load_packet
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
