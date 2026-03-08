# SwiftPaste

SwiftPaste is a FastAPI-based snippet manager with snippet versioning, JWT auth, Redis read-through cache, and PostgreSQL persistence.

## Stack

- Python 3.13
- FastAPI + Uvicorn
- SQLAlchemy (async) + Alembic
- PostgreSQL 16
- Redis 7
- NGINX (reverse proxy)
- Docker Compose
- Prometheus-compatible metrics via `prometheus_client`

## Architecture

```mermaid
flowchart LR
    C[Client] --> N[NGINX :80]
    C --> A[FastAPI :8000]
    N --> A

    A --> M[Middlewares\nRequest Logging\nRequest Metrics\nCORS]
    M --> R[API Routers]

    R --> S[Snippet Service]
    R --> H[Health Service]
    R --> U[FastAPI Users Auth]

    S --> RD[(Redis)]
    S --> PG[(PostgreSQL)]
    H --> RD
    H --> PG
    U --> PG

    A --> P[/v1/api/health/metrics]
```

## Request Flow Diagram

The main read path (`GET /v1/api/snippet/{short_id}`) is cache-first:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Route
    participant Service as snippet_service.get_snippet_cached
    participant Redis
    participant DB as PostgreSQL

    Client->>API: GET /v1/api/snippet/{short_id}?version=
    API->>Service: get_snippet_cached(short_id, version, user)
    Service->>Redis: GET snippet:{short_id}:v{version|latest}

    alt Cache hit
        Redis-->>Service: cached snippet JSON
        Service-->>API: SnippetResponse
        API-->>Client: 200
    else Cache miss or Redis error
        Service->>DB: query snippet + requested/latest version
        Service->>Service: enforce visibility + expiry rules
        alt snippet visibility is public
            Service->>Redis: SETEX cache key (TTL)
        end
        Service-->>API: SnippetResponse
        API-->>Client: 200/4xx
    end
```

## Detailed Project Flow

### 1. End-to-end request path

Every API request follows this runtime path:

1. Client sends request to NGINX (`:80`) or directly to FastAPI (`:8000`).
1. NGINX forwards request to `api:8000`.
1. FastAPI processes request through middleware:
     - request ID + structured request logging
     - request/response metrics capture
     - CORS checks
1. Router validates auth requirements (`current_user` or `optional_user`).
1. Service layer runs business logic and accesses Redis/PostgreSQL.
1. Errors are translated by centralized exception handlers.
1. Response returns with `X-Request-Id` for traceability.

### 2. Login and JWT flow

```mermaid
sequenceDiagram
        participant Client
        participant API as FastAPI /auth routes
        participant UM as UserManager
        participant DB as users table
        participant JWT as JWT strategy

        Client->>API: POST /auth/register
        API->>UM: create user
        UM->>DB: INSERT users
        DB-->>UM: user row
        UM-->>API: user created
        API-->>Client: 201

        Client->>API: POST /auth/jwt/login
        API->>DB: validate credentials
        DB-->>API: user found + password valid
        API->>JWT: create token (lifetime = JWT_LIFETIME_SECONDS)
        JWT-->>API: bearer access token
        API-->>Client: 200 {access_token, token_type}

        Client->>API: POST /v1/api/snippet/ (Authorization: Bearer ...)
        API->>API: current_user(active=True)
        API-->>Client: 201 or 401
