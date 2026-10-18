import time
from decimal import Decimal

from proofline.packet import Document, ExtractedValue, Extraction, Line, load_packet
from proofline.provenance.resolver import UnresolvedReferenceError
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


def test_trace_line_sourced_only_from_a_household_fact_is_not_empty() -> None:
    """F8812.4 sources only household:theo -- no ev- ref, so it previously
    traced to nothing (empty primary_sources, empty excluded). It should now
    show up as a resolved other_sources entry instead of vanishing."""
    packet = load_packet()
    trace = trace_line(packet, "F8812.4")

    assert trace.primary_sources == frozenset()
    other_refs = {other.ref: other.kind for other in trace.other_sources}
    assert other_refs == {"household:theo": "household_person"}


def test_trace_line_with_asset_sources_keeps_the_asset_refs_in_other_sources() -> None:
    """F4562-E.total-A's own sources are two asset: refs. Even though neither
    asset resolves to a document (their own sources are py:/ pointers), the
    asset refs themselves are kept as resolved other_sources, per asset:
    being one of the reference kinds tracing must not drop."""
    packet = load_packet()
    trace = trace_line(packet, "F4562-E.total-A")

    other_refs = {other.ref: other.kind for other in trace.other_sources}
    assert other_refs == {"asset:SAC-BLDG": "asset", "asset:SAC-ROOF": "asset"}


def test_trace_line_with_dangling_ev_ref_raises_unresolved_not_keyerror() -> None:
    line = Line(
        key="F1234.dangling",
        jurisdiction="federal",
        form="F1234",
        line="dangling",
        label="Dangling source",
        value=Decimal(0),
        rule="R-SUM",
        sources=["ev-9999"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(return_versions=[rv])

    try:
        trace_line(packet, "F1234.dangling")
    except UnresolvedReferenceError:
        pass
    else:
        raise AssertionError("expected UnresolvedReferenceError")


def test_a_dangling_ref_on_one_line_does_not_break_tracing_other_lines() -> None:
    """One dangling ref anywhere in a return version (e.g. a stray ev-9999
    added to some unrelated line) must not make every *other* line's trace
    fail too -- only that one line's own trace should raise. Before this
    fix, "documents used by any line" eagerly resolved every line's
    sources (to find excluded duplicates), so one bad ref there broke
    trace_line for the whole return version."""
    document = Document(
        id="D01",
        title="Test W-2",
        document_type="W-2",
        issuer="Test Employer",
        page_count=1,
        extraction=Extraction(status="extracted", values=1),
    )
    extracted_values = [
        ExtractedValue(
            id="ev-0001",
            document_id="D01",
            page=1,
            field="box1",
            value=1000.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    healthy_line = Line(
        key="F1040.1a",
        jurisdiction="federal",
        form="F1040",
        line="1a",
        label="Wages",
        value=Decimal(1000),
        rule="R-SUM",
        sources=["ev-0001"],
    )
    broken_line = Line(
        key="SchC.1",
        jurisdiction="federal",
        form="SchC",
        line="1",
        label="Gross receipts",
        value=Decimal(0),
        rule="R-SUM",
        sources=["ev-9999"],
    )
    rv = minimal_return_version(lines=[healthy_line, broken_line])
    packet = minimal_packet(
        documents=[document], extracted_values=extracted_values, return_versions=[rv]
    )

    # The healthy line's own trace must succeed even though a different
    # line in the same return version has a dangling ref.
    trace = trace_line(packet, "F1040.1a")
    assert trace.primary_sources == frozenset({"D01"})

    # The broken line's own trace must still raise, naming the bad ref.
    try:
        trace_line(packet, "SchC.1")
    except UnresolvedReferenceError as exc:
        assert "ev-9999" in str(exc)
    else:
        raise AssertionError("expected UnresolvedReferenceError")

    # trace_document has the same whole-return-version blast radius as
    # trace_line's "documents used by any line" sweep -- a dangling ref on
    # an unrelated line must not break tracing this unrelated document.
    document_trace = trace_document(packet, "D01")
    assert document_trace.used is True
    assert document_trace.lines_using == ("F1040.1a",)


def test_a_dangling_ref_does_not_discard_its_own_lines_other_good_refs() -> None:
    """A line with two sources, one dangling and one real, must not lose
    the real one from the whole-version sweeps -- only the bad ref is
    skipped, not the whole line's contribution."""
    document = Document(
        id="D02",
        title="Test 1099",
        document_type="1099-NEC",
        issuer="Test Payer",
        page_count=1,
        extraction=Extraction(status="extracted", values=1),
    )
    extracted_values = [
        ExtractedValue(
            id="ev-0002",
            document_id="D02",
            page=1,
            field="box1",
            value=500.0,
            value_type="money",
            confidence=0.99,
        ),
    ]
    mixed_line = Line(
        key="SchC.2",
        jurisdiction="federal",
        form="SchC",
        line="2",
        label="Other income",
        value=Decimal(500),
        rule="R-SUM",
        sources=["ev-0002", "ev-8888"],
    )
    other_line = Line(
        key="F1040.1a",
        jurisdiction="federal",
        form="F1040",
        line="1a",
        label="Wages",
        value=Decimal(0),
        rule="R-SUM",
        sources=[],
    )
    rv = minimal_return_version(lines=[mixed_line, other_line])
    packet = minimal_packet(
        documents=[document], extracted_values=extracted_values, return_versions=[rv]
    )

    # D02 is used by SchC.2's one real source, even though SchC.2 also has
    # a dangling one -- the sweep must still see it.
    document_trace = trace_document(packet, "D02")
    assert document_trace.used is True
    assert document_trace.lines_using == ("SchC.2",)


def test_tracing_all_lines_of_the_real_packet_is_fast() -> None:
    """The Step-2 "Done when" tracing is useful only if it's fast enough to
    run on every line. Before caching documents_used_by_any_line per return
    version, this took about 64s for 627 lines; the target is well under 1s."""
    packet = load_packet()
    rv = packet.return_version("v3")

    start = time.monotonic()
    for line in rv.lines:
        trace_line(packet, line.key)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"tracing all {len(rv.lines)} lines took {elapsed:.2f}s"


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
        value=Decimal(100),
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
