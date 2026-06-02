# 🧠 Ultimate Assistant AI Gateway

> **Multi-provider, any-to-any, BYOK AI gateway** — one API to rule all LLMs, image generators, TTS, STT, video, and embeddings.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192?style=flat-square&logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

</div>

---

## ✨ Key Features

### 🔌 13 Provider Adapters (Including Ollama)

| Provider | Chat | Vision | Image Gen | TTS | STT | Embeddings | Video |
|----------|:----:|:------:|:---------:|:---:|:---:|:----------:|:-----:|
| **OpenAI** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Anthropic** | ✅ | ✅ | — | — | — | — | — |
| **Google Gemini** | ✅ | ✅ | ✅ | — | — | ✅ | — |
| **Ollama** (local) | ✅ | ✅ | — | — | — | ✅ | — |
| **xAI (Grok)** | ✅ | — | — | — | — | — | — |
| **Mistral** | ✅ | — | — | — | — | ✅ | — |
| **Cohere** | ✅ | — | — | — | — | ✅ | — |
| **Groq** | ✅ | — | — | — | — | — | — |
| **DeepSeek** | ✅ | — | — | — | — | — | — |
| **ElevenLabs** | — | — | — | ✅ | ✅ | — | — |
| **Replicate** | — | — | ✅ | — | — | — | ✅ |
| **Stability AI** | — | — | ✅ | — | — | — | — |
| **Fal** | — | — | ✅ | — | — | — | ✅ |

### 🏗️ Architecture

- **Any-to-any modality routing** — text→text, text→image, image→text, text→audio, audio→text, text→video, text→vector
- **Smart routing with auto-failover** — latency-aware provider ranking, automatic fallback to next provider on failure
- **Response caching** — exact-match cache with per-user partitioning, `X-Cache` headers
- **Pipeline engine** — multi-hop conversions when no single provider can fulfill the route
- **BYOK (Bring Your Own Key)** — users store their own API keys, encrypted with rotatable Fernet keys
- **Streaming-first** — SSE and WebSocket with heartbeat keepalive
- **Auto-discovery** — add a new provider by creating `app/providers/<name>/adapter.py` — zero import changes

### 🔒 Security

- **MultiFernet key rotation** — rotate encryption keys with zero downtime
- **JWT with revocation** — token blacklisting via Redis, `jti` claim for per-token revocation
- **In-process key cache** — decrypted API keys never leave the process boundary (no Redis plaintext)
- **Password strength validation** — minimum length, uppercase, lowercase, digit, special character
- **Account lockout** — configurable failed login threshold with automatic unlock
- **Audit logging** — records security-sensitive actions (login, logout, key CRUD)

### 📊 Observability

- **Prometheus metrics** — `/metrics` endpoint with request counts, latency histograms, token usage, cost tracking
- **Request ID propagation** — `X-Request-ID` header bound to structured logs via structlog
- **OpenTelemetry tracing** — OTLP exporter for Jaeger/Tempo in production
- **Deep health check** — `/health` pings Postgres, Redis, and reports loaded providers

### 🛡️ Guardrails

- **Prompt injection detection** — 10+ regex patterns for common jailbreak attempts
- **PII detection & redaction** — email, phone, SSN, credit card patterns
- **Input length limits** — per-tier enforcement (free/pro/enterprise)
- **Post-response checks** — PII leak detection in responses

### 💰 Cost & Usage

- **Per-request cost estimation** — real-time cost tracking per provider/model
- **Usage analytics API** — `GET /usage/summary`, `GET /usage/daily`, `GET /usage/budget`
- **Monthly budgets** — configurable per-user spend limits
- **Token counting** — tiktoken-based for OpenAI-compatible models

### 🔧 Admin API

- `GET /admin/users` — list all users with roles and tiers
- `GET /admin/providers/health` — circuit breaker status, model count per provider
- `POST /admin/providers/{name}/disable` — manually open circuit breaker
- `GET /admin/stats` — system-wide metrics

---

## 🐳 Quick Start

### Prerequisites