```

### 3. Google OAuth flow

Google OAuth routes are mounted under `/auth/google` via `fastapi-users` OAuth router.

```mermaid
sequenceDiagram
        participant Client
        participant API as /auth/google/*
        participant Google
        participant DB as users table

        Client->>API: GET /auth/google/authorize
        API-->>Client: redirect/auth URL
        Client->>Google: consent
        Google-->>API: callback with code/state
        API->>Google: exchange code for profile
        API->>DB: create user or link by email (associate_by_email=True)
        API-->>Client: auth response (token/session payload)
```

### 4. Database tables and ownership model

`users` table (from FastAPI Users base + custom field):

- `id` (UUID, PK)
- `email` (unique)
- `username` (unique)
- `hashed_password`
- `is_active`, `is_superuser`, `is_verified`

`snippets` table:

- `id` (UUID, PK)
- `short_id` (unique, length = 8)
- `title`
- `author_id` (FK -> `users.id`)
- `version_counter` (latest version number)
- `created_at`, `deleted_at` (soft delete)

`snippet_versions` table:

- `id` (UUID, PK)
- `snippet_id` (FK -> `snippets.id`)
- `version` (unique per snippet via composite unique constraint)
- `content`
- `visibility` (`PUBLIC` or `PRIVATE`)
- `expires_at`, `created_at`

Relationship summary:

- One user has many snippets.
- One snippet has many immutable versions.
- Reads exclude soft-deleted rows by default through SQLAlchemy event filtering.

### 5. Snippet lifecycle flow

Create (`POST /v1/api/snippet/`):

1. Authenticated user is required.
1. Service generates `short_id` (8 chars) and retries on collision.
1. Inserts into `snippets` and first row in `snippet_versions` (`version = 1`).
1. Returns full snippet response with current version.

Update (`PUT /v1/api/snippet/{id}`):

1. Confirms snippet ownership.
1. Updates snippet title when provided.
1. If content changed, increments `version_counter` and inserts a new version row.
1. Updates cache for latest key `snippet:{short_id}:vlatest`.

Share URL (`POST /v1/api/snippet/{id}/share`):

1. Confirms ownership and selected version.
1. Computes expiry (`ttl_seconds` or default TTL).
1. Stores expiry in `snippet_versions.expires_at`.
1. Returns `share_url` with `?v={version}`.

Read (`GET /v1/api/snippet/{short_id}`):

1. Attempts Redis cache read first.
1. On miss/error, loads from DB.
1. Enforces private visibility and expiry rules.
1. Caches public payloads only.

Delete (`DELETE /v1/api/snippet/{id}`):

1. Ownership check.
1. Soft delete is applied through DB event listeners.

### 6. Redis cache handling

- Client: `redis.asyncio` (`from_url`) with tight network timeouts:
  - `socket_connect_timeout=0.1`
  - `socket_timeout=0.1`
- Key format: `snippet:{short_id}:v{version_or_latest}`
- Read path behavior:
  - 2 retry attempts on Redis `GET` with short backoff (`50ms`)
  - increments `cache_hit_total`, `cache_miss_total`, `cache_error_total`
- Write path behavior:
  - `SETEX` with `CACHE_TTL_SECONDS`
  - only public snippets are cached for shared read path
- Degradation strategy:
  - Redis failure does not fail request; service falls back to PostgreSQL

### 7. Database handling

- Async SQLAlchemy engine with:
  - connect timeout (`DB_CONNECTION_TIMEOUT`)
  - statement timeout (`DB_QUERY_TIMEOUT`, passed to PostgreSQL)
- Per-request async DB session via dependency injection.
- Alembic migrations are used for schema management.
- Query-level metrics are captured via SQLAlchemy engine events.

### 8. Error handling flow

Centralized handlers in `app/core/exception_handlers.py` map failures to a consistent JSON envelope:

```json
{
    "error": {
        "code": "STRING_CODE",
        "message": "Human readable message",
        "details": "optional details",
        "requestId": "trace id"
    }
}
```

Handled categories:

- `AppError` -> business errors (`404`, `403`, `423`, etc.)
- `RequestValidationError` -> `422`
- `StarletteHTTPException` -> mapped HTTP error envelope
- `DBAPIError` -> `503` database timeout/failure envelope
- uncaught `Exception` -> `500`

### 9. Fault tolerance and graceful degradation

- Redis outage: read path falls back to DB and increments `cache_error_total`.
- Redis health check timeout is isolated and short.
- DB and Redis health are independently checked and exposed on readiness endpoint.
- `short_id` collision handling retries before returning failure.
- NGINX reverse proxy provides a stable ingress and supports API scaling (`--scale api=N`).
- Soft delete prevents immediate hard data removal from normal query paths.

### 10. Monitoring and observability

Metrics endpoint:

- `GET /v1/api/health/metrics`

Key metric groups:

- HTTP:
  - `http_requests_total`
  - `http_request_errors_total`
  - `http_request_latency_seconds`
  - `http_request_size_bytes`
  - `http_response_size_bytes`
- DB:
  - `db_query_latency_seconds`
  - `db_slow_queries_total`
- Cache:
  - `cache_hit_total`
  - `cache_miss_total`
  - `cache_error_total`

Logging and traceability:

- JSON structured logs to stdout.
- Request logs include method, path, status, latency, request ID.
- `X-Request-Id` is echoed back in response headers.

### 11. Other implemented features

- Snippet versioning with immutable historical rows.
- Visibility controls (`public`, `private`) at version level.
- Expiring shared links via TTL-based `expires_at` management.
- User-scoped snippet listing with pagination.
- Health endpoints for liveness/readiness and dependency status.

## Core Endpoints

Base API prefix is `/v1/api` (from `settings.V1_API_PREFIX`).

### Snippet routes

- `POST /v1/api/snippet/` create snippet (auth required)
- `PUT /v1/api/snippet/{id}` update snippet by UUID (auth required)
- `DELETE /v1/api/snippet/{id}` soft-delete snippet by UUID (auth required)
- `POST /v1/api/snippet/{id}/share` create/extend share URL (auth required)
- `GET /v1/api/snippet/{short_id}` read shared snippet (optional auth)
- `GET /v1/api/snippet/` list current user snippets (paginated, auth required)

### Health and metrics routes

- `GET /v1/api/health/` combined health check
- `GET /v1/api/health/ready` readiness check
- `GET /v1/api/health/health` liveness check
- `GET /v1/api/health/metrics` Prometheus metrics

### Auth routes

- `POST /auth/jwt/login`
- `POST /auth/jwt/logout`
- `POST /auth/register`
- `GET /users/me`
- Google OAuth routes under `/auth/google`

## Project Startup Commands

### 1) Docker startup (recommended)

1. Copy env file.

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

1. Start the stack.

```bash
docker compose up --build -d
```

1. Run migrations.

```bash
docker compose run --rm migrate
```

1. Verify services.

```bash
curl http://localhost/v1/api/health/ready
```

Useful URLs:

- API docs: `http://localhost/docs`
- ReDoc: `http://localhost/redoc`
- Metrics: `http://localhost/v1/api/health/metrics`
- PgAdmin: `http://localhost:5050`

### 2) Local startup (API on host, DB/Redis in Docker)

1. Start only dependencies.

```bash
docker compose up -d db redis
```

1. Set local host-based connection values (important: use `localhost`, not `db`).

```powershell
$env:DATABASE_URL="postgresql+asyncpg://postgres:naveenpranesh@localhost:5432/swiftpaste"
$env:DATABASE_SYNC_URL="postgresql+psycopg://postgres:naveenpranesh@localhost:5432/swiftpaste"
$env:REDIS_URL="redis://localhost:6379/0"
```

1. Install dependencies and run migrations.

```bash
uv sync --dev
uv run alembic upgrade head
```

1. Start the API.

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Alternative local entrypoint:

```bash
uv run python main.py
```

Docs URL in this mode:

- `http://localhost:8000/docs`

## Docker Commands Reference

- Start all services: `docker compose up -d`
- Rebuild and start: `docker compose up --build -d`
- View logs: `docker compose logs -f api nginx`
- Run one-off migration: `docker compose run --rm migrate`
- Scale API containers: `docker compose up -d --scale api=3`
- Stop and keep volumes: `docker compose down`
- Stop and remove volumes: `docker compose down -v`

## Data Model (Current)

- `users` auth users (FastAPI Users)
- `snippets` snippet metadata + `short_id` + `version_counter`
- `snippet_versions` immutable content versions per snippet

Notes:

- `short_id` length is fixed to 8 characters.
- Read queries apply a soft-delete filter via SQLAlchemy events.
- Cache key format is `snippet:{short_id}:v{version_or_latest}`.

## Observability

- Request logging middleware adds `X-Request-Id` and structured logs.
- Request and DB latency metrics are recorded with Prometheus histograms.
- Cache counters exposed:
  - `cache_hit_total`
  - `cache_miss_total`
  - `cache_error_total`

## Development Notes

- Default compose API command runs in reload mode:
  - `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Alembic reads `DATABASE_SYNC_URL` from settings via `alembic/env.py`.
- Current migration set includes initial schema in `alembic/versions/d07059efe000_initial_migration.py`.
