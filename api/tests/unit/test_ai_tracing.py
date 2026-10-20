"""Part 3: Langfuse tracing must no-op cleanly whenever its keys aren't
set -- it is debugging only, never something the investigator depends on
to run (CLAUDE.md)."""

from __future__ import annotations

import pytest
from proofline.ai import tracing
from proofline.security.actors import AI_ASSISTANT_ID, Actor

AI_ACTOR = Actor(
    id=AI_ASSISTANT_ID, name="AI assistant", role="ai_assistant", clearance=False
)


@pytest.fixture(autouse=True)
def _no_langfuse_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)


def test_no_keys_means_no_client() -> None:
    assert tracing._client() is None


def test_trace_investigation_no_ops_without_keys() -> None:
    with tracing.trace_investigation(
        actor=AI_ACTOR, case_id="case-1", model_name="m", prompt_version=1
    ) as record:
        record["tool_calls"] = [{"name": "open_case", "args": {}}]
        record["summary"] = "x"
    # No exception, nothing sent -- that's the whole point.


def test_trace_investigation_still_propagates_the_real_error() -> None:
    with pytest.raises(ValueError, match="boom"), tracing.trace_investigation(
        actor=AI_ACTOR, case_id="case-1", model_name="m", prompt_version=1
    ):
        raise ValueError("boom")


def test_a_broken_langfuse_client_still_no_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")

    class _ExplodingClient:
        def start_observation(self, **kwargs):
            raise RuntimeError("network is down")

    monkeypatch.setattr(tracing, "_client", lambda: _ExplodingClient())
    with tracing.trace_investigation(
        actor=AI_ACTOR, case_id="case-1", model_name="m", prompt_version=1
    ) as record:
        record["summary"] = "x"
    # Still no exception -- a Langfuse failure must never crash the investigator.
