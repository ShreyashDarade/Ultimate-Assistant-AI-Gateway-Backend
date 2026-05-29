# 🧠 Ultimate Assistant — AI Gateway Backend

A production-grade, **multi-provider BYOK (Bring Your Own Key) AI gateway** that powers the *Ultimate Assistant*. It exposes a single, unified API for **chat, images, audio, video, embeddings, and any-to-any modality conversion** across 12+ AI providers — while each user supplies and controls their own provider keys.

Built with **FastAPI**, fully async top-to-bottom, streaming-first (SSE + WebSocket), and designed as a modular monolith you can scale horizontally.

---

## ✨ Features

- **One API, many providers** — OpenAI, Anthropic, Google, xAI, Mistral, Cohere, Groq, DeepSeek, ElevenLabs, Replicate, Stability, Fal, and more.
- **BYOK with encryption at rest** — user keys are encrypted with **Fernet** (`MASTER_ENCRYPTION_KEY`); plaintext is only ever cached briefly in Redis.
- **Capability-based modality router** — any input modality routes to any capable provider (e.g. text→image, audio→text, text→speech).
- **Streaming-first** — token streaming over **SSE** and **WebSocket**.
- **Unified request/response schema** — providers are normalized behind one shape, so clients don't care who served the request.
- **Resilient by default** — shared pooled `httpx` clients (HTTP/2), retries with backoff on transient errors, circuit breaking, and fail-fast on client errors (4xx).
- **Full auth** — JWT access/refresh tokens, bcrypt password hashing.
- **Observability** — `structlog` structured logs, OpenTelemetry tracing, Prometheus metrics.
- **Background processing** — `arq` workers for long-running jobs (transcoding, large media, etc.).
- **Storage** — media results stored in **S3** (or MinIO locally).

---

## 🏗️ Architecture

```
                         ┌──────────────────────────────┐
   Client (web / app) ───►   FastAPI  (ORJSONResponse)   │
   SSE / WebSocket    ◄───┤  • Auth (JWT)                │
                         │  • Rate limiting              │
                         │  • Unified API (/api/v1)      │
                         └───────────────┬──────────────┘
                                         │
                           ┌─────────────▼──────────────┐
                           │     ModalityRouter          │
                           │  (capability map → dispatch)│
                           └─────────────┬──────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                           ▼
      ┌──────────────┐          ┌──────────────┐            ┌──────────────┐
      │ Provider     │          │ Provider     │   ...      │ Provider     │
      │ Adapters     │          │ Adapters     │            │ Adapters     │
      │ (OpenAI…)    │          │ (Anthropic…) │            │ (ElevenLabs…)│
      └──────┬───────┘          └──────┬───────┘            └──────┬───────┘
             └────────── shared pooled httpx.AsyncClient ──────────┘

   Postgres (asyncpg + SQLAlchemy 2.0)   Redis (cache / queue)   S3 / MinIO (media)
                                          arq workers (jobs)
```

**Key directories**

| Path | Responsibility |
|------|----------------|
| `app/main.py` | App factory, middleware, CORS, lifespan |
| `app/core/` | Config, security (JWT + Fernet), exceptions, lifespan |
| `app/api/v1/` | Versioned routes + dependency injection |
| `app/providers/` | Provider adapters, registry, capability map, retry, client pool |
| `app/services/` | Router, key service, chat service (business logic) |
| `app/schemas/` | Pydantic request/response models |
| `app/db/` | Async engine + session management |
| `app/workers/` | `arq` background worker |
| `scripts/` | Master-key generation, provider seeding |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12** (project targets 3.12 — see note below)
- **Docker + Docker Compose** (for Postgres, Redis, MinIO)
- A provider API key to test with (e.g. OpenAI)

> ⚠️ **Note:** If your local virtualenv is Python 3.11, either recreate it with 3.12 or relax `requires-python` in `pyproject.toml`.

### 1. Clone & install

```bash
git clone <your-repo-url> ultimate-assistant
cd ultimate-assistant

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Generate the master encryption key and a strong secret, then paste them into `.env`:

```bash
python scripts/generate_master_key.py     # → MASTER_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"   # → SECRET_KEY
```

### 3. Start infrastructure

```bash
docker compose up -d postgres redis minio
```

### 4. Run migrations

```bash
alembic upgrade head
# optional: seed the provider catalog
python -m scripts.seed_providers
```

### 5. Run the API

```bash
make run
# or directly:
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

