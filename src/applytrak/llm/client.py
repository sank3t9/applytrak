"""Anthropic client accessor with optional LangSmith tracing.

Usage:
    from applytrak.llm.client import get_anthropic_client
    response = get_anthropic_client().messages.create(model=..., messages=[...])

Lazy-init: importing this module never constructs the client, so Gemini-only
deployments don't need ANTHROPIC_API_KEY at all. When LANGSMITH_API_KEY is set,
the client is wrapped with `langsmith.wrappers.wrap_anthropic` so every call
is auto-traced to the LangSmith dashboard.
"""

import os

from anthropic import Anthropic

from applytrak.config import settings

if settings.langsmith_api_key:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

_client: Anthropic | None = None


def get_anthropic_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set in .env. Set it, or switch to LLM_PROVIDER=gemini."
            )
        client = Anthropic(api_key=settings.anthropic_api_key)
        if settings.langsmith_api_key:
            from langsmith.wrappers import wrap_anthropic

            client = wrap_anthropic(client)
        _client = client
    return _client
