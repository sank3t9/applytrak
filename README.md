# ApplyTrak

Paste your resume, get the job postings that actually fit — ranked, with the reasoning shown.

Postings come from Hacker News "Who is hiring?" threads. A scheduled job fetches them, extracts structured fields with an LLM, embeds them, and collapses reposts. When someone pastes a resume, vector search narrows the corpus to the closest handful of postings and an LLM scores each one against that resume.

> **Live demo:** _add your Vercel URL here_

## How matching works

Two stages, because neither half can do the job alone at reasonable cost:

1. **Retrieve (cheap, broad).** The resume is embedded and compared against every posting's embedding with pgvector cosine similarity. Hundreds of postings → the 15 closest, in milliseconds, for the price of one embedding call.
2. **Rerank (expensive, careful).** Each candidate gets one LLM call scoring it against the resume on an explicit rubric — skills 40%, YOE 25%, location 15%, domain/seniority 20% — returning a score, the skills matched and missing, hard blockers, and a one-line verdict.

Vector similarity alone is too low-signal to rank job fit; LLM-scoring the whole corpus would be slow and expensive. Retrieve-then-rerank keeps the recall of the first and the judgment of the second.

## Pipeline

```
HN Firebase API → raw_postings
                     ↓  LLM structured extraction
                  postings (company, title, YOE, skills, comp, confidence)
                     ↓  embeddings (1024-dim)
                  postings.description_embedding
                     ↓  pgvector cosine ≥ 0.92
                  duplicates marked via canonical_id
                     ↓
        ┌────────────┴─────────────┐
   visitor pastes resume      personal use: score against
   → retrieve + rerank        profile.yaml → Telegram digest
```

Every stage is idempotent and resumable: each one queries for the rows the previous stage produced but it hasn't handled yet (no embedding, no parse, stale embedding model), so re-running is always safe and interrupted runs pick up where they stopped.

## Stack

Python 3.11 · FastAPI · PostgreSQL + pgvector · SQLAlchemy · Pydantic v2 · Redis (optional) · Anthropic Claude / Google Gemini · Voyage AI / Gemini embeddings · APScheduler · LangSmith · Docker

## Running the demo for $0

The deployed demo uses four free services and no credit card:

| Piece | Service | Why |
|---|---|---|
| Scheduled pipeline | GitHub Actions cron | Public repos get unlimited minutes; a batch job doesn't need a server |
| Database | Neon (serverless Postgres) | Free tier includes pgvector; the only thing that persists |
| LLM + embeddings | Gemini free tier | One key covers extraction, scoring, and embeddings |
| Web app | Vercel | Requests are short and stateless once the pipeline is out of the request path |

Nothing runs 24/7: the cron VM exists for a few minutes every 6 hours, and Vercel functions live only for the length of a request.

### Deploy it yourself

1. **Neon** — create a free project, copy the pooled connection string.
2. **Gemini** — get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey).
3. **GitHub** — add repo secrets `DEMO_DATABASE_URL` and `GEMINI_API_KEY`, then run the `pipeline` workflow manually once to populate the corpus.
4. **Vercel** — import the repo and set: `DATABASE_URL` (the Neon pooled URL), `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`, `EMBEDDING_PROVIDER=gemini`, `RUN_SCHEDULER=false`, `EXPOSE_ADMIN_ENDPOINTS=false`.

`RUN_SCHEDULER=false` matters because serverless has no long-lived process to run APScheduler; `EXPOSE_ADMIN_ENDPOINTS=false` hides the `/run/*` triggers so visitors can't spend your API quota.

Visitor resumes are never written to the database — they live in the request and the browser tab, nothing else.

## Local setup

```bash
cp .env.example .env          # fill in DATABASE_URL + a provider key
docker compose up --build     # postgres + redis + api on :8000
```

`entrypoint.sh` applies the schema on every start. Then seed a profile and run the pipeline:

```bash
cp profile.example.yaml profile.yaml    # your resume + targeting
uv run python scripts/seed_profile.py
uv run python scripts/run_pipeline.py                        # fetch, parse, embed, dedup
uv run python scripts/run_pipeline.py --with-score --with-digest   # + score + Telegram
```

Open http://localhost:8000 for the matcher, `/docs` for the API.

Switching to the free provider locally:

```bash
LLM_PROVIDER=gemini EMBEDDING_PROVIDER=gemini uv run python scripts/gemini_smoke.py
```

## Evaluation

The parser is checked against a hand-labeled golden set of ~30 real postings (`tests/golden/jds.jsonl`), scored per field — exact match for categorical fields, range overlap for YOE, Jaccard for skill lists — with a summary printed per run:

```bash
uv run pytest tests/test_parser_eval.py -s      # needs -s to see the accuracy table
```

The scorer is graded by a separate LLM-as-Judge call that reads the original inputs and the scorer's output, then rates the reasoning's specificity and whether the score is defensible:

```bash
uv run pytest tests/test_scorer_judge.py -s
```

Both cost real API calls, so CI runs them on a weekly schedule and on manual dispatch rather than per-commit; the per-commit workflow runs lint plus the free unit tests.

## Design notes

**Why a pipeline and not an agent.** The control flow here never varies: fetch, parse, embed, dedup, score. An agent's value is choosing what to do next based on what it just saw, and there's no such decision in this system — an LLM driving the sequence would just be paying reasoning tokens to rediscover `main()`, while making cost, latency, and testability worse. The stages stay pure functions, which is exactly what makes the golden-set eval possible.

**Embedding provenance.** Vectors from different models occupy unrelated coordinate spaces, so comparing them produces noise rather than a similarity. Every row records which model embedded it; dedup and matching filter to the active model, and the embed stage treats a stale tag like a missing vector. Switching `EMBEDDING_PROVIDER` therefore re-embeds the corpus over the next few runs instead of silently corrupting results.

**Cost control.** Parses are cached by content hash plus provider and model, so re-running the pipeline (or the eval suite) doesn't re-pay for text already seen. Scoring prompts put the resume and rubric in a cached system block, so a batch pays full input price only on the first call. All provider calls pass through a per-minute rate limiter.

## Deliberately out of scope

Multiple job sources, auto-applying, resume rewriting, multi-user accounts, and a full application-tracking UI. One source, one clear pipeline, real evals.
