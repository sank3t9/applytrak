"""Report the state of the posting corpus: what's ingested, parsed, embedded, deduped.

Answers "why does the site show N postings?" — the demo counts only canonical
(non-duplicate) postings, so that number is lower than the raw ingested count.
Also compares against the live thread to show how much is left to fetch.

Run:
    python scripts/corpus_stats.py
"""

import sys

import httpx
from sqlalchemy import func, select

from applytrak.db import session_scope
from applytrak.llm.embeddings import current_embedding_model
from applytrak.models import Posting, RawPosting, RelevanceScore
from applytrak.sources.hn import (
    SOURCE_NAME,
    get_latest_who_is_hiring_thread_id,
    get_top_level_comment_ids,
)


def main() -> int:
    tag = current_embedding_model()

    with session_scope() as session:
        raw_total = session.scalar(select(func.count(RawPosting.id))) or 0
        parsed_total = session.scalar(select(func.count(Posting.id))) or 0
        canonical = (
            session.scalar(select(func.count(Posting.id)).where(Posting.canonical_id.is_(None)))
            or 0
        )
        embedded_current = (
            session.scalar(select(func.count(Posting.id)).where(Posting.embedding_model == tag))
            or 0
        )
        embedded_stale = (
            session.scalar(
                select(func.count(Posting.id)).where(
                    Posting.description_embedding.is_not(None),
                    Posting.embedding_model.is_distinct_from(tag),
                )
            )
            or 0
        )
        unparsed = (
            session.scalar(
                select(func.count(RawPosting.id)).where(
                    ~RawPosting.id.in_(select(Posting.raw_posting_id))
                )
            )
            or 0
        )
        scored = session.scalar(select(func.count(RelevanceScore.posting_id))) or 0
        oldest, newest = session.execute(
            select(func.min(RawPosting.posted_at), func.max(RawPosting.posted_at))
        ).one()
        companies = (
            session.scalar(
                select(func.count(func.distinct(Posting.company))).where(
                    Posting.canonical_id.is_(None)
                )
            )
            or 0
        )

    duplicates = parsed_total - canonical

    print("=== corpus ===")
    print(f"  raw postings ingested   {raw_total}")
    print(f"  parsed                  {parsed_total}   (unparsed backlog: {unparsed})")
    print(f"  duplicates collapsed    {duplicates}")
    print(f"  CANONICAL (site shows)  {canonical}   across {companies} companies")
    print()
    print("=== embeddings ===")
    print(f"  current model {tag}   {embedded_current}")
    if embedded_stale:
        print(f"  stale, will be re-embedded              {embedded_stale}")
    print()
    print("=== scoring (batch/personal only) ===")
    print(f"  scored postings         {scored}")
    if oldest and newest:
        print()
        print("=== posted_at range ===")
        print(f"  {oldest:%Y-%m-%d %H:%M} .. {newest:%Y-%m-%d %H:%M} UTC")

    try:
        with httpx.Client(timeout=10.0) as client:
            thread_id = get_latest_who_is_hiring_thread_id(client)
            comment_ids = get_top_level_comment_ids(client, thread_id) if thread_id else []
        if comment_ids:
            with session_scope() as session:
                have = (
                    session.scalar(
                        select(func.count(RawPosting.id)).where(
                            RawPosting.source == SOURCE_NAME,
                            RawPosting.source_id.in_([str(c) for c in comment_ids]),
                        )
                    )
                    or 0
                )
            remaining = len(comment_ids) - have
            print()
            print("=== current thread ===")
            print(f"  thread {thread_id}: {len(comment_ids)} top-level comments")
            print(f"  ingested {have}, {remaining} left to fetch")
            if remaining:
                runs = -(-remaining // 30)
                print(f"  ~{runs} more pipeline run(s) at the default limit of 30")
    except Exception as e:
        print(f"\n(couldn't reach HN to compare: {type(e).__name__}: {e})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
