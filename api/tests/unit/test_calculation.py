"""C3: workpaper_value's engine/exact/adjusted labeling, proven against
the real packet's RSU scenario (docs/ACCEPTANCE.md A1): once N1 and N3's
basis is corrected, Schedule D line 2 should read -480, labelled exact,
carried from F8949.B.total's R-SUM of the two adjusted lots.
"""

from datetime import UTC, datetime
from decimal import Decimal

from proofline.analysis.calculation import (
    adjustments_by_claim,
    line_claim_identity,
    workpaper_value,
)
from proofline.db.models import Adjustment
from proofline.packet import load_packet
from proofline.provenance.claim_identity import lot_1099b


def _adjustment(claim_key: str, new_value: str) -> Adjustment:
    # created_at only gets its `server_default` on an actual INSERT; these
    # objects are never persisted, so it's set explicitly here, the same
    # way `actions/cases.py` always passes `created_at=when` for a real one.
    return Adjustment(
        id=f"adjustment-test-{claim_key}",
        claim_key=claim_key,
        old_value="0",
        new_value=new_value,
        evidence_refs=[],
        created_at=datetime.now(UTC),
    )


def test_line_claim_identity_maps_f8949_lot_lines() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    claim = line_claim_identity(packet, rv.line("F8949.B.N1"))
    assert claim == lot_1099b("Northlake Securities", "N1")


def test_line_claim_identity_is_none_for_non_8949_lines() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    assert line_claim_identity(packet, rv.line("F1040.1a")) is None


def test_workpaper_value_with_no_adjustments_is_the_engine_value() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    result = workpaper_value(packet, rv, "SchD.2", {})
    assert result.value == 37720
    assert result.label == "engine v3"


def test_workpaper_value_adjusted_leaf_and_exact_carry_to_sched_d() -> None:
    """The A1 scenario: N1's gain becomes 140 (19,240 proceeds - 19,100
    corrected basis) and N3's becomes -620 (18,480 - 19,100). F8949.B.total
    (R-SUM) becomes 140 + -620 = -480, and SchD.2 (R-CARRY from it) carries
    that -480 through exactly."""
    packet = load_packet()
    rv = packet.return_version("v3")
    adjustments = adjustments_by_claim(
        [
            _adjustment(str(lot_1099b("Northlake Securities", "N1")), "140"),
            _adjustment(str(lot_1099b("Northlake Securities", "N3")), "-620"),
        ]
    )

    n1 = workpaper_value(packet, rv, "F8949.B.N1", adjustments)
    assert n1.label == "adjusted"
    assert n1.value == Decimal(140)

    total = workpaper_value(packet, rv, "F8949.B.total", adjustments)
    assert total.label == "exact"
    assert total.value == Decimal(-480)

    sched_d = workpaper_value(packet, rv, "SchD.2", adjustments)
    assert sched_d.label == "exact"
    assert sched_d.value == Decimal(-480)


def test_workpaper_value_unrelated_line_is_unaffected_by_other_adjustments() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    adjustments = adjustments_by_claim(
        [_adjustment(str(lot_1099b("Northlake Securities", "N1")), "140")]
    )
    result = workpaper_value(packet, rv, "F1040.1a", adjustments)
    assert result.label == "engine v3"
