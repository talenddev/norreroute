"""Tests for UnsupportedCapabilityError and Client capability guard — TASK-4."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from norreroute import UnsupportedCapabilityError
from norreroute.client import Client
from norreroute.errors import AIProxyError
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import (
    ChatRequest,
    ChatResponse,
    ImagePart,
    Message,
    TextPart,
    Usage,
)

# ---------------------------------------------------------------------------
# Stub providers
# ---------------------------------------------------------------------------


class _NoVisionProvider:
    """Stub provider that explicitly does not support vision."""

    name = "no-vision"
    supports_vision: bool = False

    async def chat(self, request: ChatRequest) -> ChatResponse:  # pragma: no cover
        raise AssertionError("chat should not be called")

    async def _stream_gen(self) -> AsyncIterator[StreamEvent]:
        raise AssertionError("stream should not be called")  # pragma: no cover
        yield  # make it a generator

    def stream(  # pragma: no cover
        self, request: ChatRequest
    ) -> AsyncIterator[StreamEvent]:
        raise AssertionError("stream should not be called")

    async def aclose(self) -> None:
        pass


class _VisionProvider:
    """Stub provider that supports vision."""

    name = "vision-ok"
    supports_vision: bool = True

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            model="vision-ok",
            content=[TextPart(text="ok")],
            finish_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
            raw={},
        )

    async def _stream_gen(self) -> AsyncIterator[StreamEvent]:
        yield TextDelta(text="ok")
        yield StreamEnd(
            finish_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
        )

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._stream_gen()

    async def aclose(self) -> None:
        pass


class _TextOnlyProvider:
    """Stub provider with no supports_vision attribute (defaults to True)."""

    name = "text-only"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            model="text-only",
            content=[TextPart(text="ok")],
            finish_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
            raw={},
        )

    def stream(  # pragma: no cover
        self, request: ChatRequest
    ) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# UnsupportedCapabilityError
# ---------------------------------------------------------------------------


def test_unsupported_capability_error_fields() -> None:
    err = UnsupportedCapabilityError("vision", provider="ollama")
    assert err.capability == "vision"
    assert err.provider == "ollama"
    assert "ollama" in str(err)
    assert "vision" in str(err)


def test_unsupported_capability_error_is_aiproxy_error() -> None:
    err = UnsupportedCapabilityError("vision", provider="test")
    assert isinstance(err, AIProxyError)


def test_unsupported_capability_error_message_format() -> None:
    err = UnsupportedCapabilityError("vision", provider="my-provider")
    assert str(err) == "Provider 'my-provider' does not support capability 'vision'"


def test_unsupported_capability_error_exported_from_top_level() -> None:
    from norreroute import UnsupportedCapabilityError as UCE  # noqa: PLC0415

    assert UCE is UnsupportedCapabilityError


# ---------------------------------------------------------------------------
# Client capability guard — chat()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_raises_when_provider_lacks_vision() -> None:
    client = Client(_NoVisionProvider())  # type: ignore[arg-type]
    request = ChatRequest(
        model="no-vision",
        messages=[Message(role="user", content=[ImagePart(data=b"\xff\xd8")])],
    )
    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await client.chat(request)
    assert exc_info.value.provider == "no-vision"
    assert exc_info.value.capability == "vision"


@pytest.mark.asyncio
async def test_client_guard_fires_before_any_http_call() -> None:
    """Guard must raise before provider.chat() is ever invoked."""
    chat_called = False

    class _TrackingNoVisionProvider(_NoVisionProvider):
        async def chat(self, request: ChatRequest) -> ChatResponse:  # type: ignore[override]
            nonlocal chat_called
            chat_called = True
            raise AssertionError("should not be reached")

        def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
            raise AssertionError("should not be reached")

    client = Client(_TrackingNoVisionProvider())  # type: ignore[arg-type]
    request = ChatRequest(
        model="mock",
        messages=[Message(role="user", content=[ImagePart(data=b"\xff\xd8")])],
    )
    with pytest.raises(UnsupportedCapabilityError):
        await client.chat(request)

    assert not chat_called, "provider.chat() should not have been called"


@pytest.mark.asyncio
async def test_client_passes_through_when_no_image_part() -> None:
    client = Client(_NoVisionProvider())  # type: ignore[arg-type]
    # Replace _NoVisionProvider.chat to return a real response
    async def _mock_chat(request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            model="no-vision",
            content=[TextPart(text="hello")],
            finish_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
            raw={},
        )

    client._provider.chat = _mock_chat  # type: ignore[method-assign]
    request = ChatRequest(
        model="no-vision",
        messages=[Message(role="user", content=[TextPart(text="hello")])],
    )
    response = await client.chat(request)
    assert response.text == "hello"


@pytest.mark.asyncio
async def test_client_passes_through_when_provider_supports_vision() -> None:
    client = Client(_VisionProvider())  # type: ignore[arg-type]
    request = ChatRequest(
        model="vision-ok",
        messages=[Message(role="user", content=[ImagePart(data=b"\xff\xd8")])],
    )
    response = await client.chat(request)
    assert response.text == "ok"


# ---------------------------------------------------------------------------
# Client capability guard — stream()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_stream_raises_when_provider_lacks_vision() -> None:
    client = Client(_NoVisionProvider())  # type: ignore[arg-type]
    request = ChatRequest(
        model="no-vision",
        messages=[Message(role="user", content=[ImagePart(data=b"\xff\xd8")])],
    )
    with pytest.raises(UnsupportedCapabilityError):
        # stream() is synchronous but the guard is sync too — should raise immediately
        async for _ in client.stream(request):
            pass


# ---------------------------------------------------------------------------
# RetryingProvider propagates supports_vision
# ---------------------------------------------------------------------------


def test_capability_guard_works_through_retry_wrapper() -> None:
    from norreroute.retry import RetryingProvider, RetryPolicy  # noqa: PLC0415

    inner = _NoVisionProvider()
    retrying = RetryingProvider(inner, RetryPolicy())  # type: ignore[arg-type]
    assert retrying.supports_vision is False


def test_retry_wrapper_propagates_supports_vision_true() -> None:
    from norreroute.retry import RetryingProvider, RetryPolicy  # noqa: PLC0415

    inner = _VisionProvider()
    retrying = RetryingProvider(inner, RetryPolicy())  # type: ignore[arg-type]
    assert retrying.supports_vision is True


def test_default_supports_vision_true_for_unknown_attribute() -> None:
    from norreroute.retry import RetryingProvider, RetryPolicy  # noqa: PLC0415

    inner = _TextOnlyProvider()
    retrying = RetryingProvider(inner, RetryPolicy())  # type: ignore[arg-type]
    # No supports_vision on inner — should default to True
    assert retrying.supports_vision is True


@pytest.mark.asyncio
async def test_client_with_retry_raises_when_provider_lacks_vision() -> None:
    from norreroute.retry import RetryPolicy  # noqa: PLC0415

    client = Client(
        _NoVisionProvider(),  # type: ignore[arg-type]
        retry=RetryPolicy(),
    )
    request = ChatRequest(
        model="no-vision",
        messages=[Message(role="user", content=[ImagePart(data=b"\xff\xd8")])],
    )
    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        await client.chat(request)
    assert exc_info.value.provider == "no-vision"