Open the interactive docs at **http://localhost:8000/docs**.

### 6. Run the background worker (separate terminal)

```bash
make worker
# or: arq app.workers.worker.WorkerSettings
```

---

## 🐳 Run everything with Docker

```bash
make docker-up      # build + start the full stack
make docker-logs    # tail the app logs
make docker-down    # stop
```

---

## 🔌 Using it as the Ultimate Assistant backend

All endpoints are under `/api/v1`. Typical flow:

### 1. Register / log in

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "super-secret"}'

# Login → returns access + refresh tokens
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "super-secret"}'
```

Use the returned `access_token` as `Authorization: Bearer <token>` on every call below.

### 2. Add your provider key (BYOK)

The key is encrypted before it ever touches the database.

```bash
curl -X POST http://localhost:8000/api/v1/keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-..."}'
```

### 3. Chat (non-streaming)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello!"}]
      }'
```

### 4. Chat (streaming via SSE)

```bash
curl -N -X POST http://localhost:8000/api/v1/chat?stream=true \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "provider": "openai",
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Write a haiku about the sea."}]
      }'
```

### 5. Other modalities

| Capability | Endpoint |
|------------|----------|
| Text → Image | `POST /api/v1/images` |
| Text → Speech / Speech → Text | `POST /api/v1/audio` |
| Video generation | `POST /api/v1/video` |
| Embeddings | `POST /api/v1/embeddings` |
| Any-to-any conversion | `POST /api/v1/conversions` |
| List available models | `GET /api/v1/models` |
| Upload files | `POST /api/v1/files` |
| Conversation history | `GET/POST /api/v1/conversations` |

> The **unified response schema** means switching `provider`/`model` requires no client changes — the gateway normalizes everything.

### WebSocket streaming

Connect to `ws://localhost:8000/api/v1/chat/ws` and send a chat payload to receive token chunks in real time.

---

## ⚙️ Configuration reference

Key settings in `.env` (see `.env.example` for the full list):

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing secret. **Must** be strong in production. |
| `MASTER_ENCRYPTION_KEY` | Fernet key used to encrypt user provider keys. |
| `DATABASE_URL` | Async Postgres DSN (`postgresql+asyncpg://…`). |
| `REDIS_URL` | Redis connection (cache + queue). |
| `S3_BUCKET` / `S3_ENDPOINT_URL` | Media storage (MinIO locally, AWS in prod). |
| `CORS_ORIGINS` | Comma-separated allowed origins (used when `DEBUG=false`). |
| `RATE_LIMIT_*` | Per-window request limits. |

**Production guardrails:** the app refuses to start in production if `SECRET_KEY` is weak/default, `MASTER_ENCRYPTION_KEY` is missing, or `DEBUG=true`.

---

## 🧪 Development

```bash
make lint      # ruff + mypy
make format    # auto-format + fix
make test      # pytest with coverage
make migrate-new msg="add foo table"   # create a migration
```

Install dev tooling:

```bash
pip install -e ".[dev]"
```

---

## 🩺 Health & metrics

- **Health check:** `GET /health`
- **Prometheus metrics:** `GET /metrics`
- **OpenAPI docs:** `GET /docs` (Swagger) and `GET /redoc`

---

## 🔒 Security notes

- User provider keys are **encrypted at rest** with Fernet; decrypted values are cached in Redis only briefly (short TTL) and invalidated on update/delete.
- Retries apply only to transient/server errors (`408, 425, 429, 5xx`); client errors fail fast.
- Passwords hashed with bcrypt; JWT access + refresh token rotation.
- Always set strong `SECRET_KEY` and `MASTER_ENCRYPTION_KEY` and disable `DEBUG` in production.

---

## 📦 Tech stack

FastAPI · Uvicorn/Gunicorn · httpx (HTTP/2) · SQLAlchemy 2.0 (async) · asyncpg · Alembic · Redis · arq · Pydantic v2 · python-jose · passlib/bcrypt · cryptography (Fernet) · aioboto3 (S3) · structlog · OpenTelemetry · Prometheus.

---

## 📄 License

Add your license here (e.g. MIT).