- **Docker** & **Docker Compose**
- **Python 3.12+** (for local development)
- At least one provider API key (or [Ollama](https://ollama.com) for free local inference)

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/Ultimate-Assistant-AI-Gateway-Backend.git
cd Ultimate-Assistant-AI-Gateway-Backend
cp .env.example .env
```

Generate an encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste it into `.env` as `MASTER_ENCRYPTION_KEYS=<your-key>`.

### 2. Start with Docker

```bash
docker compose up -d --build
```

This starts:
- **App** on `http://localhost:8000`
- **PostgreSQL** on `localhost:5432`
- **Redis** on `localhost:6379`
- **MinIO** (S3) on `localhost:9000`
- **ARQ worker** for background jobs

### 3. Verify

```bash
curl http://localhost:8000/health
```

Expected:
```json
{
  "service": "ultimate-assistant",
  "version": "0.2.0",
  "redis": "ok",
  "postgres": "ok",
  "providers_loaded": 13,
  "status": "healthy"
}
```

### 4. Use the API

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "MyStr0ng!Pass"}'

# Add your API key (BYOK)
curl -X POST http://localhost:8000/api/v1/keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "label": "my-key"}'

# Chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## 🦙 Ollama Support (Local LLMs)

Run any open-source LLM locally through the gateway — **no API key required**.

### Setup

1. [Install Ollama](https://ollama.com/download)
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Add "ollama" as a provider key in the gateway (use any string as the API key):
   ```bash
   curl -X POST http://localhost:8000/api/v1/keys \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"provider": "ollama", "api_key": "ollama", "label": "local"}'
   ```
4. Chat with local models:
   ```bash
   curl -X POST http://localhost:8000/api/v1/chat \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "provider": "ollama",
       "model": "llama3.2",
       "messages": [{"role": "user", "content": "Explain quantum computing"}],
       "stream": false
     }'
   ```

### Supported Ollama Models

| Category | Models |
|----------|--------|
| **Chat** | llama3.2, llama3.1, llama3.1:70b, mistral, mistral-nemo, phi4, gemma3, gemma3:12b, qwen3, qwen3:8b, deepseek-r1, codellama, command-r |
| **Vision** | llava, llava:13b, llava-llama3, moondream |
| **Embeddings** | nomic-embed-text, mxbai-embed-large, all-minilm |

> 💡 Ollama models run locally, so costs are **$0.00** — perfect for development, testing, or private deployments.

---

## 🧭 Smart Routing & Failover

The gateway doesn't just pick the first available provider — it **ranks** them.

### How It Works

1. **Capability lookup** — find all providers that support the requested modality (e.g., text→text)
2. **BYOK filter** — only include providers the user has a key for
3. **Preference filter** — apply user's `provider` / `model` preference if specified
4. **Rank** — score candidates by: `p50_latency × (1 + error_rate) × cost_weight`
5. **Dispatch with failover** — try the top-ranked provider; if it fails, automatically try the next one

### Circuit Breaker

- Shared across workers via Redis
- **Closed → Open** after 5 consecutive failures
- **Open → Half-Open** after 30s recovery timeout (one probe request allowed)
- **Half-Open → Closed** if probe succeeds

---

## 🔐 Function Calling / Tool Use

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the weather in London?"}],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get current weather for a city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string"}
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "stream": false
  }'
```

---

## 📸🎵🎬 Media Input Reference

### Image Input

| Property | Details |
|----------|---------|
| **Endpoints** | `POST /images/vision` (URL), `POST /images/vision/upload` (file upload) |
| **Max file size** | **20 MB** |
| **Accepted formats** | PNG, JPEG, GIF, WebP, BMP, TIFF, SVG |
| **Accepted MIME types** | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/bmp`, `image/tiff`, `image/svg+xml` |
| **Input methods** | Public URL, base64 data URI, or multipart file upload |
| **Vision providers** | OpenAI (gpt-4o), Anthropic (Claude), Google (Gemini), Ollama (LLaVA, Moondream) |

```bash
# Via URL
curl -X POST http://localhost:8000/api/v1/images/vision \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://example.com/photo.jpg", "prompt": "What is in this image?"}'

# Via file upload
curl -X POST http://localhost:8000/api/v1/images/vision/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@photo.jpg" \
  -F "prompt=Describe this image"
```

#### Image Generation (Output)

| Property | Details |
|----------|---------|
| **Endpoint** | `POST /images/generate` |
| **Prompt limit** | 4000 characters |
| **Sizes** | `256x256`, `512x512`, `1024x1024`, `1792x1024`, `1024x1792` |
| **Quality** | `standard`, `hd` |
| **Batch** | 1–4 images per request |
| **Providers** | OpenAI (gpt-image-1), Stability, Fal, Replicate |

---

### Audio Input (STT — Speech to Text)

| Property | Details |
|----------|---------|
| **Endpoint** | `POST /audio/stt` |
| **Max file size** | **25 MB** |
| **Accepted formats** | MP3, MP4, M4A, WAV, WebM, OGG, FLAC, Opus |
| **Accepted MIME types** | `audio/mpeg`, `audio/mp4`, `audio/wav`, `audio/webm`, `audio/ogg`, `audio/flac`, `audio/x-m4a` |
| **Input method** | Multipart file upload only |
| **Language hint** | Optional ISO 639-1 code (e.g. `en`, `es`, `fr`) |
| **STT providers** | OpenAI (whisper-1), ElevenLabs |

```bash
curl -X POST http://localhost:8000/api/v1/audio/stt \
  -H "Authorization: Bearer <token>" \
  -F "file=@recording.mp3" \
  -F "language=en"
```

