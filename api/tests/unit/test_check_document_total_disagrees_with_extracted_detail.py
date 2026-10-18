import json
from pathlib import Path

from proofline.checks.document_total_disagrees_with_extracted_detail import run
from proofline.packet import Document, Extraction, ExtractedValue, load_packet
from tests.unit.factories import minimal_packet, minimal_return_version

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "DOCUMENT_TOTAL_DISAGREES_WITH_EXTRACTED_DETAIL.json"
)


def test_real_packet_matches_fixture() -> None:
    packet = load_packet()
    findings = run(packet)

    actual = [f.model_dump(mode="json") for f in findings]
    expected = json.loads(_FIXTURE_PATH.read_text())

    assert actual == expected


def test_partial_document_with_matching_total_is_not_flagged() -> None:
    document = Document(
        id="D01",
        title="Test brokerage statement",
        document_type="1099-composite",
        issuer="Test Broker",
        page_count=2,
        extraction=Extraction(status="partial", values=2, reason="page 2 not read"),
    )
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="b_summary_proceeds",
            label="summary total proceeds",
            value=100.0,
            value_type="money",
            confidence=0.99,
        ),
        ExtractedValue(
            id="ev-0002",
            document_id="D01",
            page=1,
            field="M1_proceeds",
            value=100.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    rv = minimal_return_version(documents_used=["D01"])
    packet = minimal_packet(
        documents=[document], extracted_values=extracted_values, return_versions=[rv]
    )

    assert run(packet) == []


def test_superseded_document_not_in_documents_used_is_skipped() -> None:
    """A superseded document isn't flagged even if its own numbers
    disagree -- it's not what feeds the current return."""
    document = Document(
        id="D01",
        title="Test brokerage statement (superseded)",
        document_type="1099-composite",
        issuer="Test Broker",
        page_count=2,
        extraction=Extraction(status="partial", values=2, reason="page 2 not read"),
    )
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="b_summary_proceeds",
            label="summary total proceeds",
            value=250.0,
            value_type="money",
            confidence=0.99,
        ),
        ExtractedValue(
            id="ev-0002",
            document_id="D01",
            page=1,
            field="M1_proceeds",
            value=100.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    rv = minimal_return_version(documents_used=[], documents_superseded=["D01"])
    packet = minimal_packet(
        documents=[document], extracted_values=extracted_values, return_versions=[rv]
    )

    assert run(packet) == []
