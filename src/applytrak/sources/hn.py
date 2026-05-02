"""Hacker News 'Ask HN: Who is hiring?' scraper.

Uses HN's public Firebase REST API (no auth, no rate limits).
  - User endpoint:  GET /v0/user/<username>.json
  - Item endpoint:  GET /v0/item/<id>.json

Each top-level comment in a 'Who is hiring?' thread is treated as one posting.
"""

import logging

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_USER_WHOISHIRING = "whoishiring"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={id}"
SOURCE_NAME = "hn_whoishiring"


class FetchedPosting(BaseModel):
    """One scraped posting, ready to persist as a RawPosting row."""

    source: str = SOURCE_NAME
    source_id: str
    url: str
    raw_text: str = Field(min_length=1)


def _clean_html(html_text: str) -> str:
    """Strip HTML tags, decode entities, normalize whitespace.

    Preserves paragraph breaks (the structure matters for LLM parsing later).
    """
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.insert_before("\n")
    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _fetch_item(client: httpx.Client, item_id: int) -> dict | None:
    """GET one item from HN API. Returns None if the item is missing."""
    response = client.get(f"{HN_API_BASE}/item/{item_id}.json")
    response.raise_for_status()
    return response.json()


def get_latest_who_is_hiring_thread_id(client: httpx.Client) -> int | None:
    """Find the most recent 'Ask HN: Who is hiring?' thread.

    Walks `whoishiring`'s submitted history newest-first, returns the first
    matching post's id. Usually found within the first 3-5 items.
    """
    response = client.get(f"{HN_API_BASE}/user/{HN_USER_WHOISHIRING}.json")
    response.raise_for_status()
    submitted_ids: list[int] = response.json().get("submitted", [])

    for item_id in submitted_ids:
        item = _fetch_item(client, item_id)
        if not item:
            continue
        title = item.get("title", "")
        if title.startswith("Ask HN: Who is hiring?"):
            logger.info("Found latest 'Who is hiring?' thread: %r (id=%s)", title, item_id)
            return item_id

    return None


def get_top_level_comment_ids(client: httpx.Client, thread_id: int) -> list[int]:
    """Return the IDs of every top-level comment under a thread."""
    item = _fetch_item(client, thread_id)
    if not item:
        return []
    return item.get("kids", [])


def fetch_comment(client: httpx.Client, comment_id: int) -> FetchedPosting | None:
    """Fetch one comment as a FetchedPosting. Returns None for deleted/dead/empty comments."""
    item = _fetch_item(client, comment_id)
    if not item:
        return None
    if item.get("dead") or item.get("deleted"):
        return None
    text = item.get("text")
    if not text:
        return None
    return FetchedPosting(
        source_id=str(comment_id),
        url=HN_ITEM_URL.format(id=comment_id),
        raw_text=_clean_html(text),
    )
