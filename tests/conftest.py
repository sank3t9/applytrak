"""Pytest fixtures + session hooks for the eval harness.

Per-entry results from `tests/test_parser_eval.py` accumulate on
`config._eval_results`. The `pytest_sessionfinish` hook prints a
field-level summary once all tests have run.
"""

from collections import defaultdict

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config._eval_results = {}  # type: ignore[attr-defined]
    config._judge_results = {}  # type: ignore[attr-defined]


@pytest.fixture
def eval_results(request: pytest.FixtureRequest) -> dict:
    """Per-test results sink for the parser eval."""
    return request.config._eval_results  # type: ignore[attr-defined]


@pytest.fixture
def judge_results(request: pytest.FixtureRequest) -> dict:
    """Per-test results sink for the scorer LLM-as-Judge eval."""
    return request.config._judge_results  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _print_parser_summary(session)
    _print_judge_summary(session)


def _print_parser_summary(session: pytest.Session) -> None:
    results: dict[str, tuple[float, dict]] = getattr(session.config, "_eval_results", {})
    if not results:
        return

    by_field: dict[str, list[float]] = defaultdict(list)
    for _, (_, fields) in results.items():
        for field, score in fields.items():
            by_field[field].append(float(score) if isinstance(score, bool) else score)

    print("\n\n=== Parser eval — field-level accuracy ===")
    for field in sorted(by_field):
        scores = by_field[field]
        avg = sum(scores) / len(scores)
        print(f"  {field:25s}  {avg:.3f}  (n={len(scores)})")

    overalls = [overall for overall, _ in results.values()]
    print("\n=== Parser overall ===")
    print(f"  Mean entry score:        {sum(overalls) / len(overalls):.3f}")
    print(f"  Entries above 0.70:      {sum(1 for s in overalls if s >= 0.70)}/{len(overalls)}")
    print(f"  Entries above 0.85:      {sum(1 for s in overalls if s >= 0.85)}/{len(overalls)}")


def _print_judge_summary(session: pytest.Session) -> None:
    results: dict[str, object] = getattr(session.config, "_judge_results", {})
    if not results:
        return

    qualities = [v.reasoning_quality for v in results.values()]
    appropriate_rate = sum(1 for v in results.values() if v.score_appropriate) / len(results)
    all_flags = [flag for v in results.values() for flag in v.flags]

    print("\n\n=== Scorer judge eval ===")
    print(f"  Mean reasoning_quality:  {sum(qualities) / len(qualities):.3f}  (n={len(qualities)})")
    print(f"  score_appropriate rate:  {appropriate_rate:.2f}")
    if all_flags:
        print(f"  Flags raised: {len(all_flags)}")
        flag_counts: dict[str, int] = defaultdict(int)
        for flag in all_flags:
            flag_counts[flag] += 1
        for flag, n in sorted(flag_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    [{n}] {flag}")
