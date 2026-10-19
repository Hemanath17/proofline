"""C2/S3 tie-outs: a computed line's own engine v3 value against its
current workpaper value, proven against the real packet's A1 scenario
(N1/N3's corrected basis changes Schedule D line 2 from 37,720 to -480).
"""

from datetime import UTC, datetime
from decimal import Decimal

from proofline.analysis.calculation import adjustments_by_claim
from proofline.analysis.tie_outs import scope_tie_outs
from proofline.db.models import Adjustment
from proofline.packet import load_packet
from proofline.provenance.claim_identity import lot_1099b


def _adjustment(claim_key: str, new_value: str) -> Adjustment:
    return Adjustment(
        id=f"adjustment-test-{claim_key}",
        claim_key=claim_key,
        old_value="0",
        new_value=new_value,
        evidence_refs=[],
        created_at=datetime.now(UTC),
    )


def test_tie_outs_balance_with_no_adjustments() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    tie_outs = scope_tie_outs(packet, rv, "investments", {})
    assert tie_outs
    assert all(t.ok for t in tie_outs)
    assert all(t.difference == 0 for t in tie_outs)


def test_tie_out_breaks_once_the_rsu_adjustment_is_approved() -> None:
    packet = load_packet()
    rv = packet.return_version("v3")
    adjustments = adjustments_by_claim(
        [
            _adjustment(str(lot_1099b("Northlake Securities", "N1")), "140"),
            _adjustment(str(lot_1099b("Northlake Securities", "N3")), "-620"),
        ]
    )
    tie_outs = scope_tie_outs(packet, rv, "investments", adjustments)
    by_line = {t.line_key: t for t in tie_outs}

    sched_d = by_line["SchD.2"]
    assert sched_d.ok is False
    assert sched_d.engine_value == 37720
    assert sched_d.workpaper_value == Decimal(-480)
    assert sched_d.difference == Decimal(-480) - Decimal(37720)

    total = by_line["F8949.B.total"]
    assert total.ok is False
