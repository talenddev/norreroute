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
class ImagePart:
    """A binary image content block.

    Args:
        data: Raw image bytes (e.g. JPEG or PNG).
        media_type: MIME type of the image data. Providers that require
            base64 will encode ``data`` themselves during serialisation.
    """

    data: bytes
    media_type: str = "image/jpeg"
    type: Literal["image"] = "image"


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


ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart


@dataclass(frozen=True)
class Message:
    """A single message in a conversation."""

    role: Role
    content: Sequence[ContentPart]

    @classmethod
    def user(cls, text: str = "", *, images: Sequence[bytes] = ()) -> Message:
        """Convenience constructor for a user-role message.

        Args:
            text: The text prompt (optional if images are provided).
            images: Raw image bytes. Each item becomes an ``ImagePart``
                with ``media_type="image/jpeg"``.

        Returns:
            A ``Message`` with role ``"user"``.
        """
        parts: list[ContentPart] = []
        if text:
            parts.append(TextPart(text=text))
        for img in images:
            parts.append(ImagePart(data=img))
        return cls(role="user", content=parts)

    @classmethod
    def system(cls, text: str) -> Message:
        """Convenience constructor for a system-role message."""
        return cls(role="system", content=[TextPart(text=text)])


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

    @property
    def text(self) -> str:
        """Return the concatenated text of all TextPart content blocks.

        Returns an empty string if the response contains no TextPart
        (e.g. a pure tool-use response).
        """
        return "".join(p.text for p in self.content if isinstance(p, TextPart))


__all__ = [
    "Role",
    "TextPart",
    "ImagePart",
    "ToolUsePart",
    "ToolResultPart",
    "ContentPart",
    "Message",
    "ToolSpec",
    "ChatRequest",
    "Usage",
    "ChatResponse",
]
