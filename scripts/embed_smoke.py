"""Smoke test: embed two short strings, check dimensions and similarity.

Run:
    python scripts/embed_smoke.py
"""

import math
import sys

from applytrak.llm.embeddings import embed_texts


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b)


def main() -> int:
    similar = "Senior backend engineer at fintech startup, Python and AWS"
    different = "Mosquito-control biotech engineer working on hardware automation"

    print("Embedding two test strings...")
    embeddings = embed_texts([similar, different])

    print(f"\nDimensions: {len(embeddings[0])}")
    print(f"L2 norm[0]: {math.sqrt(sum(x*x for x in embeddings[0])):.4f}  (should be ~1.0)")
    print(f"First 5 values[0]: {embeddings[0][:5]}")

    sim = cosine_similarity(embeddings[0], embeddings[1])
    print(f"\nCosine similarity (different topics): {sim:.4f}  (should be ~0.3-0.6)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
