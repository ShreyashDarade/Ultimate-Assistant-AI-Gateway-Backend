"""Ollama request/response ↔ unified schema mapping.

Ollama exposes an OpenAI-compatible API at /v1/chat/completions,
plus its native API at /api/chat and /api/embeddings.
We use the OpenAI-compatible endpoints for simplicity.
"""

from app.schemas.provider import Chunk, UnifiedRequest, UnifiedResponse


def to_chat_request(req: UnifiedRequest, model: str | None = None) -> dict:
    """Build an Ollama-compatible chat request (OpenAI format)."""
    return {
        "model": model or req.model or "llama3.2",
        "messages": req.messages or [{"role": "user", "content": req.prompt}],
        "temperature": req.temperature,
        "stream": req.stream,
        **({"max_tokens": req.max_tokens} if req.max_tokens else {}),
        **({"tools": req.tools} if req.tools else {}),
    }


def from_chat_response(data: dict) -> UnifiedResponse:
    """Parse a non-streaming Ollama chat response (OpenAI format)."""
    choice = data["choices"][0]
    usage = data.get("usage", {})
    message = choice.get("message", {})

    return UnifiedResponse(
        content=message.get("content"),
        model=data.get("model"),
        provider="ollama",
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        tool_calls=message.get("tool_calls"),
    )


def from_stream_chunk(data: dict) -> Chunk | None:
    """Parse a streaming chunk (OpenAI SSE format)."""
    if not data.get("choices"):
        return None
    delta = data["choices"][0].get("delta", {})
    content = delta.get("content", "")
    finish_reason = data["choices"][0].get("finish_reason")
    if not content and not finish_reason:
        return None
    return Chunk(
        content=content or "",
        finish_reason=finish_reason,
        model=data.get("model"),
        tool_calls=delta.get("tool_calls"),
    )


def to_embedding_request(req: UnifiedRequest, model: str | None = None) -> dict:
    """Build an Ollama embedding request (OpenAI format)."""
    return {
        "model": model or req.model or "nomic-embed-text",
        "input": req.prompt or (req.messages[-1]["content"] if req.messages else ""),
    }


def to_vision_request(req: UnifiedRequest, model: str | None = None) -> dict:
    """Build a vision request — Ollama supports images via base64 in messages."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": req.prompt or "Describe this image"},
                {"type": "image_url", "image_url": {"url": req.input_url}},
            ],
        }
    ]
    return {
        "model": model or req.model or "llava",
        "messages": messages,
        "max_tokens": req.max_tokens or 1000,
    }
