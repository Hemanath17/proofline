from decimal import Decimal

from proofline.packet import Document, Extraction, ExtractedValue, Line, load_packet
from proofline.provenance.tracing import (
    dependency_graph,
    dependents_of,
    trace_document,
    trace_line,
)
from tests.unit.factories import minimal_packet, minimal_return_version


def test_trace_f1040_1a_finds_d08_and_d09_with_d10_excluded() -> None:
    """The Step 2 'Done when': tracing F1040.1a returns D08 and D09, with
    D10 marked as excluded (the generic duplicate signal), not as a third
    source."""
    packet = load_packet()
    trace = trace_line(packet, "F1040.1a")

    assert trace.primary_sources == frozenset({"D08", "D09"})

    excluded_ids = {excluded.document_id for excluded in trace.excluded}
    assert excluded_ids == {"D10"}
    assert "Halvorsen" in trace.note


def test_trace_document_d10_reports_unused() -> None:
    packet = load_packet()
    trace = trace_document(packet, "D10")

    assert trace.used is False
    assert trace.lines_using == ()
    assert trace.note is not None and "contributes to no line" in trace.note


def test_trace_document_d08_reports_the_line_it_feeds() -> None:
    packet = load_packet()
    trace = trace_document(packet, "D08")

    assert trace.used is True
    assert "F1040.1a" in trace.lines_using


def test_dependency_graph_and_dependents_are_inverses() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")

    graph = dependency_graph(rv)
    assert "F1040.1a" in graph["F1040.1z"]

    assert "F1040.1z" in dependents_of(rv, "F1040.1a")


def test_trace_line_with_asset_sourced_entirely_from_prior_years_is_empty_not_an_error() -> (
    None
):
    """F4562-E.total-A sources two assets whose own `sources` are a py:/
    pointer into prior_years, not an ev- reference -- there's no document
    behind it in the current packet. The recursive asset lookup should
    come back empty, not raise."""
    packet = load_packet()
    trace = trace_line(packet, "F4562-E.total-A")

    assert trace.primary_sources == frozenset()
    assert trace.excluded == ()


def test_trace_line_recurses_through_an_asset_with_document_backed_sources() -> None:
    """When an asset's own sources *are* ev- refs, tracing a line that
    points at the asset should recurse through to the real document."""
    document = Document(
        id="D01",
        title="Test depreciation support",
        document_type="invoice",
        issuer="Test Vendor",
        page_count=1,
        extraction=Extraction(status="extracted", values=1),
    )
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="cost",
            value=1000.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    line = Line(
        key="F4562.total",
        jurisdiction="federal",
        form="F4562",
        line="total",
        label="Depreciation total",
        value=Decimal("100"),
        rule="R-DEPRECIATION-SCHEDULE",
        sources=["asset:TEST-ASSET"],
    )
    rv = minimal_return_version(
        lines=[line],
        assets=[{"asset_id": "TEST-ASSET", "sources": ["ev-0001"]}],
    )
    packet = minimal_packet(
        documents=[document], extracted_values=extracted_values, return_versions=[rv]
    )

    trace = trace_line(packet, "F4562.total")
    assert trace.primary_sources == frozenset({"D01"})
