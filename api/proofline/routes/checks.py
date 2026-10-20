from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from proofline.actions.service import perform
from proofline.checks.runner import run_all_checks
from proofline.db.connection import get_session
from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.dependencies import get_current_actor, require_non_client
from proofline.security.redact import redact_for_actor

router = APIRouter()


@router.get("/checks")
def get_checks(actor: Actor = Depends(require_non_client)) -> dict:
    """Live findings, run fresh against the current packet -- not a stored
    snapshot. `POST /api/check-runs` is what takes a snapshot."""
    packet = load_packet()
    run_result = run_all_checks(packet)
    body = {
        "findings": [
            finding.model_dump(mode="json") for finding in run_result.findings
        ],
        "failures": [
            failure.model_dump(mode="json") for failure in run_result.failures
        ],
    }
    return redact_for_actor(actor, packet, body)


@router.post("/check-runs")
def record_check_run(
    actor: Actor = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> dict:
    packet = load_packet()
    result = perform(session, actor, "record_check_run", packet=packet)
    return redact_for_actor(actor, packet, result.current_state.to_dict())
