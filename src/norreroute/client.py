"""Client facade — sync and async wrappers over Provider."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from .provider import Provider
from .registry import resolve
from .streaming import StreamEvent
from .types import ChatRequest, ChatResponse

if TYPE_CHECKING:
    from .retry import RetryPolicy


class Client:
    """Provider-agnostic client for LLM chat completions.

    Accepts either a provider name (resolved via the registry) or a Provider
    instance directly. Exposes both async and sync interfaces.

    Note:
        ``chat_sync`` and ``stream_sync`` call ``asyncio.run`` / create a new
        event loop. They are unsuitable for use inside a running event loop
        (e.g. inside an async web handler). Use the async methods there instead.

    Args:
        provider: A provider name string (resolved via registry) or a Provider
                  instance.
        retry: Optional retry configuration. Pass a ``RetryPolicy`` instance for
               fine-grained control, ``True`` for default policy, or ``False``
               (default) to disable retries.
        **provider_kwargs: Keyword arguments forwarded to the provider factory
                           when ``provider`` is a string.
    """

    def __init__(
        self,
        provider: str | Provider,
        *,
        retry: RetryPolicy | bool = False,
        **provider_kwargs: object,
    ) -> None:
        self._provider: Provider = (
            provider
            if isinstance(provider, Provider)
            else resolve(provider, **provider_kwargs)
        )

        if retry is not False and retry is not None:
            from .retry import RetryingProvider
            from .retry import RetryPolicy as _RetryPolicy

            policy: RetryPolicy = (
                retry if isinstance(retry, _RetryPolicy) else _RetryPolicy()
            )
            self._provider = RetryingProvider(self._provider, policy)

    @property
    def provider_name(self) -> str:
        """Return the name of the underlying provider.

        Returns:
            The provider name string (e.g. ``"anthropic"`` or ``"ollama"``).
        """
        return self._provider.name

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request asynchronously.

        Args:
            request: The chat request to send.

        Returns:
            A ChatResponse containing the model's reply.
        """
        return await self._provider.chat(request)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Return an async iterator of streaming events for the request.

        Args:
            request: The chat request to stream.

        Returns:
            An async iterator of StreamEvent objects.
        """
        return self._provider.stream(request)

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        """Synchronous wrapper around ``chat``.

        Args:
            request: The chat request to send.

        Returns:
            A ChatResponse containing the model's reply.

        Raises:
            RuntimeError: If called from within a running event loop.
        """
        return asyncio.run(self._provider.chat(request))

    def stream_sync(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Synchronous wrapper around ``stream``.

        Yields StreamEvent objects from a new event loop.

        Args:
            request: The chat request to stream.

        Yields:
            StreamEvent objects as they arrive from the provider.
        """
        loop = asyncio.new_event_loop()
        agen = self._provider.stream(request).__aiter__()
        try:
            while True:
                try:
                    yield loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    return
        finally:
            loop.close()

    async def aclose(self) -> None:
        """Release the provider's underlying resources."""
        await self._provider.aclose()


__all__ = ["Client"]
