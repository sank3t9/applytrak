"""Provider-agnostic structured-output LLM calls.

One entry point:

    generate_structured(task=..., user=..., schema=SomeModel) -> SomeModel

The active provider comes from LLM_PROVIDER:
  - anthropic → forced tool use; the schema becomes the tool's input schema.
    A provided system block is sent with prompt caching (it's stable across a
    batch, so subsequent calls within the TTL read the prefix at reduced cost).
  - gemini    → native structured output (response_schema on a Pydantic class);
    thinking disabled to keep latency and free-tier token budgets predictable.

Both paths rate-limit through acquire_rate_limit under a per-provider key.
"""

import logging
from typing import Literal, TypeVar

from pydantic import BaseModel

from applytrak.config import settings
from applytrak.rate_limit import acquire_rate_limit

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

Task = Literal["parse", "score"]


def generate_structured(
    *,
    task: Task,
    user: str,
    schema: type[T],
    system: str | None = None,
    max_tokens: int = 2048,
    tool_name: str = "record_output",
) -> T:
    """Run one structured-output call on the active provider.

    `task` picks the configured model tier ("parse" → cheap/fast, "score" →
    higher quality). `tool_name` only affects the Anthropic path.

    Raises pydantic.ValidationError on malformed model output and ValueError
    when the model returns no structured payload at all.
    """
    if settings.llm_provider == "gemini":
        return _gemini_structured(
            task=task, user=user, schema=schema, system=system, max_tokens=max_tokens
        )
    return _anthropic_structured(
        task=task,
        user=user,
        schema=schema,
        system=system,
        max_tokens=max_tokens,
        tool_name=tool_name,
    )


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


def _anthropic_structured(
    *,
    task: Task,
    user: str,
    schema: type[T],
    system: str | None,
    max_tokens: int,
    tool_name: str,
) -> T:
    from applytrak.llm.client import get_anthropic_client

    model = settings.anthropic_model_parse if task == "parse" else settings.anthropic_model_score

    kwargs: dict = {}
    if system is not None:
        kwargs["system"] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    with acquire_rate_limit("anthropic", max_per_minute=settings.anthropic_rpm):
        response = get_anthropic_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            tools=[
                {
                    "name": tool_name,
                    "description": f"Record the structured {schema.__name__} output.",
                    "input_schema": schema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
            **kwargs,
        )

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return schema(**block.input)

    raise ValueError(f"Model did not call {tool_name!r} tool. Response: {response.content!r}")


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

_gemini_client = None


def get_gemini_client():
    """Lazy-init the Gemini client so importing this module never needs a key."""
    global _gemini_client
    if _gemini_client is None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set in .env. "
                "Get a free key at https://aistudio.google.com/app/apikey"
            )
        from google import genai

        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _gemini_structured(
    *,
    task: Task,
    user: str,
    schema: type[T],
    system: str | None,
    max_tokens: int,
) -> T:
    from google.genai import types as genai_types

    model = settings.gemini_model_parse if task == "parse" else settings.gemini_model_score

    config = genai_types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        response_schema=schema,
        # Extraction and rubric scoring don't benefit from extended thinking;
        # a 0 budget keeps latency and free-tier token spend predictable.
        thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
    )

    with acquire_rate_limit("gemini", max_per_minute=settings.gemini_rpm):
        response = get_gemini_client().models.generate_content(
            model=model,
            contents=user,
            config=config,
        )

    if not response.text:
        raise ValueError(f"Gemini returned no structured payload. Response: {response!r}")
    return schema.model_validate_json(response.text)
