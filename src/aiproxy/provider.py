"""Provider protocol definition."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from .streaming import StreamEvent
from .types import ChatRequest, ChatResponse


@runtime_checkable
class Provider(Protocol):
    """Protocol that all LLM provider implementations must satisfy.

    Providers are async-only. Sync wrappers live in the Client facade.
    """

    name: str  # e.g. "anthropic", "ollama"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request and return a complete response."""
        ...

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Send a chat completion request and stream events as they arrive."""
        ...

    async def aclose(self) -> None:
        """Release underlying resources (e.g. httpx client connections)."""
        ...


__all__ = ["Provider"]
