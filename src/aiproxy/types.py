"""Core domain model — frozen dataclasses, no Pydantic."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class TextPart:
    """A plain text content block."""

    text: str
    type: Literal["text"] = "text"


@dataclass(frozen=True)
class ToolUsePart:
    """A tool invocation block emitted by the model."""

    id: str
    name: str
    arguments: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"


@dataclass(frozen=True)
class ToolResultPart:
    """The result of a tool invocation, sent back to the model."""

    tool_use_id: str
    content: str  # JSON-encoded result or plain text
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"


ContentPart = TextPart | ToolUsePart | ToolResultPart


@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""

    role: Role
    content: Sequence[ContentPart]


@dataclass(frozen=True)
class ToolSpec:
    """Specification for a callable tool the model may invoke."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ChatRequest:
    """A provider-agnostic chat completion request."""

    model: str
    messages: Sequence[Message]
    system: str | None = None  # Anthropic-style top-level system prompt
    tools: Sequence[ToolSpec] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    stop: Sequence[str] = ()
    # provider-specific escape hatch
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    """Token usage statistics."""

    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ChatResponse:
    """A provider-agnostic chat completion response."""

    model: str
    content: Sequence[ContentPart]  # may include ToolUsePart
    finish_reason: Literal["stop", "length", "tool_use", "error"]
    usage: Usage
    raw: dict[str, Any]  # untouched provider payload for debugging


__all__ = [
    "Role",
    "TextPart",
    "ToolUsePart",
    "ToolResultPart",
    "ContentPart",
    "Message",
    "ToolSpec",
    "ChatRequest",
    "Usage",
    "ChatResponse",
]
