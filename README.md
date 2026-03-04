# SwiftPaste — Engineering Log (So Far) + Next Steps

SwiftPaste is a Pastebin-style code-snippet manager built locally (Docker) to practice production-grade system design: reliability, scalability, performance, and observability — without cloud bills.

---

## 1) What’s completed so far

### 1.1 Repo + documentation

- Created project repo structure (`swiftpaste/`) and `docs/` folder.
- Wrote **v0 API contract** covering:
  - `GET /health`
  - `POST /snippets`
  - `GET /s/{shortId}`
- Standardized a **consistent error response shape** for all endpoints.
- Defined **v0 SLO targets** (latency + error rate) to make performance measurable.

### 1.2 Key design decisions (locked)

- **Short IDs:** random Base62, length = **8**
- **Storage:** Postgres stores snippet content (`TEXT`)
- **Privacy model:** **unlisted private**
  - Anyone with the URL can read
  - Private snippets must never appear in search/listing feeds
- **Max content length:** **50,000** characters
- **Primary key:** **UUID** (`id`)

### 1.3 Local runtime + database

- Docker Compose runs the system locally.
- `/health` endpoint works.
- DB migrations exist (at least initial schema).
- DB enforces:
  - `short_id` uniqueness
  - collision-handling strategy exists (retry on conflict)

### 1.4 MVP endpoints (end-to-end)

- `POST /snippets` works end-to-end:
  - accepts content + visibility
  - returns shortId + url + createdAt
- `GET /s/{shortId}` works end-to-end:
  - returns snippet by shortId
  - returns 404 for unknown/invalid IDs
- Unique constraint on `short_id` enforced and collisions handled via retry.

### 1.5 Horizontal scaling + failure tolerance

- Added **NGINX load balancer** in front of the API.
- Ran multiple API replicas behind NGINX.
- Validated behavior under failure:
  - killed an API container during traffic
  - system stayed available (no single point of failure at app layer)

### 1.6 Caching with Redis + measurement

- Implemented **read-through caching** for snippet reads:
  - `GET` checks Redis first; falls back to Postgres on miss; stores with TTL.
- Added minimal cache observability:
  - `cache_hit_total`, `cache_miss_total`, `cache_error_total`
  - cache hit rate computed from counters
- Verified impact with load tests:
  - cold-cache vs warm-cache runs
  - p95 latency improvement measured
- Confirmed graceful degradation:
  - Redis down → fallback to Postgres (slower, but still working)

---

## 2) Architecture snapshot (current)

**Client → NGINX → API replicas → Postgres**
                     ↘︎ Redis (cache)

- Postgres is the source of truth.
- Redis accelerates hot reads.
- NGINX enables local horizontal scaling.
- Metrics/logging exist enough to validate SLOs and cache behavior.

---

## 3) Performance & cache validation results (k6)

### What the counters showed

**Before the k6 run**

- `cache_hit_total = 54655`
- `cache_miss_total = 71`

**After the k6 run**

- `cache_hit_total = 73483`
- `cache_miss_total = 77`
- `cache_error_total = 0`

### Deltas for that run

- Δhit  = 73483 − 54655 = **18828**
- Δmiss = 77 − 71 = **6**

**Warm-cache hit rate**

- hit_rate = 18828 / (18828 + 6)
- = 18828 / 18834
- = **0.99968 ≈ 99.97%**

This is a textbook warm-cache result.

### Latency improvement (p95)

- Earlier run p95: **228.03 ms**
- This run p95: **212.09 ms**

Improvement:

- 228.03 − 212.09 = **15.94 ms**
- 15.94 / 228.03 ≈ **6.99% (~7%)**

Interpretation:

- Cache is helping, but not massively — likely because response cost is still dominated by JSON serialization and proxy overhead (and possibly returning a larger payload).

### Redis-down fallback test

- Redis stopped → `cache_error_total` increased to **562**
- API still served requests via Postgres fallback (no outage)
- After Redis restart, the system returned to normal (no persistent breakage)

