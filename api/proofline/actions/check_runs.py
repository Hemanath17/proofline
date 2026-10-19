"""Recording a check-run snapshot: a point-in-time record of what the
checks found, kept forever even if the checks' logic changes later
(docs/DECISIONS.md: "check runs saved at each decision"). No case workflow
exists yet to attach this to a real decision, so Step 4 exposes it as its
own action; Step 5's case transitions will reuse `_findings_payload` below
when they need to snapshot a check run alongside their own event.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from proofline.actions.errors import ActionValidationError
from proofline.actions.results import ActionResult
from proofline.checks.models import CheckFailure, CheckResult
from proofline.checks.runner import run_all_checks
from proofline.db.canonical import prepare_payload_for_storage
from proofline.db.models import CheckRun
from proofline.db.repository import insert_check_run, insert_event
from proofline.packet import Packet
from proofline.security.actors import Actor
from proofline.security.permissions import check_permission


def _findings_payload(findings: list[CheckResult]) -> list[dict]:
    return [prepare_payload_for_storage(f.model_dump(mode="json")) for f in findings]


def _failures_payload(failures: list[CheckFailure]) -> list[dict]:
    return [f.model_dump(mode="json") for f in failures]


def record_check_run(
    session: Session,
    actor: Actor,
    *,
    entity_id: str | None,
    expected_revision: int | None,
    payload: dict[str, Any],
    occurred_at: datetime | None,
    packet: Packet | None = None,
) -> ActionResult:
    check_permission(actor, "record_check_run")
    if packet is None:
        raise ActionValidationError("record_check_run needs the packet")
    when = occurred_at or datetime.now(UTC)
    run_result = run_all_checks(packet)
    return_version = packet.return_versions[-1].version
    findings_payload = _findings_payload(run_result.findings)
    failures_payload = _failures_payload(run_result.failures)
    run_id = f"check_run-{uuid.uuid4()}"
    event = insert_event(
        session,
        "check_run_recorded",
        {
            "return_version": return_version,
            "findings": findings_payload,
            "failures": failures_payload,
        },
        actor_id=actor.id,
        entity_type="check_run",
        entity_id=run_id,
        revision=None,
        occurred_at=when,
    )
    check_run = CheckRun(
        id=run_id,
        event_id=event.id,
        return_version=return_version,
        findings=findings_payload,
        failures=failures_payload,
    )
    insert_check_run(session, check_run)
    return ActionResult(event=event, current_state=check_run)