#### Audio Generation (TTS — Text to Speech)

| Property | Details |
|----------|---------|
| **Endpoint** | `POST /audio/tts` |
| **Max text length** | 4096 characters |
| **Output formats** | `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm` |
| **Voices** | alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer |
| **Speed** | 0.25x to 4.0x |
| **TTS providers** | OpenAI (tts-1, tts-1-hd), ElevenLabs |

---

### Video Input / Generation

| Property | Details |
|----------|---------|
| **Text→Video** | `POST /video/generate/text` |
| **Image→Video (URL)** | `POST /video/generate/image-to-video` |
| **Image→Video (upload)** | `POST /video/generate/image-to-video/upload` |
| **Max image size** | **20 MB** (for image→video) |
| **Image formats** | PNG, JPEG, WebP |
| **Max video duration** | 30s (text→video), 15s (image→video) |
| **Prompt limit** | 4000 characters |
| **Aspect ratios** | `16:9`, `9:16`, `1:1`, `4:3` |
| **Async** | ✅ Returns `job_id` immediately — poll `GET /video/jobs/{id}` |
| **Providers** | Replicate (Kling), Fal (MiniMax) |

```bash
# Text to video
curl -X POST http://localhost:8000/api/v1/video/generate/text \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cat walking on the moon", "duration": 5, "aspect_ratio": "16:9"}'

# Image to video (upload)
curl -X POST http://localhost:8000/api/v1/video/generate/image-to-video/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@landscape.jpg" \
  -F "prompt=Pan slowly across the landscape" \
  -F "duration=5"

# Check job status
curl http://localhost:8000/api/v1/video/jobs/<job_id> \
  -H "Authorization: Bearer <token>"
```

---

### File Upload

| Property | Details |
|----------|---------|
| **Endpoint** | `POST /files/upload` |
| **Max file size** | **50 MB** |
| **Documents** | PDF, DOCX, TXT, CSV, Markdown, JSON, HTML, XML |
| **Images** | PNG, JPEG, GIF, WebP, SVG, BMP, TIFF |
| **Audio** | MP3, WAV, WebM, OGG, FLAC, M4A, Opus |
| **Video** | MP4, WebM, MOV |
| **Archives** | ZIP, TAR, GZ |
| **Auto-parsing** | ✅ PDF, DOCX, TXT are auto-parsed for text extraction |
| **Storage** | S3 / MinIO with pre-signed download URLs |

---

### Chat Multimodal Input

Images can be sent inline in chat messages via the `content` array:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": "https://example.com/photo.jpg"}
      ]
    }],
    "stream": false
  }'
```

### Limits Summary

| Resource | Free Tier | Pro Tier | Enterprise |
|----------|-----------|----------|------------|
| **Image upload** | 20 MB | 20 MB | 20 MB |
| **Audio upload** | 25 MB | 25 MB | 25 MB |
| **File upload** | 50 MB | 50 MB | 50 MB |
| **Max input tokens** | 4,096 | 32,768 | 131,072 |
| **Rate limit** | 30 req/min | 300 req/min | 3,000 req/min |
| **Chat rate limit** | 20 req/min | 20 req/min | 20 req/min |

---

## 📊 Monitoring

### Prometheus Metrics

Available at `http://localhost:8000/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total HTTP requests by method, endpoint, status |
| `http_request_duration_seconds` | Histogram | HTTP request latency |
| `provider_requests_total` | Counter | Provider API calls by provider, model, status |
| `provider_request_duration_seconds` | Histogram | Provider API latency |
| `tokens_used_total` | Counter | Tokens consumed by provider, model, direction |
| `estimated_cost_usd_total` | Counter | Estimated API cost in USD |
| `cache_operations_total` | Counter | Cache hits and misses |
| `active_websocket_connections` | Gauge | Active WebSocket connections |
| `circuit_breaker_open` | Gauge | Circuit breaker state per provider |

### Request Tracing

Every request gets an `X-Request-ID` header (generated or propagated). All structured logs include this ID for easy correlation.

For production tracing, set `OTEL_EXPORTER_ENDPOINT` in `.env` to export spans to Jaeger or Tempo.

---

## 📁 Project Structure

