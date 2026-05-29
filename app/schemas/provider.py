from pydantic import BaseModel


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


class UnifiedResponse(BaseModel):
    content: str | None = None
    file_url: str | None = None
    model: str | None = None
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


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


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    modalities: list[str]  # ["text→text", "text→image", ...]
    context_window: int | None = None
    max_output_tokens: int | None = None


class ProviderInfo(BaseModel):
    name: str
    models: list[ModelInfo]
    capabilities: list[str]
