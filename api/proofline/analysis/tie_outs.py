"""C2/S3 tie-outs: "totals that must agree, each check or cross with the
difference" (docs/UX.md S3). CLAUDE.md: "Engine runs v1, v2 and v3 never
change... we never present the result as a recomputed return" -- so a
tie-out is not the workpaper value agreeing with itself (it always would,
by construction); it's the engine's own v3 total for a computed line
(R-SUM/R-CARRY) against the current workpaper value once approved
adjustments are overlaid (docs/CONTRACTS.md C3). A difference here is
exactly what an approved adjustment changed, surfaced rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from proofline.analysis.calculation import workpaper_value
from proofline.analysis.signoff import scope_lines
from proofline.checks.money import parse_money
from proofline.db.models import Adjustment
from proofline.packet import Packet, ReturnVersion


@dataclass(frozen=True)
class TieOut:
    line_key: str
    label: str | None
    engine_value: object
    workpaper_value: object
    ok: bool
    difference: Decimal


def scope_tie_outs(
    packet: Packet,
    rv: ReturnVersion,
    scope: str,
    adjustments: dict[str, Adjustment],
) -> list[TieOut]:
    tie_outs: list[TieOut] = []
    for line in scope_lines(rv, scope):
        if line.rule not in ("R-SUM", "R-CARRY") or not line.inputs:
            continue
        try:
            engine_value = parse_money(line.value)
            workpaper = workpaper_value(packet, rv, line.key, adjustments)
            wp_value = parse_money(workpaper.value)
        except ValueError:
            continue
        if engine_value is None or wp_value is None:
            continue
        tie_outs.append(
            TieOut(
                line_key=line.key,
                label=line.label,
                engine_value=line.value,
                workpaper_value=workpaper.value,
                ok=engine_value == wp_value,
                difference=wp_value - engine_value,
            )
        )
    return tie_outs
