"""Tests for aiproxy.client.Client facade."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

import aiproxy.registry as registry_module
from aiproxy.client import Client
from aiproxy.provider import Provider
from aiproxy.streaming import StreamEnd, StreamEvent, TextDelta
from aiproxy.types import ChatRequest, ChatResponse, Message, TextPart, Usage


# ---------------------------------------------------------------------------
# Concrete stub provider (must satisfy isinstance(..., Provider) check)
# ---------------------------------------------------------------------------


class _StubProvider:
    """A concrete provider stub whose isinstance check against Provider passes."""

    name = "test"

    def __init__(self, response: ChatResponse | None = None) -> None:
        self._response = response or ChatResponse(
            model="test-model",
            content=[TextPart(text="hello")],
            finish_reason="stop",
            usage=Usage(input_tokens=5, output_tokens=3),
            raw={},
        )
        self.closed = False

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return self._response

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield TextDelta(text="hello")
        yield StreamEnd(finish_reason="stop", usage=None)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._stream_impl(request)

    async def aclose(self) -> None:
        self.closed = True


def _make_request() -> ChatRequest:
    return ChatRequest(
        model="test-model",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )


# ---------------------------------------------------------------------------
# Fixture: isolate registry state
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_factories() -> None:
    original = dict(registry_module._FACTORIES)
    registry_module._FACTORIES.clear()
    yield
    registry_module._FACTORIES.clear()
    registry_module._FACTORIES.update(original)


# ---------------------------------------------------------------------------
# Tests — Provider instance injection
# ---------------------------------------------------------------------------


def test_client_accepts_provider_instance() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    assert isinstance(client._provider, _StubProvider)


async def test_client_chat_returns_response() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    response = await client.chat(_make_request())
    assert isinstance(response, ChatResponse)
    assert response.finish_reason == "stop"


async def test_client_stream_yields_events() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    events: list[StreamEvent] = []
    async for event in client.stream(_make_request()):
        events.append(event)
    assert any(isinstance(e, TextDelta) for e in events)
    assert isinstance(events[-1], StreamEnd)


async def test_client_aclose_calls_provider_aclose() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    await client.aclose()
    assert provider.closed is True


# ---------------------------------------------------------------------------
# Tests — Registry lookup by name
# ---------------------------------------------------------------------------


def test_client_resolves_provider_by_name() -> None:
    registry_module.register("test", lambda **kw: _StubProvider())
    client = Client("test")
    assert client._provider.name == "test"


def test_client_unknown_provider_raises() -> None:
    with pytest.raises(KeyError):
        Client("nonexistent")


# ---------------------------------------------------------------------------
# Tests — Sync wrappers
# ---------------------------------------------------------------------------


def test_chat_sync_returns_response() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    response = client.chat_sync(_make_request())
    assert isinstance(response, ChatResponse)
    assert response.content[0] == TextPart(text="hello")


def test_stream_sync_yields_events() -> None:
    provider = _StubProvider()
    client = Client(provider=provider)
    events = list(client.stream_sync(_make_request()))
    assert len(events) == 2
    assert isinstance(events[0], TextDelta)
    assert isinstance(events[1], StreamEnd)


# ---------------------------------------------------------------------------
# Tests — isinstance check
# ---------------------------------------------------------------------------


def test_stub_provider_satisfies_protocol() -> None:
    provider = _StubProvider()
    assert isinstance(provider, Provider)
