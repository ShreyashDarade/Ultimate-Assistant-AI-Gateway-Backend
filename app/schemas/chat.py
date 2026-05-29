from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    provider: str | None = None
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = True
    conversation_id: str | None = None


class ChatChunk(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    finish_reason: str | None = None
    model: str | None = None
    provider: str | None = None


class ChatResponse(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
