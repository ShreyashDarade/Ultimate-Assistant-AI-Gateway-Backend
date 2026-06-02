"""Provider-agnostic schemas — strongly typed unified request/response."""

from pydantic import BaseModel


class UnifiedMessage(BaseModel):
    """Strongly typed message for provider adapters."""
    role: str
    content: str | list[dict] | None = None
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class UnifiedRequest(BaseModel):
    """Provider-agnostic request that all adapters accept."""
    prompt: str | None = None
    messages: list[dict] | None = None
    model: str | None = None
    max_tokens: int | None = None
    temperature: float = 0.7
    stream: bool = False
    input_url: str | None = None  # for media inputs (image/audio/video URL)
    input_data: bytes | None = None  # for raw binary inputs
    options: dict | None = None
    # Function / tool calling
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None


class UnifiedResponse(BaseModel):
    content: str | None = None
    file_url: str | None = None
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    tool_calls: list[dict] | None = None


class MediaResult(BaseModel):
    file_url: str
    mime_type: str
    model: str
    provider: str
    latency_ms: int | None = None


class Chunk(BaseModel):
    content: str
    finish_reason: str | None = None
    model: str | None = None
    tool_calls: list[dict] | None = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    modalities: list[str]  # ["text→text", "text→image", ...]
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True


class ProviderInfo(BaseModel):
    name: str
    models: list[ModelInfo]
    capabilities: list[str]
    status: str = "healthy"  # healthy / degraded / unavailable
