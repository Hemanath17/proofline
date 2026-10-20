"""B15: diff any two of v1, v2, v3, or the current workpaper version.
Generalizes `analysis/signoff.py`'s fingerprint/document-comparison shape
(Step 7's "changes since the last sign-off") to any pair instead of only
"the last sign-off vs. now" -- the same underlying question (what changed,
by which rule, engine or adjustment), asked more broadly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.db.repository import list_adjustments
from proofline.packet import Packet

Version = Literal["v1", "v2", "v3", "workpaper"]


@dataclass(frozen=True)
class LineDiff:
    line_key: str
    label: str | None
    rule: str | None
    old_value: Any
    new_value: Any
    changed: bool
    source: str  # "engine" | "adjustment" | "n/a" (line doesn't exist on one side)


def _rv_for(packet: Packet, version: Version):
    return (
        packet.return_versions[-1]
        if version == "workpaper"
        else packet.return_version(version)
    )


def _label_for(
    packet: Packet, from_version: Version, to_version: Version, line_key: str
) -> str | None:
    for version in (to_version, from_version):
        try:
            return _rv_for(packet, version).line(line_key).label
        except KeyError:
            continue
    return None


def _value_label_rule(
    packet: Packet, session: Session, version: Version, line_key: str
) -> tuple[Any, str, str | None]:
    """Returns (value, source, rule) for `line_key` at `version`, or
    (None, "n/a", None) if the line doesn't exist at that version."""
    if version == "workpaper":
        rv = packet.return_versions[-1]
        try:
            rv.line(line_key)
        except KeyError:
            return None, "n/a", None
        adjustments = adjustments_by_claim(list_adjustments(session))
        result = workpaper_value(packet, rv, line_key, adjustments)
        source = "adjustment" if result.label == "adjusted" else "engine"
        return result.value, source, rv.line(line_key).rule
    rv = packet.return_version(version)
    try:
        line = rv.line(line_key)
    except KeyError:
        return None, "n/a", None
    return line.value, "engine", line.rule


def diff_versions(
    packet: Packet, session: Session, from_version: Version, to_version: Version
) -> list[LineDiff]:
    from_keys = {line.key for line in _rv_for(packet, from_version).lines}
    to_keys = {line.key for line in _rv_for(packet, to_version).lines}
    all_line_keys = sorted(from_keys | to_keys)

    diffs = []
    for line_key in all_line_keys:
        old_value, old_source, old_rule = _value_label_rule(
            packet, session, from_version, line_key
        )
        new_value, new_source, new_rule = _value_label_rule(
            packet, session, to_version, line_key
        )
        diffs.append(
            LineDiff(
                line_key=line_key,
                label=_label_for(packet, from_version, to_version, line_key),
                rule=new_rule or old_rule,
                old_value=old_value,
                new_value=new_value,
                changed=old_value != new_value,
                source=new_source if new_source != "n/a" else old_source,
            )
        )
    return diffs
