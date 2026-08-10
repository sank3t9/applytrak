"""Smoke test the Gemini provider: structured parse + embedding, no database needed.

Verifies GEMINI_API_KEY works and that both halves of the demo stack respond:
structured output (parse) and 1024-dim embeddings.

Run (bash / Git Bash):
    LLM_PROVIDER=gemini EMBEDDING_PROVIDER=gemini REDIS_URL= \\
        uv run python scripts/gemini_smoke.py

Run (PowerShell):
    $env:LLM_PROVIDER="gemini"; $env:EMBEDDING_PROVIDER="gemini"; $env:REDIS_URL=""
    uv run python scripts/gemini_smoke.py

REDIS_URL is blanked so the rate limiter stays in-process — this test needs no
services at all.
"""

import sys

from applytrak.config import settings

SAMPLE_JD = """Acme Robotics | Senior Backend Engineer | Remote (US) | $160k-$190k

We're a 30-person Series A robotics company. Looking for someone with 5+ years
building Python services at scale. You'll own our fleet telemetry pipeline.

Required: Python, PostgreSQL, AWS, Kubernetes
Nice to have: Rust, gRPC, time-series databases
"""


BASH_CMD = (
    "LLM_PROVIDER=gemini EMBEDDING_PROVIDER=gemini REDIS_URL= uv run python scripts/gemini_smoke.py"
)


def main() -> int:
    if not settings.gemini_api_key:
        print(
            "[FAIL] GEMINI_API_KEY is not set. Get a free key at "
            "https://aistudio.google.com/app/apikey",
            file=sys.stderr,
        )
        return 1

    # Fail fast rather than silently exercising a different provider.
    wrong = []
    if settings.llm_provider != "gemini":
        wrong.append(f"LLM_PROVIDER={settings.llm_provider!r} (want 'gemini')")
    if settings.embedding_provider != "gemini":
        wrong.append(f"EMBEDDING_PROVIDER={settings.embedding_provider!r} (want 'gemini')")
    if wrong:
        print(f"[FAIL] wrong configuration: {'; '.join(wrong)}", file=sys.stderr)
        print(f"\nRun it as:\n    {BASH_CMD}", file=sys.stderr)
        return 1

    print(f"Parse model:     {settings.gemini_model_parse}")
    print(f"Score model:     {settings.gemini_model_score}")
    print(f"Embedding model: {settings.gemini_embedding_model}")

    print("\n=== Structured output (parse) ===")
    from applytrak.llm.parse_prompt import PARSE_PROMPT
    from applytrak.llm.providers import generate_structured
    from applytrak.schemas import ParsedJD

    parsed = generate_structured(
        task="parse",
        user=PARSE_PROMPT.format(raw_text=SAMPLE_JD),
        schema=ParsedJD,
    )
    print(f"[OK] {parsed.company} | {parsed.title}")
    print(f"     yoe={parsed.yoe_min}-{parsed.yoe_max} remote={parsed.is_remote}")
    print(f"     location={parsed.location!r}")
    print(f"     must_have={parsed.must_have_skills}")
    print(f"     comp={parsed.comp_min}-{parsed.comp_max} {parsed.comp_currency}")
    print(f"     confidence={parsed.parse_confidence}")

    print("\n=== Embeddings ===")
    from applytrak.llm.embeddings import EMBEDDING_DIM, current_embedding_model, embed_text

    doc_vec = embed_text(SAMPLE_JD, input_type="document")
    query_vec = embed_text("Backend engineer, Python and AWS, 5 years", input_type="query")
    magnitude = sum(v * v for v in doc_vec) ** 0.5
    similarity = sum(a * b for a, b in zip(doc_vec, query_vec, strict=True))

    print(f"[OK] tag={current_embedding_model()}")
    print(f"     dim={len(doc_vec)} (expected {EMBEDDING_DIM})")
    print(f"     magnitude={magnitude:.6f} (expected ~1.0 after normalization)")
    print(f"     cosine(jd, related query)={similarity:.4f}")

    if len(doc_vec) != EMBEDDING_DIM:
        print(f"[FAIL] expected {EMBEDDING_DIM} dims, got {len(doc_vec)}", file=sys.stderr)
        return 1
    if abs(magnitude - 1.0) > 0.01:
        print(f"[FAIL] vector not normalized (magnitude={magnitude})", file=sys.stderr)
        return 1

    print("\n[OK] Gemini provider is working end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
