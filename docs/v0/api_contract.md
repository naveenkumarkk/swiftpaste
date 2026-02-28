# SwiftPaste API Contract (V1)

## Base Rules

1. **Content-Type**: `application/json`
2. **All responses are JSON** (including errors)
3. **Errors use one consistent envelope**
4. **Short URLs / `shortId` are immutable identifiers**
   - You can create new versions later, but a `shortId` itself never changes.

---

## Conventions

### Timestamps

All timestamps are **UTC ISO-8601** (e.g. `2026-02-21T10:12:45Z`).

### Visibility

`visibility` is one of:

- `public`
- `private`

> v1 note: “private” can behave like “unlisted” (not searchable, only accessible by link) until auth exists.

### Standard Error Shape

All error responses follow this shape:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable message",
    "details": {
      "optional": "object"
    },
    "requestId": "optional-string"
  }
}
```

## SLOs (Local Dev Targets)

### Availability

**Goal:** Keep the API up and responding during local testing.

- **API availability:** **99.9%** during a **1-hour** test window  
  Practical meaning (local): no crashes, clean restarts, no “stuck” service.

- **How you’ll measure later**

  - `availability = successful_requests / total_requests`
  - “Successful” = HTTP 2xx + 3xx (optionally include 4xx if you want to measure *service up* vs *user success*)

---

### Latency

Measured under a local load test (same machine / Docker network).

#### GET `/s/{shortId}` (read path)

**Load target:** **100 RPS**

- **p95 latency:** ≤ **50ms**
- **p99 latency:** ≤ **150ms**

#### POST `/snippets` (write path)

**Load target:** **10 RPS**

- **p95 latency:** ≤ **120ms**

#### Notes

- Track latency at the API boundary (request received → response sent).
- Record percentiles (p50/p95/p99) per endpoint.

---

### Correctness (Non-negotiable)

These are “must never break” guarantees.

- **0% stale reads:** If a snippet is created successfully, an immediate read must return the same content.
- **0 user-visible `shortId` collisions:** Collisions must be handled internally (retry), never returned to the client.

---

### Error Budget (Optional but Useful)

During a **10-minute** load test:

- **5xx error rate:** < **0.1%**

### How you’ll measure later

- `5xx_rate = 5xx_responses / total_responses`

---

### What to Log (so SLOs are measurable later)

For every request (at minimum):

- `requestId`
- `endpoint`
- `method`
- `statusCode`
- `latencyMs`
- `timestamp`

### PATCH /snippets/{shortId}

Rule: in one DB transaction

lock snippet row

new_version = latest_version + 1

insert snippet_versions row

update snippet.latest_version = new_version

Locking matters so two edits don’t both create version “2”.

In Postgres you use SELECT ... FOR UPDATE.
