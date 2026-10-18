import json
from decimal import Decimal
from pathlib import Path

from proofline.checks.rsu_lot_zero_basis_supplement_available import run
from proofline.packet import ExtractedValue, Line, load_packet
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


def test_noncovered_zero_basis_lot_with_no_supplement_is_not_flagged() -> None:
    """A noncovered, zero-basis lot with no matching stock plan supplement
    on file is a lead for a human to chase, not something this check can
    confirm -- it should stay silent rather than guess."""
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
        value=Decimal("100"),
        rule="R-8949-LOT",
        sources=["ev-0001", "ev-0002", "ev-0003", "ev-0004"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(extracted_values=extracted_values, return_versions=[rv])

    assert run(packet) == []


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
        value=Decimal("100"),
        rule="R-8949-LOT",
        sources=["ev-0001", "ev-0002", "ev-0003", "ev-0004"],
    )
    rv = minimal_return_version(lines=[line])
    packet = minimal_packet(extracted_values=extracted_values, return_versions=[rv])

    assert run(packet) == []
