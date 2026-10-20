"""The Evidence Investigator: one Pydantic AI agent, served through Groq,
that reads a case's own evidence and proposes -- never decides -- a
resolution for it. Runs strictly on demand, triggered only by
`POST /api/cases/{case_id}/investigate` (`proofline/routes/ai.py`); it
never runs on a schedule or in the background, and it never calls
`submit_proposal` itself -- only a human, through the ordinary action
service, turns an accepted suggestion into a real proposal (CLAUDE.md).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.usage import UsageLimits
from sqlalchemy.orm import Session

from proofline.ai import tools as ai_tools
from proofline.ai.schema import InvestigatorSuggestion
from proofline.packet import load_packet
from proofline.security.actors import AI_ASSISTANT_ID, Actor, load_actors

PROMPT_VERSION = 1
DEFAULT_MODEL_NAME = "openai/gpt-oss-120b"
DEFAULT_MAX_TOOL_CALLS = 12
DEFAULT_MAX_TOTAL_TOKENS = 20_000

_SYSTEM_PROMPT = """You are the Evidence Investigator for a CPA firm's tax workpaper.

You investigate exactly one case at a time, using these tools:
- open_case: the case's own status, claims and evidence_refs, plus its proposals and decisions.
- trace_claim: traces one claim/line/document identity in both directions.
- read_evidence: a document's own masked text and fields.
- find_related_documents: find documents by exact id or full-text search.

You may only read. You never write, approve, close, sign off, or file
anything -- that is enforced outside of you, but you should not act as if
you could anyway.

Rules you must follow:
- Start by calling open_case on the case you were asked to investigate.
- Cite only claim ids and document ids that belong to THIS case -- its own
  `claims` and the documents behind its own `evidence_refs`. Citing
  something you merely found elsewhere in the packet, even if it is real
  and even if it looks related, is a failure, not thoroughness.
- Every number in `numbers_cited` must be a number you actually read in
  the evidence you cite -- never a number you computed, estimated, or
  inferred.
- `proposed_resolution_type` must be one of the four existing resolution
  types, whichever actually matches what the evidence shows.
- A client's own statement (a qa-, msg- or call- reference) is not
  independent verification on its own -- it can support a
  `record_judgment` or the chosen side of a `resolve_evidence_conflict`,
  never settle a question by itself.
- If the evidence does not clearly support a conclusion, set `confidence`
  to "uncertain" rather than overstating it.
"""


class InvestigatorConfigError(Exception):
    """Raised when the investigator can't run at all -- e.g. no
    GROQ_API_KEY. There is no fallback model; this is caught by the route
    and turned into a clear error, never a hang."""


def is_enabled() -> bool:
    """CLAUDE.md / docs/PLAN.md Step 10: "the feature stays off until it
    passes its evaluation in api/eval/ and beats the plain checks... if it
    doesn't ship it off and say so." Defaults to false regardless of
    whether GROQ_API_KEY happens to be set -- a human flips this only
    after `api/eval`'s golden-set run actually clears the bar (see
    docs/DECISIONS.md for the current state)."""
    return os.environ.get("AI_INVESTIGATOR_ENABLED", "false").strip().lower() == "true"


@dataclass
class InvestigatorDeps:
    actor: Actor
    session: Session


@dataclass
class InvestigatorRun:
    suggestion: InvestigatorSuggestion
    model_name: str
    tool_calls: list[dict[str, Any]]
    latency_ms: float
    error: str | None = None


def usage_limits() -> UsageLimits:
    return UsageLimits(
        tool_calls_limit=int(
            os.environ.get("AI_INVESTIGATOR_MAX_TOOL_CALLS", DEFAULT_MAX_TOOL_CALLS)
        ),
        total_tokens_limit=int(
            os.environ.get("AI_INVESTIGATOR_MAX_TOTAL_TOKENS", DEFAULT_MAX_TOTAL_TOKENS)
        ),
    )


def model_name() -> str:
    return os.environ.get("AI_INVESTIGATOR_MODEL", DEFAULT_MODEL_NAME)


def _build_model() -> GroqModel:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise InvestigatorConfigError(
            "GROQ_API_KEY is not set -- the Evidence Investigator has no fallback "
            "model and will not run without it"
        )
    return GroqModel(model_name(), provider=GroqProvider(api_key=api_key))


def build_agent() -> Agent[InvestigatorDeps, InvestigatorSuggestion]:
    agent: Agent[InvestigatorDeps, InvestigatorSuggestion] = Agent(
        _build_model(),
        output_type=InvestigatorSuggestion,
        deps_type=InvestigatorDeps,
        system_prompt=_SYSTEM_PROMPT,
    )

    @agent.tool
    def open_case(ctx: RunContext[InvestigatorDeps], case_id: str) -> dict:
        """Read the case under investigation: status, claims, evidence_refs,
        proposals and decisions."""
        return ai_tools.open_case(ctx.deps.actor, ctx.deps.session, case_id)

    @agent.tool
    def trace_claim(ctx: RunContext[InvestigatorDeps], claim_id: str) -> dict:
        """Trace one claim, line or document identity in both directions:
        its inputs, what uses it, and the documents behind it."""
        return ai_tools.trace_claim(ctx.deps.actor, ctx.deps.session, claim_id)

    @agent.tool
    def read_evidence(
        ctx: RunContext[InvestigatorDeps],
        document_id: str | None = None,
        claim_id: str | None = None,
    ) -> dict:
        """Read a document's own masked text and fields, by document id or
        by a claim/evidence ref that resolves to one."""
        return ai_tools.read_evidence(
            ctx.deps.actor,
            ctx.deps.session,
            document_id=document_id,
            claim_id=claim_id,
        )

    @agent.tool
    def find_related_documents(ctx: RunContext[InvestigatorDeps], query: str) -> dict:
        """Find documents by exact id or full-text search."""
        return ai_tools.find_related_documents(ctx.deps.actor, ctx.deps.session, query)

    return agent


def _tool_calls_made(result: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in result.all_messages():
        if isinstance(message, ModelResponse):
            for call in message.tool_calls:
                calls.append({"name": call.tool_name, "args": call.args_as_dict()})
    return calls


def investigate_case(session: Session, case_id: str) -> InvestigatorRun:
    """Runs one investigation of `case_id`, as the `ai-assistant` actor.
    Raises `InvestigatorConfigError` if GROQ_API_KEY isn't set; otherwise
    returns the raw (not-yet-validated) suggestion plus run metadata for
    the audit event and the Langfuse trace."""
    actor = load_actors(load_packet())[AI_ASSISTANT_ID]
    deps = InvestigatorDeps(actor=actor, session=session)
    agent = build_agent()
    prompt = (
        f"Investigate case {case_id}. Call open_case first, then follow its own "
        "claims and evidence_refs with trace_claim/read_evidence before writing "
        "your summary."
    )
    started = time.monotonic()
    result = agent.run_sync(prompt, deps=deps, usage_limits=usage_limits())
    latency_ms = (time.monotonic() - started) * 1000
    return InvestigatorRun(
        suggestion=result.output,
        model_name=model_name(),
        tool_calls=_tool_calls_made(result),
        latency_ms=latency_ms,
    )
