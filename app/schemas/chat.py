"""Chat schemas — multimodal messages, function calling, tool use."""

from typing import Literal

from pydantic import BaseModel, Field


# ── Multimodal content parts ─────────────────────────


class ContentPart(BaseModel):
    """A single part of a multimodal message."""
    type: Literal["text", "image_url", "audio", "file"] = "text"
    text: str | None = None
    image_url: str | None = None
    audio_url: str | None = None
    file_id: str | None = None


# ── Function / tool calling ──────────────────────────


class FunctionDef(BaseModel):
    name: str
    description: str = ""
    parameters: dict | None = None  # JSON Schema


class ToolDef(BaseModel):
    type: str = "function"
    function: FunctionDef


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: dict  # {"name": ..., "arguments": ...}


# ── Messages ─────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str | list[ContentPart] | None = None
    name: str | None = None  # for tool messages
    tool_calls: list[ToolCall] | None = None  # for assistant messages with tool calls
    tool_call_id: str | None = None  # for tool result messages


# ── Request / Response ───────────────────────────────


class ChatRequest(BaseModel):
    model: str | None = None
    provider: str | None = None
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = True
    conversation_id: str | None = None
    # Function / tool calling
    tools: list[ToolDef] | None = None
    tool_choice: str | dict | None = None  # "auto", "none", or {"type": "function", "function": {"name": "..."}}
    # Cache control
    bypass_cache: bool = False


class ChatChunk(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    finish_reason: str | None = None
    model: str | None = None
    provider: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatResponse(BaseModel):
    id: str
    content: str
    role: str = "assistant"
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    tool_calls: list[ToolCall] | None = None
    cached: bool = False
