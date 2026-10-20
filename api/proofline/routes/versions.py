"""B15, B16: comparing versions, and the packet's five what-ifs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from proofline.analysis.calculation import adjustments_by_claim, workpaper_value
from proofline.analysis.version_diff import Version, diff_versions
from proofline.db.connection import get_session
from proofline.db.repository import list_adjustments
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()

_VERSIONS = ("v1", "v2", "v3", "workpaper")


def _require_version(value: str) -> Version:
    if value not in _VERSIONS:
        raise HTTPException(
            status_code=422, detail=f"version must be one of {_VERSIONS}"
        )
    return value  # type: ignore[return-value]


@router.get("/versions/diff")
def get_version_diff(
    from_: str = Query(alias="from"),
    to: str = Query(default="workpaper"),
    only_changed: bool = Query(default=False),
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    from_version = _require_version(from_)
    to_version = _require_version(to)
    diffs = diff_versions(packet, session, from_version, to_version)
    if only_changed:
        diffs = [d for d in diffs if d.changed]
    body = {
        "from": from_version,
        "to": to_version,
        "lines": [
            {
                "line_key": d.line_key,
                "label": d.label,
                "rule": d.rule,
                "old_value": d.old_value,
                "new_value": d.new_value,
                "changed": d.changed,
                "source": d.source,
            }
            for d in diffs
        ],
    }
    return redact_for_actor(actor, packet, body)


@router.get("/what-ifs")
def get_what_ifs(
    actor: Actor = Depends(require_non_client),
    session: Session = Depends(get_session),
) -> dict:
    """C3/B16: the packet's five named what-ifs, each an exact engine
    result already in the packet, alongside the current workpaper value
    for the same changed lines -- nothing else is computed as a what-if."""
    packet = load_packet()
    rv = packet.return_versions[-1]
    adjustments = adjustments_by_claim(list_adjustments(session))
    alternatives = []
    for alternative in packet.what_if.alternatives:
        changed_lines = []
        for changed in alternative.changed_lines:
            try:
                current = workpaper_value(packet, rv, changed.key, adjustments)
                current_value = current.value
            except KeyError:
                current_value = None
            changed_lines.append(
                {
                    "line_key": changed.key,
                    "change": changed.change,
                    "what_if_old": changed.old,
                    "what_if_new": changed.new,
                    "current_workpaper_value": current_value,
                }
            )
        alternatives.append(
            {
                "id": alternative.id,
                "description": alternative.description,
                "base_version": alternative.base_version,
                "choices": alternative.choices,
                "federal": alternative.federal,
                "california": alternative.california,
                "changed_lines": changed_lines,
            }
        )
    body = {"alternatives": alternatives}
    return redact_for_actor(actor, packet, body)
