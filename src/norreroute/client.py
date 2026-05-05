"""Client facade — sync and async wrappers over Provider."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

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
        trace: Set to ``True`` to enable OpenTelemetry tracing (requires
               ``opentelemetry-api`` to be installed). Defaults to ``False``.
        tracer: Provide a custom OTel tracer object instead of the default one.
        **provider_kwargs: Keyword arguments forwarded to the provider factory
                           when ``provider`` is a string.
    """

    def __init__(
        self,
        provider: str | Provider,
        *,
        retry: RetryPolicy | bool = False,
        trace: bool = False,
        tracer: Any = None,
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

        # Resolve OTel tracer (None when tracing disabled)
        from .tracing import get_tracer

        self._tracer: Any = get_tracer(trace, tracer)

    @property
    def provider_name(self) -> str:
        """Return the name of the underlying provider.

        Returns:
            The provider name string (e.g. ``"anthropic"`` or ``"ollama"``).
        """
        return self._provider.name

    def _validate_request(self, request: ChatRequest) -> None:
        """Raise UnsupportedCapabilityError if the request uses unsupported features.

        Currently checks for ImagePart presence when the provider does not
        declare ``supports_vision = True``.
        """
        from .errors import UnsupportedCapabilityError
        from .types import ImagePart

        has_images = any(
            isinstance(part, ImagePart)
            for msg in request.messages
            for part in msg.content
        )
        if has_images and not getattr(self._provider, "supports_vision", True):
            raise UnsupportedCapabilityError("vision", provider=self._provider.name)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request asynchronously.

        Args:
            request: The chat request to send.

        Returns:
            A ChatResponse containing the model's reply.
        """
        self._validate_request(request)
        from .tracing import _set_response_attributes, chat_span

        with chat_span(self._tracer, request) as _span_ctx:
            response = await self._provider.chat(request)
            if self._tracer is not None:
                # Set response attributes on the current span
                from opentelemetry import trace  # noqa: PLC0415

                span = trace.get_current_span()
                _set_response_attributes(span, response)
            return response

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Internal generator that delegates to the provider's stream."""
        async for event in self._provider.stream(request):
            yield event

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Return an async iterator of streaming events for the request.

        Args:
            request: The chat request to stream.

        Returns:
            An async iterator of StreamEvent objects.
        """
        self._validate_request(request)
        if self._tracer is None:
            return self._provider.stream(request)
        return self._traced_stream(request)

    async def _traced_stream(  # noqa: E501
        self, request: ChatRequest
    ) -> AsyncIterator[StreamEvent]:
        """Async generator that wraps streaming in an OTel span.

        Manages the span lifecycle manually (start/end) rather than using
        start_as_current_span as a context manager across a yield boundary.
        This avoids OTel context-token errors that occur when async generator
        cleanup runs in a different asyncio Task context (e.g., on early break).
        """
        from opentelemetry.trace import StatusCode  # noqa: PLC0415

        span = self._tracer.start_span("norreroute.stream")
        span.set_attribute("gen_ai.system", "norreroute")
        span.set_attribute("gen_ai.request.model", request.model)
        if request.max_tokens is not None:
            span.set_attribute("gen_ai.request.max_tokens", request.max_tokens)
        if request.temperature is not None:
            span.set_attribute("gen_ai.request.temperature", request.temperature)

        try:
            async for event in self._provider.stream(request):
                yield event
        except Exception as exc:
            span.set_status(StatusCode.ERROR)
            span.record_exception(exc)
            raise
        finally:
            span.end()

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        """Synchronous wrapper around ``chat``.

        Args:
            request: The chat request to send.

        Returns:
            A ChatResponse containing the model's reply.

        Raises:
            RuntimeError: If called from within a running event loop.
        """
        return asyncio.run(self.chat(request))

    def stream_sync(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Synchronous wrapper around ``stream``.

        Yields StreamEvent objects from a new event loop.

        Args:
            request: The chat request to stream.

        Yields:
            StreamEvent objects as they arrive from the provider.
        """
        loop = asyncio.new_event_loop()
        agen = self.stream(request).__aiter__()
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
