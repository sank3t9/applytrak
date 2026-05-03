"""Smoke test: send a tiny message to Claude Haiku, print the response and token usage.

Run:
    python scripts/llm_smoke.py

If LANGSMITH_API_KEY is set, the call appears as a trace in your LangSmith
dashboard at https://smith.langchain.com under the project name from .env
(default: 'applytrak').
"""

import sys

from applytrak.config import settings
from applytrak.llm.client import client


def main() -> int:
    print(f"Model:    {settings.anthropic_model_parse}")
    if settings.langsmith_api_key:
        print(f"LangSmith: ENABLED (project={settings.langsmith_project})")
    else:
        print("LangSmith: DISABLED (set LANGSMITH_API_KEY in .env to enable tracing)")

    response = client.messages.create(
        model=settings.anthropic_model_parse,
        max_tokens=64,
        messages=[
            {"role": "user", "content": "Reply with exactly the three words: hello applytrak ok"}
        ],
    )

    text = response.content[0].text
    usage = response.usage

    print(f"\nResponse: {text!r}")
    print(f"Tokens:   in={usage.input_tokens} out={usage.output_tokens}")
    estimated_cost = (usage.input_tokens * 1.0 + usage.output_tokens * 5.0) / 1_000_000
    print(f"Cost:     ~${estimated_cost:.6f} (Haiku 4.5 pricing)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
