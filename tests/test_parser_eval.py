"""Per-field accuracy eval of the LLM parser against the hand-labeled golden set.

Reads tests/golden/jds.jsonl, runs `parse_jd` on each raw_text, scores against
the human `expected` block, and asserts overall per-entry score above
PASS_THRESHOLD.

Cost: ~30 Haiku calls = ~$0.06 first run. After that, parse cache makes re-runs
free — UNLESS you change the parse prompt, in which case bump CACHE_VERSION
in src/applytrak/llm/cache.py to invalidate stale entries.

Run:
    pytest tests/test_parser_eval.py -s
"""

import json
from pathlib import Path

import pytest

from applytrak.llm.parse_prompt import parse_jd
from applytrak.schemas import ParsedJD

GOLDEN_PATH = Path(__file__).parent / "golden" / "jds.jsonl"

PASS_THRESHOLD = 0.60


def _load_golden() -> list[dict]:
    if not GOLDEN_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


GOLDEN_ENTRIES = _load_golden()


# ---------------------------------------------------------------------------
# Per-field comparators
# ---------------------------------------------------------------------------


def _string_match(actual: str | None, expected: str | None) -> bool:
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    return actual.strip().lower() == expected.strip().lower()


def _yoe_range_match(
    a_min: int | None, a_max: int | None,
    e_min: int | None, e_max: int | None,
) -> bool:
    """Both null OR ranges overlap."""
    if (a_min, a_max) == (None, None) and (e_min, e_max) == (None, None):
        return True
    if (a_min, a_max) == (None, None) or (e_min, e_max) == (None, None):
        return False
    return max(a_min or 0, e_min or 0) <= min(a_max or 100, e_max or 100)


def _set_overlap(actual: list[str], expected: list[str]) -> float:
    """Jaccard similarity on lowercased skills."""
    a = {s.lower().strip() for s in actual}
    e = {s.lower().strip() for s in expected}
    if not a and not e:
        return 1.0
    if not a or not e:
        return 0.0
    return len(a & e) / len(a | e)


def _comp_close(
    actual: int | None, expected: int | None, pct_tolerance: float = 0.10
) -> bool:
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    return abs(actual - expected) / max(expected, 1) <= pct_tolerance


def _confidence_close(actual: float, expected: float, tolerance: float = 0.2) -> bool:
    return abs(actual - expected) <= tolerance


# ---------------------------------------------------------------------------
# Entry-level scoring
# ---------------------------------------------------------------------------


def score_entry(parsed: ParsedJD, expected: dict) -> dict[str, bool | float]:
    return {
        "company":             _string_match(parsed.company, expected.get("company")),
        "title":               _string_match(parsed.title, expected.get("title")),
        "location":            _string_match(parsed.location, expected.get("location")),
        "is_remote":           parsed.is_remote == expected.get("is_remote"),
        "is_hybrid":           parsed.is_hybrid == expected.get("is_hybrid"),
        "yoe_range":           _yoe_range_match(
                                   parsed.yoe_min, parsed.yoe_max,
                                   expected.get("yoe_min"), expected.get("yoe_max"),
                               ),
        "must_have_skills":    _set_overlap(parsed.must_have_skills,
                                            expected.get("must_have_skills", [])),
        "nice_to_have_skills": _set_overlap(parsed.nice_to_have_skills,
                                            expected.get("nice_to_have_skills", [])),
        "comp_min":            _comp_close(parsed.comp_min, expected.get("comp_min")),
        "comp_max":            _comp_close(parsed.comp_max, expected.get("comp_max")),
        "comp_currency":       _string_match(parsed.comp_currency, expected.get("comp_currency")),
        "parse_confidence":    _confidence_close(
                                   parsed.parse_confidence,
                                   expected.get("parse_confidence", 0.5),
                               ),
    }


def _to_float(v: bool | float) -> float:
    return float(v) if isinstance(v, bool) else v


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GOLDEN_ENTRIES, reason="No golden entries — run scripts/seed_golden.py first")
@pytest.mark.parametrize(
    "entry",
    GOLDEN_ENTRIES,
    ids=[e["id"] for e in GOLDEN_ENTRIES],
)
def test_parse_quality(entry: dict, eval_results: dict) -> None:
    parsed = parse_jd(entry["raw_text"])
    fields = score_entry(parsed, entry["expected"])

    field_scores = [_to_float(v) for v in fields.values()]
    overall = sum(field_scores) / len(field_scores)
    eval_results[entry["id"]] = (overall, fields)

    failing = {k: v for k, v in fields.items() if _to_float(v) < 0.5}
    assert overall >= PASS_THRESHOLD, (
        f"Entry {entry['id']} scored {overall:.2f} (< {PASS_THRESHOLD}). "
        f"Failing fields: {failing}"
    )
