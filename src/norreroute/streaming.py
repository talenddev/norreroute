"""Neutral streaming event types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .types import Usage


@dataclass(frozen=True)
class TextDelta:
    """A chunk of streamed text content."""

    text: str
    type: Literal["text_delta"] = "text_delta"


@dataclass(frozen=True)
class ToolCallDelta:
    """A chunk of a streamed tool call (name/arguments may arrive in pieces)."""

    id: str
    name: str | None  # may arrive in chunks
    arguments_json: str  # accumulating JSON fragment
    type: Literal["tool_call_delta"] = "tool_call_delta"


@dataclass(frozen=True)
class StreamEnd:
    """Signals the end of a streaming response."""

    finish_reason: str
    usage: Usage | None
    type: Literal["end"] = "end"


StreamEvent = TextDelta | ToolCallDelta | StreamEnd

__all__ = [
    "TextDelta",
    "ToolCallDelta",
    "StreamEnd",
    "StreamEvent",
]