---

## 4) Acceptance criteria write-up (cache milestone)

### 4.1 Observability (minimum) — PASS

- `cache_hit_total`, `cache_miss_total`, `cache_error_total` exported on `/v1/api/health/metrics`
- cache hit rate computed from counters:
  - `hits / (hits + misses)`

### 4.2 Cold vs warm cache — PASS

From warm run:

- Δhits = **18828**
- Δmisses = **6**
- Warm hit rate ≈ **99.97%**
- p95 improved from **~228ms → ~212ms** (**~7%**)

### 4.3 Redis-down fallback — PASS

- Redis down increases `cache_error_total` (observed **562**)
- API still serves reads (fallback to Postgres)
- Recovery after Redis restart without persistent failures

---

## 5) What “production-grade” still requires (next steps)

Below is a practical roadmap. Each step is scoped so it can be shipped and tested.

### Step 1 — Versioning (edits without breaking old links)

**Goal:** allow editing a snippet while preserving historical versions.

- Data model:
  - store multiple versions per shortId
  - define “latest” read behavior
- API additions:
  - `PATCH /snippets/{shortId}` (create new version)
  - optional: `GET /s/{shortId}?v=3` (fetch old version)
- Cache change:
  - version-aware keys (avoid stale reads)
  - e.g., cache `snippet:{shortId}:v{n}` and/or `snippet:{shortId}:latest`

**Acceptance tests**

- Edit creates a new version.
- Old versions are still retrievable.
- Cache never serves outdated content after an edit.

---

### Step 2 — Abuse resistance (rate limiting + payload limits)

**Goal:** prevent one user from melting your system.

- Rate limiting (start at NGINX or API layer):
  - per-IP limits for `POST /snippets` (stricter)
  - separate limits for `GET` (looser)
- Body size enforcement:
  - reject content larger than max length early

**Acceptance tests**

- sustained spam hits 429
- normal use unaffected

---

### Step 3 — Reliability hardening (timeouts, retries, circuit behavior)

**Goal:** predictable behavior under partial failure.

- Add timeouts for:
  - Postgres queries
  - Redis calls
- Define retry rules:
  - retry safe operations (idempotent reads) carefully
  - avoid retry storms
- Add “fail-open” cache behavior:
  - Redis errors should not break reads

**Acceptance tests**

- Redis slow/down does not cause API meltdown.
- Postgres slow triggers controlled errors (not indefinite hanging).

---

### Step 4 — Observability upgrade (production-style)

**Goal:** you can debug latency + errors quickly.

- Request ID propagation:
  - NGINX → API → logs
- Structured logs to STDOUT (container best practice)
- Metrics:
  - request rate, error rate
  - latency histograms (p50/p95/p99)
  - cache hit rate
- Optional: tracing later (OpenTelemetry)

**Acceptance tests**

- can correlate a single request across NGINX + API logs using request_id
- can explain p95 spikes with metrics (cache miss vs DB latency, etc.)

---

### Step 5 — Search + tags (eventual consistency)

**Goal:** add search without slowing down the core read path.

- Keep Postgres as source of truth.
- Choose a search approach:
  - start with Postgres full-text search (simple)
  - later: async indexing to a search service (more distributed)
- Eventual consistency path:
  - write event → async index update

**Acceptance tests**

- creating snippets doesn’t block on search indexing
- search results converge within a defined time window

---

### Step 6 — Chaos + load testing “as a feature”

**Goal:** treat reliability as a product requirement.

- automated load tests (repeatable)
- kill container tests (repeatable)
- Redis down tests
- Postgres restart tests

**Acceptance tests**

- SLOs remain stable across runs
- regressions are caught early

---

## 6) Suggested immediate next milestone

**Implement Versioning + Version-aware caching.**

Why next:

- core product feature (Pastebin-like edits)
- forces cache correctness (a real production problem)
- sets you up cleanly for search/tags later

---
