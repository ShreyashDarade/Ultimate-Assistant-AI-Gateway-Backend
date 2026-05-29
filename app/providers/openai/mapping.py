"""OpenAI request/response ↔ unified schema mapping."""

from app.schemas.provider import Chunk, UnifiedRequest, UnifiedResponse


def to_chat_request(req: UnifiedRequest, model: str | None = None) -> dict:
    return {
        "model": model or req.model or "gpt-4o",
        "messages": req.messages or [{"role": "user", "content": req.prompt}],
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "stream": req.stream,
    }


def from_chat_response(data: dict) -> UnifiedResponse:
    choice = data["choices"][0]
    usage = data.get("usage", {})
    return UnifiedResponse(
        content=choice["message"]["content"],
        model=data.get("model"),
        provider="openai",
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


def from_stream_chunk(data: dict) -> Chunk | None:
    if not data.get("choices"):
        return None
    delta = data["choices"][0].get("delta", {})
    content = delta.get("content", "")
    if not content and not data["choices"][0].get("finish_reason"):
        return None
    return Chunk(
        content=content or "",
        finish_reason=data["choices"][0].get("finish_reason"),
        model=data.get("model"),
    )


def to_image_request(req: UnifiedRequest, model: str | None = None) -> dict:
    return {
        "model": model or req.model or "gpt-image-1",
        "prompt": req.prompt,
        "n": 1,
        "size": req.options.get("size", "1024x1024") if req.options else "1024x1024",
    }


def to_tts_request(req: UnifiedRequest, model: str | None = None) -> dict:
    return {
        "model": model or req.model or "tts-1",
        "input": req.prompt,
        "voice": req.options.get("voice", "alloy") if req.options else "alloy",
        "response_format": req.options.get("format", "mp3") if req.options else "mp3",
    }


def to_stt_request(req: UnifiedRequest, model: str | None = None) -> dict:
    return {
        "model": model or req.model or "whisper-1",
    }


def to_embedding_request(req: UnifiedRequest, model: str | None = None) -> dict:
    return {
        "model": model or req.model or "text-embedding-3-small",
        "input": req.prompt or (req.messages[-1]["content"] if req.messages else ""),
    }


def to_vision_request(req: UnifiedRequest, model: str | None = None) -> dict:
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
        "model": model or req.model or "gpt-4o",
        "messages": messages,
        "max_tokens": req.max_tokens or 1000,
    }
