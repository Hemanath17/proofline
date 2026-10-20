"""Langfuse tracing for one investigator run, over OpenTelemetry (Langfuse's
Python SDK is OTel-native from v3 on). Debugging only -- it is explicitly
NOT the audit record. The audit record is the `ai_suggestion_recorded`/
`ai_suggestion_reviewed` events in Postgres (`proofline.ai.events`); losing
every Langfuse trace ever sent would not lose anything this app depends on
for correctness or compliance.

Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from the
environment. If either key is unset, or the Langfuse client fails to
start or send for any reason, tracing no-ops cleanly -- it must never
crash or hang the investigator (CLAUDE.md: "Code must degrade gracefully
with all of them unset").
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Iterator
from typing import Any

from proofline.packet import load_packet
from proofline.security.actors import Actor
from proofline.security.redact import redact_for_actor

logger = logging.getLogger(__name__)


def _client() -> Any | None:
    if not (
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    ):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.environ.get("LANGFUSE_HOST"),
        )
    except Exception:
        logger.warning("Langfuse client unavailable; tracing disabled", exc_info=True)
        return None


@contextlib.contextmanager
def trace_investigation(
    *, actor: Actor, case_id: str, model_name: str, prompt_version: int
) -> Iterator[dict[str, Any]]:
    """Yields a mutable dict the caller fills in as the run progresses
    (`tool_calls`, `summary`, `confidence`, `validation`); everything in
    it is redacted through `redact_for_actor` -- the same path document and
    claim reads already use -- before being sent to Langfuse."""
    client = _client()
    started = time.monotonic()
    record: dict[str, Any] = {"tool_calls": [], "error": None}
    try:
        yield record
    except Exception as exc:
        record["error"] = str(exc)
        raise
    finally:
        if client is not None:
            _send(client, actor, case_id, model_name, prompt_version, started, record)


def _send(
    client: Any,
    actor: Actor,
    case_id: str,
    model_name: str,
    prompt_version: int,
    started: float,
    record: dict[str, Any],
) -> None:
    try:
        packet = load_packet()
        latency_ms = (time.monotonic() - started) * 1000
        span = client.start_observation(
            name="evidence_investigator.investigate",
            as_type="agent",
            input=redact_for_actor(actor, packet, {"case_id": case_id}),
            model=model_name,
            version=str(prompt_version),
        )
        span.update(
            output=redact_for_actor(
                actor,
                packet,
                {
                    "tool_calls": record.get("tool_calls"),
                    "summary": record.get("summary"),
                    "confidence": record.get("confidence"),
                    "validation": record.get("validation"),
                    "error": record.get("error"),
                },
            ),
            metadata={"latency_ms": latency_ms},
        )
        span.end()
        client.flush()
    except Exception:
        logger.warning("Langfuse span failed to send; ignored", exc_info=True)
