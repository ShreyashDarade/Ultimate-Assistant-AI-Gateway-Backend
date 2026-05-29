from pydantic import BaseModel


class ConversionRequest(BaseModel):
    input: str  # text prompt, or file_id for media
    input_modality: str = "text"
    output_modality: str = "image"
    model: str | None = None
    provider: str | None = None
    options: dict | None = None


class ConversionResponse(BaseModel):
    id: str
    output: str  # text content or file_url
    output_modality: str
    model: str
    provider: str
    latency_ms: int | None = None
    file_id: str | None = None
