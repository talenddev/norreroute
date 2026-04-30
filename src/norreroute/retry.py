"""Retry policy and retrying provider wrapper."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from ._internal import full_jitter
from .errors import ProviderError, RateLimitError
from .provider import Provider
from .streaming import StreamEvent, TextDelta, ToolCallDelta
from .types import ChatRequest, ChatResponse


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for retry behaviour on transient errors.

    Attributes:
        max_attempts: Total number of attempts (including the first call).
        initial_delay: Starting delay in seconds before the first retry.
        max_delay: Maximum cap on the pre-jitter delay window.
        multiplier: Exponential backoff multiplier applied per attempt.
        jitter: Fraction of delay to randomise (0..1). Kept for interface
            compatibility; the actual randomisation is full-jitter (uniform
            over the capped window), not a fraction of the deterministic delay.
        retry_on: Tuple of exception types that trigger a retry.
    """

    max_attempts: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.25
    retry_on: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (RateLimitError, ProviderError)
    )

    def should_retry(self, exc: BaseException, attempt: int) -> bool:
        """Return True if the exception is retryable and attempts remain.

        Args:
            exc: The exception raised by the provider.
            attempt: 1-based attempt number of the call that just failed.

        Returns:
            True if a retry should be made.
        """
        return isinstance(exc, self.retry_on) and attempt < self.max_attempts

    def delay_for(self, attempt: int) -> float:
        """Compute the sleep duration before the next attempt.

        Uses AWS full-jitter: uniform(0, min(max_delay, initial * mult**attempt)).

        Args:
            attempt: 1-based attempt number of the call that just failed
                (so the next attempt will be attempt+1).

        Returns:
            Seconds to sleep.
        """
        return full_jitter(
            self.initial_delay,
            self.multiplier,
            self.max_delay,
            attempt,
        )


class RetryingProvider:
    """Wraps a Provider and retries transient failures per a RetryPolicy.

    Satisfies the Provider Protocol so it can be used anywhere a Provider is
    accepted.

    Args:
        inner: The underlying Provider to delegate calls to.
        policy: The RetryPolicy governing retry behaviour.
        sleep: Injectable sleep callable (default: asyncio.sleep). Override in
            tests to avoid actual sleeps.
    """

    def __init__(
        self,
        inner: Provider,
        policy: RetryPolicy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._sleep = sleep
        # Expose name as a plain attribute to satisfy the Provider Protocol
        self.name: str = inner.name

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat request with retry on transient errors.

        Args:
            request: The chat request to send.

        Returns:
            The first successful ChatResponse.

        Raises:
            The last exception if all attempts are exhausted or the error is
            not retryable.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                return await self._inner.chat(request)
            except BaseException as exc:
                if not self._policy.should_retry(exc, attempt):
                    raise
                delay = self._policy.delay_for(attempt)
                await self._sleep(delay)

    async def _stream_with_retry(  # noqa: E501
        self, request: ChatRequest
    ) -> AsyncIterator[StreamEvent]:
        """Async generator implementing stream-with-retry semantics.

        Retries only before the first content event (TextDelta or ToolCallDelta)
        is yielded. After the first such event, errors propagate without retry.
        """
        attempt = 0
        while True:
            attempt += 1
            first_yielded = False
            # Obtain the async generator so we can call aclose() on it
            agen: AsyncGenerator[StreamEvent, None] = self._inner.stream(request)  # type: ignore[assignment]
            try:
                # Peek the first event inside the retry boundary
                try:
                    first_event: StreamEvent = await agen.__anext__()
                except StopAsyncIteration:
                    return

                # If first event is a content event, we are past the retry boundary
                if isinstance(first_event, (TextDelta, ToolCallDelta)):
                    first_yielded = True

                yield first_event

                # Stream the rest; retry boundary is now closed
                async for event in agen:
                    yield event
                return

            except BaseException as exc:
                if first_yielded:
                    # Already emitted content to caller — cannot retry
                    raise
                with contextlib.suppress(Exception):
                    await agen.aclose()
                if not self._policy.should_retry(exc, attempt):
                    raise
                delay = self._policy.delay_for(attempt)
                await self._sleep(delay)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Return an async iterator of streaming events with retry support.

        Args:
            request: The chat request to stream.

        Returns:
            An async iterator of StreamEvent objects.
        """
        return self._stream_with_retry(request)

    async def aclose(self) -> None:
        """Release the inner provider's resources."""
        await self._inner.aclose()


__all__ = ["RetryPolicy", "RetryingProvider"]
