"""Integration-style tests — same ChatRequest through both providers via Client.

All HTTP is mocked (respx for Ollama, pytest-mock for Anthropic SDK).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
import respx

from norreroute.client import Client
from norreroute.providers.anthropic import AnthropicProvider
from norreroute.providers.ollama import OllamaProvider
from norreroute.streaming import StreamEnd, TextDelta
from norreroute.types import (
    ChatRequest,
    ChatResponse,
    Message,
    TextPart,
)

OLLAMA_BASE = "http://localhost:11434"


# ---------------------------------------------------------------------------
# Shared request fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def chat_request() -> ChatRequest:
    return ChatRequest(
        model="test-model",
        messages=[Message(role="user", content=[TextPart(text="What is 2+2?")])],
        system="You are a helpful math assistant.",
        max_tokens=128,
    )


# ---------------------------------------------------------------------------
# Provider fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anthropic_provider() -> AnthropicProvider:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        provider = AnthropicProvider()
    return provider


@pytest.fixture
def ollama_provider() -> OllamaProvider:
    return OllamaProvider(base_url=OLLAMA_BASE)


@pytest.fixture
def anthropic_client(anthropic_provider: AnthropicProvider) -> Client:
    return Client(provider=anthropic_provider)


@pytest.fixture
def ollama_client(ollama_provider: OllamaProvider) -> Client:
    return Client(provider=ollama_provider)


# ---------------------------------------------------------------------------
# Mock setup helpers
# ---------------------------------------------------------------------------


def _mock_anthropic_response(provider: AnthropicProvider, text: str = "4") -> None:
    """Patch the Anthropic SDK to return a text response."""
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text

    resp = MagicMock(spec=anthropic.types.Message)
    resp.id = "msg_test"
    resp.type = "message"
    resp.model = "claude-3-haiku-20240307"
    resp.stop_reason = "end_turn"
    resp.stop_sequence = None
    resp.usage = MagicMock()
    resp.usage.input_tokens = 12
    resp.usage.output_tokens = 3
    resp.content = [content_block]

    provider._client.messages.create = AsyncMock(return_value=resp)


def _mock_anthropic_stream(provider: AnthropicProvider, chunks: list[str]) -> None:
    """Patch the Anthropic SDK to stream text chunks."""
    final_msg = MagicMock(spec=anthropic.types.Message)
    final_msg.stop_reason = "end_turn"
    final_msg.usage = MagicMock()
    final_msg.usage.input_tokens = 10
    final_msg.usage.output_tokens = 5

    async def _text_gen():
        for chunk in chunks:
            yield chunk

    mock_stream = MagicMock()
    mock_stream.text_stream = _text_gen()
    mock_stream.get_final_message = AsyncMock(return_value=final_msg)

    @asynccontextmanager
    async def _mock_cm(*args: Any, **kwargs: Any):
        yield mock_stream

    provider._client.messages.stream = _mock_cm


# ---------------------------------------------------------------------------
# chat() round-trip tests — parametrized over both providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("client_fixture", ["anthropic_client", "ollama_client"])
@respx.mock
async def test_chat_returns_chat_response(
    request: pytest.FixtureRequest,
    client_fixture: str,
    chat_request: ChatRequest,
) -> None:
    client: Client = request.getfixturevalue(client_fixture)

    if client_fixture == "anthropic_client":
        _mock_anthropic_response(client._provider)  # type: ignore[arg-type]
    else:
        respx.post(f"{OLLAMA_BASE}/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "4"},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 3,
                },
            )
        )

    response = await client.chat(chat_request)

    assert isinstance(response, ChatResponse)
    assert len(response.content) >= 1
    assert isinstance(response.content[0], TextPart)
    assert response.finish_reason == "stop"


@pytest.mark.parametrize("client_fixture", ["anthropic_client", "ollama_client"])
@respx.mock
async def test_chat_usage_has_positive_counts(
    request: pytest.FixtureRequest,
    client_fixture: str,
    chat_request: ChatRequest,
) -> None:
    client: Client = request.getfixturevalue(client_fixture)

    if client_fixture == "anthropic_client":
        _mock_anthropic_response(client._provider)  # type: ignore[arg-type]
    else:
        respx.post(f"{OLLAMA_BASE}/api/chat").mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "4"},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 12,
                    "eval_count": 3,
                },
            )
        )

    response = await client.chat(chat_request)

    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0


# ---------------------------------------------------------------------------
# stream() round-trip tests — parametrized over both providers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("client_fixture", ["anthropic_client", "ollama_client"])
@respx.mock
async def test_stream_yields_text_delta_then_stream_end(
    request: pytest.FixtureRequest,
    client_fixture: str,
    chat_request: ChatRequest,
) -> None:
    client: Client = request.getfixturevalue(client_fixture)

    if client_fixture == "anthropic_client":
        _mock_anthropic_stream(client._provider, ["4"])  # type: ignore[arg-type]
    else:
        chunks = [
            {"message": {"content": "4"}, "done": False},
            {
                "message": {"content": ""},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 5,
                "eval_count": 2,
            },
        ]
        ndjson = "\n".join(json.dumps(c) for c in chunks)
        respx.post(f"{OLLAMA_BASE}/api/chat").mock(
            return_value=httpx.Response(200, content=ndjson.encode())
        )

    events = []
    async for event in client.stream(chat_request):
        events.append(event)

    assert any(isinstance(e, TextDelta) for e in events)
    assert isinstance(events[-1], StreamEnd)
    assert events[-1].finish_reason in ("stop", "length", "tool_use", "error")


# ---------------------------------------------------------------------------
# stream_sync() — verify sync wrapper works (Ollama only, simpler to mock)
# ---------------------------------------------------------------------------


@respx.mock
def test_stream_sync_yields_events(
    ollama_client: Client,
    chat_request: ChatRequest,
) -> None:
    chunks = [
        {"message": {"content": "Hello"}, "done": False},
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 3,
            "eval_count": 1,
        },
    ]
    ndjson = "\n".join(json.dumps(c) for c in chunks)
    respx.post(f"{OLLAMA_BASE}/api/chat").mock(
        return_value=httpx.Response(200, content=ndjson.encode())
    )

    events = list(ollama_client.stream_sync(chat_request))

    assert len(events) >= 1
    assert isinstance(events[-1], StreamEnd)
