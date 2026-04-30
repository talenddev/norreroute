"""Unit tests for retry.py — RetryPolicy, RetryingProvider, and Client wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from norreroute.client import Client
from norreroute.errors import AuthenticationError, ProviderError, RateLimitError
from norreroute.retry import RetryingProvider, RetryPolicy
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta, ToolCallDelta
from norreroute.types import ChatRequest, ChatResponse, Message, TextPart, Usage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request() -> ChatRequest:
    return ChatRequest(
        model="test-model",
        messages=[Message(role="user", content=[TextPart(text="hello")])],
    )


def _make_response() -> ChatResponse:
    return ChatResponse(
        model="test-model",
        content=[TextPart(text="pong")],
        finish_reason="stop",
        usage=Usage(input_tokens=5, output_tokens=5),
        raw={},
    )


class FakeProvider:
    """Scripted provider for testing retry logic.

    chat_sequence: list of Exception instances or ChatResponse objects.
                  Each call to chat() pops the next item.
    stream_sequences: list of sequences; each call to stream() pops the next
                      sequence and yields/raises items in it.
    """

    name = "fake"

    def __init__(
        self,
        chat_sequence: list[Any] | None = None,
        stream_sequences: list[list[Any]] | None = None,
    ) -> None:
        self._chat_seq: list[Any] = list(chat_sequence or [])
        self._stream_seqs: list[list[Any]] = list(stream_sequences or [])
        self.chat_calls = 0
        self.stream_calls = 0
        self.aclose_calls = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.chat_calls += 1
        item = self._chat_seq.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item  # type: ignore[return-value]

    async def _stream_gen(self, sequence: list[Any]) -> AsyncIterator[StreamEvent]:
        for item in sequence:
            if isinstance(item, BaseException):
                raise item
            yield item  # type: ignore[misc]

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.stream_calls += 1
        sequence = self._stream_seqs.pop(0)
        return self._stream_gen(sequence)

    async def aclose(self) -> None:
        self.aclose_calls += 1


# ---------------------------------------------------------------------------
# RetryPolicy unit tests
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_default_fields(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.initial_delay == 0.5
        assert policy.max_delay == 30.0
        assert policy.multiplier == 2.0
        assert policy.jitter == 0.25
        assert RateLimitError in policy.retry_on
        assert ProviderError in policy.retry_on

    def test_should_retry_retryable_within_limit(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        exc = RateLimitError("rate limit", provider="fake")
        assert policy.should_retry(exc, attempt=1) is True
        assert policy.should_retry(exc, attempt=2) is True

    def test_should_retry_false_at_limit(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        exc = RateLimitError("rate limit", provider="fake")
        assert policy.should_retry(exc, attempt=3) is False

    def test_should_retry_false_for_non_retryable(self) -> None:
        # AuthenticationError IS a ProviderError subclass, so the default policy
        # would retry it. Use a custom policy that only retries RateLimitError
        # to test the non-retryable path.
        policy = RetryPolicy(max_attempts=3, retry_on=(RateLimitError,))
        exc = AuthenticationError("auth", provider="fake")
        assert policy.should_retry(exc, attempt=1) is False

    def test_authentication_error_is_retryable_with_default_policy(self) -> None:
        # AuthenticationError extends ProviderError, so default policy retries it.
        policy = RetryPolicy(max_attempts=3)
        exc = AuthenticationError("auth", provider="fake")
        assert policy.should_retry(exc, attempt=1) is True

    def test_delay_for_is_non_negative(self) -> None:
        policy = RetryPolicy()
        for attempt in range(1, 6):
            delay = policy.delay_for(attempt)
            assert delay >= 0.0

    def test_delay_for_respects_max_delay(self) -> None:
        policy = RetryPolicy(initial_delay=1.0, multiplier=10.0, max_delay=5.0)
        # After several attempts the cap is 5.0, jitter gives [0, 5]
        for _ in range(20):
            assert policy.delay_for(10) <= 5.0

    def test_frozen_dataclass(self) -> None:
        policy = RetryPolicy()
        with pytest.raises(Exception):  # FrozenInstanceError
            policy.max_attempts = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RetryingProvider.chat tests
# ---------------------------------------------------------------------------

class TestRetryingProviderChat:
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self) -> None:
        resp = _make_response()
        provider = FakeProvider(chat_sequence=[resp])
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        retrying = RetryingProvider(provider, RetryPolicy(), sleep=fake_sleep)
        result = await retrying.chat(_make_request())
        assert result is resp
        assert provider.chat_calls == 1
        assert slept == []

    @pytest.mark.asyncio
    async def test_retries_twice_then_succeeds(self) -> None:
        resp = _make_response()
        provider = FakeProvider(
            chat_sequence=[
                RateLimitError("rl", provider="fake"),
                RateLimitError("rl", provider="fake"),
                resp,
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(
            max_attempts=3, initial_delay=1.0, multiplier=1.0, max_delay=10.0
        )
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        result = await retrying.chat(_make_request())
        assert result is resp
        assert provider.chat_calls == 3
        assert len(slept) == 2

    @pytest.mark.asyncio
    async def test_non_retryable_propagates_immediately(self) -> None:
        # Use a policy that only retries RateLimitError, so AuthenticationError
        # (not in retry_on) propagates immediately.
        provider = FakeProvider(
            chat_sequence=[AuthenticationError("auth", provider="fake")]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=5, retry_on=(RateLimitError,))
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        with pytest.raises(AuthenticationError):
            await retrying.chat(_make_request())
        assert provider.chat_calls == 1
        assert slept == []

    @pytest.mark.asyncio
    async def test_exhausted_retries_raises_last_error(self) -> None:
        provider = FakeProvider(
            chat_sequence=[
                RateLimitError("rl1", provider="fake"),
                RateLimitError("rl2", provider="fake"),
                RateLimitError("rl3", provider="fake"),
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=3)
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        with pytest.raises(RateLimitError):
            await retrying.chat(_make_request())
        assert provider.chat_calls == 3
        assert len(slept) == 2

    @pytest.mark.asyncio
    async def test_name_delegates_to_inner(self) -> None:
        provider = FakeProvider()
        retrying = RetryingProvider(provider, RetryPolicy())
        assert retrying.name == "fake"

    @pytest.mark.asyncio
    async def test_aclose_delegates_to_inner(self) -> None:
        provider = FakeProvider()
        retrying = RetryingProvider(provider, RetryPolicy())
        await retrying.aclose()
        assert provider.aclose_calls == 1


# ---------------------------------------------------------------------------
# RetryingProvider.stream tests
# ---------------------------------------------------------------------------

class TestRetryingProviderStream:
    @pytest.mark.asyncio
    async def test_stream_success_no_retry(self) -> None:
        delta = TextDelta(text="hello")
        end = StreamEnd(finish_reason="stop", usage=None)
        provider = FakeProvider(stream_sequences=[[delta, end]])
        retrying = RetryingProvider(provider, RetryPolicy())
        events = [e async for e in retrying.stream(_make_request())]
        assert events == [delta, end]
        assert provider.stream_calls == 1

    @pytest.mark.asyncio
    async def test_stream_retries_error_before_first_yield(self) -> None:
        """Error before any content event triggers retry."""
        delta = TextDelta(text="ok")
        end = StreamEnd(finish_reason="stop", usage=None)
        provider = FakeProvider(
            stream_sequences=[
                [RateLimitError("rl", provider="fake")],
                [delta, end],
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=3)
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        events = [e async for e in retrying.stream(_make_request())]
        assert events == [delta, end]
        assert provider.stream_calls == 2
        assert len(slept) == 1

    @pytest.mark.asyncio
    async def test_stream_error_after_first_yield_propagates(self) -> None:
        """Error after a TextDelta is yielded must NOT be retried."""
        delta = TextDelta(text="partial")
        provider = FakeProvider(
            stream_sequences=[
                [delta, ProviderError("mid-stream", provider="fake")],
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=5)
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)

        results: list[StreamEvent] = []
        with pytest.raises(ProviderError):
            async for event in retrying.stream(_make_request()):
                results.append(event)

        assert results == [delta]
        assert provider.stream_calls == 1
        assert slept == []

    @pytest.mark.asyncio
    async def test_stream_retry_on_error_before_tool_call_delta(self) -> None:
        """ToolCallDelta also counts as 'first content event'."""
        tcd = ToolCallDelta(id="1", name="fn", arguments_json='{"x":1}')
        end = StreamEnd(finish_reason="tool_use", usage=None)
        provider = FakeProvider(
            stream_sequences=[
                [RateLimitError("rl", provider="fake")],
                [tcd, end],
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=3)
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        events = [e async for e in retrying.stream(_make_request())]
        assert events[0] == tcd
        assert provider.stream_calls == 2

    @pytest.mark.asyncio
    async def test_stream_exhausted_retries_raises(self) -> None:
        provider = FakeProvider(
            stream_sequences=[
                [RateLimitError("rl", provider="fake")],
                [RateLimitError("rl", provider="fake")],
                [RateLimitError("rl", provider="fake")],
            ]
        )
        slept: list[float] = []

        async def fake_sleep(secs: float) -> None:
            slept.append(secs)

        policy = RetryPolicy(max_attempts=3)
        retrying = RetryingProvider(provider, policy, sleep=fake_sleep)
        with pytest.raises(RateLimitError):
            async for _ in retrying.stream(_make_request()):
                pass
        assert provider.stream_calls == 3
        assert len(slept) == 2


# ---------------------------------------------------------------------------
# Client wiring tests
# ---------------------------------------------------------------------------

class TestClientRetryWiring:
    def test_no_retry_kwarg_uses_bare_provider(self) -> None:
        """Client() without retry= must NOT wrap provider in RetryingProvider."""
        provider = FakeProvider()
        client = Client(provider=provider)
        assert not isinstance(client._provider, RetryingProvider)

    def test_retry_false_uses_bare_provider(self) -> None:
        provider = FakeProvider()
        client = Client(provider=provider, retry=False)
        assert not isinstance(client._provider, RetryingProvider)

    def test_retry_true_wraps_with_default_policy(self) -> None:
        provider = FakeProvider()
        client = Client(provider=provider, retry=True)
        assert isinstance(client._provider, RetryingProvider)

    def test_retry_policy_instance_wraps_correctly(self) -> None:
        provider = FakeProvider()
        policy = RetryPolicy(max_attempts=7)
        client = Client(provider=provider, retry=policy)
        assert isinstance(client._provider, RetryingProvider)
        assert client._provider._policy.max_attempts == 7  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_client_provider_name_with_retry(self) -> None:
        provider = FakeProvider()
        client = Client(provider=provider, retry=True)
        assert client.provider_name == "fake"

    @pytest.mark.asyncio
    async def test_client_provider_name_without_retry(self) -> None:
        provider = FakeProvider()
        client = Client(provider=provider)
        assert client.provider_name == "fake"
