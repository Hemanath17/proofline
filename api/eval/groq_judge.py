"""A DeepEval judge model backed by Groq -- the same provider the
investigator itself runs on (CLAUDE.md names only Groq and Langfuse as
Step 10's external services; there is no second provider key to manage).
Only constructed by `api/eval` tests that already skip cleanly when
GROQ_API_KEY isn't set.
"""

from __future__ import annotations

import os

from deepeval.models.base_model import DeepEvalBaseLLM

DEFAULT_JUDGE_MODEL = "openai/gpt-oss-120b"
# Temporary, one-time escape hatch (docs/DECISIONS.md, 2026-10-20): the
# shipped default is Groq (CLAUDE.md). AI_INVESTIGATOR_PROVIDER=openai lets
# today's real eval run against OpenAI instead, because Groq's daily token
# budget was exhausted -- it is not a permanent dual-provider mechanism and
# should not be left set anywhere persistent. Same switch investigator.py
# reads for the model under test.
DEFAULT_OPENAI_JUDGE_MODEL = "gpt-5-nano"
# See investigator.py's GROQ_MAX_RETRIES: the groq SDK already retries
# 429/5xx with exponential backoff + jitter and respects a `Retry-After`
# header -- its default budget of 2 just isn't big enough when the eval
# suite's judge calls run back to back against the same per-minute token
# budget as the investigator's own calls.
GROQ_MAX_RETRIES = 5


def _provider() -> str:
    return os.environ.get("AI_INVESTIGATOR_PROVIDER", "groq").strip().lower()


class GroqJudgeModel(DeepEvalBaseLLM):
    """Despite the name, this also serves as the OpenAI-backed judge when
    AI_INVESTIGATOR_PROVIDER=openai -- renaming it was out of scope for a
    one-time, temporary substitution."""

    def __init__(self, model_name: str | None = None) -> None:
        self._using_openai = _provider() == "openai"
        if self._using_openai:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "AI_INVESTIGATOR_PROVIDER=openai but OPENAI_API_KEY is not set"
                )
            default_model = DEFAULT_OPENAI_JUDGE_MODEL
        else:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "GROQ_API_KEY is not set -- the judge model has no key"
                )
            default_model = DEFAULT_JUDGE_MODEL
        self._api_key = api_key
        super().__init__(model_name or default_model)

    def load_model(self) -> GroqJudgeModel:
        if self._using_openai:
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        else:
            from groq import Groq

            self._client = Groq(api_key=self._api_key, max_retries=GROQ_MAX_RETRIES)
        return self

    def _temperature_kwargs(self) -> dict:
        # gpt-5-nano (a reasoning model) rejects any explicit temperature
        # other than its default of 1 -- confirmed live, not assumed --
        # so only pin temperature=0 for Groq's (non-reasoning) judge model.
        return {} if self._using_openai else {"temperature": 0}

    def generate(self, prompt: str, *args, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.name,
            messages=[{"role": "user", "content": prompt}],
            **self._temperature_kwargs(),
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        if self._using_openai:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)
        else:
            from groq import AsyncGroq

            client = AsyncGroq(api_key=self._api_key, max_retries=GROQ_MAX_RETRIES)
        response = await client.chat.completions.create(
            model=self.name,
            messages=[{"role": "user", "content": prompt}],
            **self._temperature_kwargs(),
        )
        return response.choices[0].message.content or ""

    def get_model_name(self) -> str:
        return self.name
