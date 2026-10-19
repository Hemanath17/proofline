"""C3: the workpaper value of a line (docs/CONTRACTS.md C3).

- Engine value: v1/v2/v3 exactly as delivered -- never edited.
- Adjustment: an overlay on one claim.
- Workpaper value: engine v3 plus the approved adjustments.
- Exact: a change is only carried forward along R-SUM and R-CARRY lines,
  since those are plain sums and carries, so substituting an adjusted
  leaf's value and replaying the same sum/carry is still exactly correct.
- At the first rule that isn't R-SUM or R-CARRY, we stop rather than
  estimate here -- CONTRACTS.md calls for an estimate via
  `tax_effect_rates` at that point, but which rate category applies is
  itself check-specific knowledge (short-term vs long-term capital gain,
  ordinary income, ...) that doesn't generalize from the line alone.
  Nothing in Step 7's acceptance tests (A1, A2) needs a line past an
  R-SUM/R-CARRY chain to carry anything other than its still-unadjusted
  engine value, so that estimate path is left for whichever later step
  actually renders such a line (docs/DECISIONS.md has the full note).

The claim a line corresponds to is only known for Form 8949 lot lines
today (`_f8949_claim`) -- the same issuer+lot-id identity
`proofline.checks.rsu_lot_zero_basis_supplement_available` already uses,
rebuilt here rather than imported so this module never depends on one
check's internals. Extend `_LINE_CLAIM_RESOLVERS` as other domains need
adjustment support.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from proofline.checks.money import parse_money
from proofline.db.models import Adjustment
from proofline.packet import Line, Packet, ReturnVersion
from proofline.provenance.claim_identity import ClaimIdentity, lot_1099b

Label = str  # "engine" | "exact" | "adjusted"


@dataclass(frozen=True)
class ValueLabel:
    value: Any
    label: Label
    engine_version: str
    adjustment: Adjustment | None = None


def _f8949_claim(packet: Packet, line: Line) -> ClaimIdentity | None:
    if line.form != "F8949":
        return None
    lot_id = line.key.split(".")[-1]
    basis_value = next(
        (
            value
            for value in packet.extracted_values
            if value.field == f"{lot_id}_basis"
        ),
        None,
    )
    if basis_value is None:
        return None
    issuer = packet.document(basis_value.document_id).issuer
    if issuer is None:
        return None
    return lot_1099b(issuer, lot_id)


_LINE_CLAIM_RESOLVERS = (_f8949_claim,)


def line_claim_identity(packet: Packet, line: Line) -> ClaimIdentity | None:
    """Best-effort: which claim this line's value is about, if any domain
    this module knows how to map has an answer."""
    for resolver in _LINE_CLAIM_RESOLVERS:
        claim = resolver(packet, line)
        if claim is not None:
            return claim
    return None


def adjustments_by_claim(adjustments: list[Adjustment]) -> dict[str, Adjustment]:
    """The latest adjustment per claim (CONTRACTS.md: a claim's value is
    overlaid by its approved adjustment; if more than one were ever
    approved for the same claim, the most recent wins, matching how a
    sign-off's "values" fingerprint should read the claim today)."""
    latest: dict[str, Adjustment] = {}
    for adjustment in sorted(adjustments, key=lambda a: a.created_at):
        latest[adjustment.claim_key] = adjustment
    return latest


def workpaper_value(
    packet: Packet,
    rv: ReturnVersion,
    line_key: str,
    adjustments: dict[str, Adjustment],
    _memo: dict[str, ValueLabel] | None = None,
) -> ValueLabel:
    """The workpaper value of one line: engine v3 (or whichever version
    `rv` is) plus any approved adjustment, carried forward exactly along
    R-SUM/R-CARRY chains. `adjustments` is `adjustments_by_claim`'s output,
    computed once per request and threaded through the recursion so a
    line used by many lines is only resolved once per call (`_memo`).
    """
    memo = {} if _memo is None else _memo
    if line_key in memo:
        return memo[line_key]

    line = rv.line(line_key)
    engine_label = f"engine {rv.version}"

    claim = line_claim_identity(packet, line)
    if claim is not None and str(claim) in adjustments:
        adjustment = adjustments[str(claim)]
        result = ValueLabel(
            value=parse_money(adjustment.new_value),
            label="adjusted",
            engine_version=rv.version,
            adjustment=adjustment,
        )
        memo[line_key] = result
        return result

    if not line.inputs or line.rule not in ("R-SUM", "R-CARRY"):
        result = ValueLabel(
            value=line.value, label=engine_label, engine_version=rv.version
        )
        memo[line_key] = result
        return result

    input_results = [
        workpaper_value(packet, rv, input_key, adjustments, memo)
        for input_key in line.inputs
    ]
    any_changed = any(result.label in ("exact", "adjusted") for result in input_results)
    if not any_changed:
        result = ValueLabel(
            value=line.value, label=engine_label, engine_version=rv.version
        )
        memo[line_key] = result
        return result

    if line.rule == "R-SUM":
        total = sum(
            (parse_money(result.value) or Decimal(0)) for result in input_results
        )
        result = ValueLabel(value=total, label="exact", engine_version=rv.version)
    else:  # R-CARRY
        result = ValueLabel(
            value=input_results[0].value, label="exact", engine_version=rv.version
        )
    memo[line_key] = result
    return result