```
app/
├── api/v1/
│   ├── routes/
│   │   ├── admin.py          # Admin dashboard API
│   │   ├── auth.py           # Register, login, refresh, logout
│   │   ├── chat.py           # Chat + streaming
│   │   ├── conversations.py  # Conversation history
│   │   ├── keys.py           # BYOK key management
│   │   ├── models.py         # List models + capabilities
│   │   ├── usage.py          # Usage analytics + budget
│   │   ├── images.py         # Image generation
│   │   ├── audio.py          # TTS + STT
│   │   ├── video.py          # Video generation
│   │   ├── embeddings.py     # Text embeddings
│   │   └── files.py          # File upload + parsing
│   ├── deps.py               # FastAPI dependencies
│   └── router.py             # Route aggregation
├── core/
│   ├── config.py             # Settings (env vars)
│   ├── security.py           # JWT, hashing, encryption, revocation
│   ├── middleware.py          # RequestID, logging, Prometheus
│   ├── ratelimit.py          # Tiered token-bucket rate limiter
│   ├── telemetry.py          # OpenTelemetry + Prometheus metrics
│   ├── exceptions.py         # Custom exception hierarchy
│   ├── lifespan.py           # Startup/shutdown lifecycle
│   └── logging.py            # Structlog configuration
├── providers/
│   ├── base.py               # BaseProvider + capability protocols
│   ├── capabilities.py       # Modality enum + capability map
│   ├── client_pool.py        # Shared httpx client pool (HTTP/2)
│   ├── registry.py           # Auto-discovery + provider registry
│   ├── retry.py              # Retry + Redis circuit breaker
│   ├── openai/               # OpenAI adapter
│   ├── anthropic/            # Anthropic adapter
│   ├── google/               # Google Gemini adapter
│   ├── ollama/               # 🆕 Ollama adapter (local LLMs)
│   ├── xai/                  # xAI (Grok) adapter
│   ├── mistral/              # Mistral adapter
│   ├── cohere/               # Cohere adapter
│   ├── groq/                 # Groq adapter
│   ├── deepseek/             # DeepSeek adapter
│   ├── elevenlabs/           # ElevenLabs adapter
│   ├── replicate/            # Replicate adapter
│   ├── stability/            # Stability AI adapter
│   └── fal/                  # Fal adapter
├── services/
│   ├── router.py             # Modality router with failover
│   ├── ranker.py             # 🆕 Latency/cost provider ranker
│   ├── chat_service.py       # Chat orchestration + cache + guardrails
│   ├── cache.py              # Response cache (per-user)
│   ├── cost_service.py       # 🆕 Cost estimation + budgets
│   ├── guardrails.py         # 🆕 Content safety (injection, PII)
│   ├── key_service.py        # BYOK key management
│   ├── usage_service.py      # Usage tracking + analytics
│   ├── pipeline.py           # Multi-hop conversion pipeline
│   ├── conversion_service.py # Any-to-any modality conversion
│   ├── streaming.py          # SSE + WebSocket streaming
│   └── file_service.py       # File upload + S3 + parsing
├── models/
│   ├── base.py               # Base model + SoftDeleteMixin
│   ├── user.py               # User (role, tier, budget)
│   ├── api_key.py            # Encrypted API keys
│   ├── conversation.py       # Conversation threads
│   ├── message.py            # Chat messages
│   ├── usage.py              # Usage records (indexed)
│   ├── audit_log.py          # 🆕 Security audit log
│   └── file.py               # File metadata
├── schemas/
│   ├── chat.py               # Multimodal messages + tool calling
│   ├── provider.py           # Unified request/response
│   ├── auth.py               # Auth schemas
│   ├── key.py                # Key schemas
│   ├── conversion.py         # Conversion schemas
│   └── file.py               # File schemas
├── db/
│   ├── session.py            # Async SQLAlchemy session
│   └── repositories/         # Data access layer
├── workers/                   # ARQ background tasks
├── utils/
│   ├── tokens.py             # Token counting + pricing
│   ├── ids.py                # ULID / UUID generators
│   └── time.py               # Time utilities
└── main.py                   # FastAPI app factory
```

---

## 🔧 Adding a New Provider

Thanks to auto-discovery, adding a provider requires **zero import changes**:

```bash
mkdir app/providers/my_provider
touch app/providers/my_provider/__init__.py
```

Create `app/providers/my_provider/adapter.py`:

```python
from app.providers.base import BaseProvider, ChatCapable
from app.providers.capabilities import Modality, ModalityPair
from app.schemas.provider import ModelInfo, UnifiedRequest, UnifiedResponse, Chunk

class MyProviderAdapter(BaseProvider, ChatCapable):
    name = "my_provider"
    base_url = "https://api.myprovider.com"

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {(Modality.TEXT, Modality.TEXT): ["my-model-v1"]}

    def get_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="my-model-v1", name="My Model", provider="my_provider", modalities=["text→text"])]

    async def chat(self, req, api_key):
        # Implement chat logic
        ...

    async def stream_chat(self, req, api_key):
        # Implement streaming
        ...
```

Add the base URL to `client_pool.py`:
```python
"my_provider": "https://api.myprovider.com",
```

That's it. The registry auto-discovers it at startup. ✅

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v --cov=app

# Lint
ruff check app/ tests/
mypy app/

# Run locally
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
