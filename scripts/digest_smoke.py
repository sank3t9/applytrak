"""Smoke test: build a digest and optionally send to Telegram + record in digests table.

Usage:
    python scripts/digest_smoke.py --dry-run      # build + print, don't send
    python scripts/digest_smoke.py                # send and record
    python scripts/digest_smoke.py --include-sent # include already-sent postings (preview)
"""

import logging
import sys

from applytrak.db import session_scope
from applytrak.delivery.digest import (
    build_digest_message,
    record_digest_sent,
    select_top_postings,
)
from applytrak.delivery.telegram import send_message

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    include_sent = "--include-sent" in sys.argv

    with session_scope() as session:
        rows = select_top_postings(session, exclude_sent=not include_sent)

    message = build_digest_message(rows)
    print(f"\n[OK] Built digest: {len(rows)} item(s), {len(message)} chars")
    print("=" * 60)
    print(message)
    print("=" * 60)

    if dry_run:
        print("\n[OK] --dry-run set, not sending or recording.")
        return 0

    if not rows:
        print("\n[OK] No new postings to send. Skipping Telegram + DB write.")
        return 0

    try:
        response = send_message(message)
        msg_id = response.get("result", {}).get("message_id")
        status = "sent"
        delivery_message_id = str(msg_id) if msg_id is not None else None
        print(f"\n[OK] Sent to Telegram. message_id={msg_id}")
    except Exception as e:
        print(f"\n[FAIL] Telegram send failed: {type(e).__name__}: {e}", file=sys.stderr)
        status = "failed"
        delivery_message_id = None

    with session_scope() as session:
        digest = record_digest_sent(
            session,
            posting_ids=[r.posting_id for r in rows],
            delivery_method="telegram",
            delivery_status=status,
            delivery_message_id=delivery_message_id,
        )
        print(f"[OK] Recorded digest id={digest.id} status={status}")

    return 0 if status == "sent" else 1


if __name__ == "__main__":
    sys.exit(main())
