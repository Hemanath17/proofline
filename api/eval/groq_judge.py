"""A DeepEval judge model backed by Groq -- the same provider the
investigator itself runs on (CLAUDE.md names only Groq and Langfuse as
Step 10's external services; there is no second provider key to manage).
Only constructed by `api/eval` tests that already skip cleanly when
GROQ_API_KEY isn't set.
"""

from __future__ import annotations

import os

from deepeval.models.base_model import DeepEvalBaseLLM

DEFAULT_JUDGE_MODEL = "llama-3.3-70b-versatile"


class GroqJudgeModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str = DEFAULT_JUDGE_MODEL) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set -- the judge model has no key")
        self._api_key = api_key
        super().__init__(model_name)

    def load_model(self) -> GroqJudgeModel:
        from groq import Groq

        self._client = Groq(api_key=self._api_key)
        return self

    def generate(self, prompt: str, *args, **kwargs) -> str:
        response = self._client.chat.completions.create(
            model=self.name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self.name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    def get_model_name(self) -> str:
        return self.name
