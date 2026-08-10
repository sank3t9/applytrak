"""Run the pipeline as a batch job. Entry point for the scheduled GitHub Action.

Default stages: fetch, parse, embed, dedup. Scoring and the digest are opt-in
because they need a seeded profile row (the public demo scores per visitor at
request time instead).

Run:
    python scripts/run_pipeline.py                      # demo pipeline
    python scripts/run_pipeline.py --with-score         # + score against profile.yaml
    python scripts/run_pipeline.py --with-score --with-digest   # personal full run
    python scripts/run_pipeline.py --fetch-limit 60

Exits non-zero if a stage attempted work and every attempt failed, so a broken
API key or schema surfaces as a red workflow run instead of a silent no-op.
"""

import argparse
import logging
import sys

from applytrak.config import settings
from applytrak.pipeline import (
    DEFAULT_FETCH_LIMIT,
    run_dedup,
    run_digest,
    run_embed,
    run_fetch,
    run_parse,
    run_score,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fetch-limit",
        type=int,
        default=DEFAULT_FETCH_LIMIT,
        help=f"Max HN comments to fetch this run (default: {DEFAULT_FETCH_LIMIT}).",
    )
    parser.add_argument(
        "--with-score",
        action="store_true",
        help="Also score postings against the seeded profile row.",
    )
    parser.add_argument(
        "--with-digest",
        action="store_true",
        help="Also build and send the Telegram digest (implies --with-score).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # One line per HTTP call and an "AFC is enabled" notice per request drowns out
    # the pipeline's own progress; warnings from these still get through.
    for noisy in ("httpx", "google_genai.models", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    print(f"provider={settings.llm_provider} embeddings={settings.embedding_provider}")
    print(f"redis={'yes' if settings.redis_url else 'no (postgres cache + local limiter)'}")

    failures: list[str] = []

    def record(stage: str, result) -> None:
        data = result.model_dump()
        print(f"\n=== {stage} ===")
        print(result.model_dump_json(indent=2))
        failed = data.get("failed", 0)
        succeeded = data.get("inserted", 0) + data.get("embedded", 0) + data.get("skipped", 0)
        if failed and not succeeded:
            failures.append(f"{stage}: all {failed} attempt(s) failed")

    record("fetch", run_fetch(limit=args.fetch_limit))
    record("parse", run_parse())
    record("embed", run_embed())
    record("dedup", run_dedup())

    if args.with_score or args.with_digest:
        record("score", run_score())
    if args.with_digest:
        result = run_digest()
        print("\n=== digest ===")
        print(result.model_dump_json(indent=2))
        if result.delivery_status == "failed":
            failures.append("digest: delivery failed")

    if failures:
        print("\n[FAIL] " + "; ".join(failures), file=sys.stderr)
        return 1

    print("\n[OK] pipeline run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
