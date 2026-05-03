"""Anthropic client singleton with optional LangSmith tracing.

Usage:
    from applytrak.llm.client import client
    response = client.messages.create(model=..., messages=[...])

When LANGSMITH_API_KEY is set in .env, the client is wrapped with
`langsmith.wrappers.wrap_anthropic` so every call is auto-traced
to the LangSmith dashboard. When unset, the plain Anthropic client
is used (no tracing, no error).
"""

import os

from anthropic import Anthropic
from langsmith.wrappers import wrap_anthropic

from applytrak.config import settings

if settings.langsmith_api_key:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

_anthropic = Anthropic(api_key=settings.anthropic_api_key)

client = wrap_anthropic(_anthropic) if settings.langsmith_api_key else _anthropic
