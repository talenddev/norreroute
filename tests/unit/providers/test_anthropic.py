"""Tests for AnthropicProvider — SDK methods mocked via pytest-mock."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from aiproxy.errors import AuthenticationError, ProviderError, RateLimitError
from aiproxy.providers.anthropic import AnthropicProvider
from aiproxy.streaming import StreamEnd, TextDelta
from aiproxy.types import (
    ChatRequest,
    ChatResponse,
    Message,
    TextPart,
    ToolSpec,
    ToolUsePart,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    system: str | None = None,
    tools: list[ToolSpec] | None = None,
) -> ChatRequest:
    return ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[Message(role="user", content=[TextPart(text="Hello")])],
        system=system,
        tools=tuple(tools) if tools else (),
        max_tokens=256,
    )


def _make_anthropic_response(
    text: str = "Hello from Claude",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 8,
    tool_use: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a mock anthropic.Message response."""
    resp = MagicMock(spec=anthropic.types.Message)
    resp.id = "msg_test_123"
    resp.type = "message"
    resp.model = "claude-3-haiku-20240307"
    resp.stop_reason = stop_reason
    resp.stop_sequence = None
    resp.usage = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens

    if tool_use:
        tb = MagicMock()
        tb.type = "tool_use"
        tb.id = tool_use["id"]
        tb.name = tool_use["name"]
        tb.input = tool_use["input"]
        resp.content = [tb]
    else:
        tb = MagicMock()
        tb.type = "text"
        tb.text = text
        resp.content = [tb]

    return resp


@pytest.fixture
def provider() -> AnthropicProvider:
    """Create a provider with a test API key (no real network calls)."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        return AnthropicProvider()


# ---------------------------------------------------------------------------
# chat() tests
# ---------------------------------------------------------------------------


async def test_chat_returns_text_response(provider: AnthropicProvider) -> None:
    mock_response = _make_anthropic_response()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    response = await provider.chat(_make_request())

    assert isinstance(response, ChatResponse)
    assert response.finish_reason == "stop"
    assert len(response.content) == 1
    assert isinstance(response.content[0], TextPart)
    assert response.content[0].text == "Hello from Claude"


async def test_chat_usage_populated(provider: AnthropicProvider) -> None:
    mock_response = _make_anthropic_response(input_tokens=15, output_tokens=7)
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    response = await provider.chat(_make_request())

    assert response.usage.input_tokens == 15
    assert response.usage.output_tokens == 7


async def test_chat_raw_populated(provider: AnthropicProvider) -> None:
    mock_response = _make_anthropic_response()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    response = await provider.chat(_make_request())

    assert "id" in response.raw
    assert "usage" in response.raw
    assert response.raw["stop_reason"] == "end_turn"


async def test_chat_sends_system_param(provider: AnthropicProvider) -> None:
    mock_response = _make_anthropic_response()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    await provider.chat(_make_request(system="You are a helpful assistant."))

    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a helpful assistant."


async def test_chat_without_system_omits_param(provider: AnthropicProvider) -> None:
    mock_response = _make_anthropic_response()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    await provider.chat(_make_request(system=None))

    call_kwargs = provider._client.messages.create.call_args.kwargs
    assert "system" not in call_kwargs


async def test_chat_with_tools_returns_tool_use_part(
    provider: AnthropicProvider,
) -> None:
    tool_use = {"id": "call_abc", "name": "get_weather", "input": {"city": "London"}}
    mock_response = _make_anthropic_response(stop_reason="tool_use", tool_use=tool_use)
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    tools = [ToolSpec(name="get_weather", description="Get weather", parameters={})]
    response = await provider.chat(_make_request(tools=tools))

    assert response.finish_reason == "tool_use"
    assert len(response.content) == 1
    part = response.content[0]
    assert isinstance(part, ToolUsePart)
    assert part.id == "call_abc"
    assert part.name == "get_weather"
    assert part.arguments == {"city": "London"}


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------


async def test_chat_401_raises_authentication_error(
    provider: AnthropicProvider,
) -> None:
    exc = anthropic.AuthenticationError(
        message="invalid api key",
        response=MagicMock(status_code=401),
        body={"error": {"type": "authentication_error"}},
    )
    provider._client.messages.create = AsyncMock(side_effect=exc)

    with pytest.raises(AuthenticationError) as exc_info:
        await provider.chat(_make_request())
    assert exc_info.value.status == 401
    assert exc_info.value.provider == "anthropic"


async def test_chat_429_raises_rate_limit_error(provider: AnthropicProvider) -> None:
    exc = anthropic.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429),
        body={"error": {"type": "rate_limit_error"}},
    )
    provider._client.messages.create = AsyncMock(side_effect=exc)

    with pytest.raises(RateLimitError) as exc_info:
        await provider.chat(_make_request())
    assert exc_info.value.status == 429


async def test_chat_500_raises_provider_error(provider: AnthropicProvider) -> None:
    exc = anthropic.InternalServerError(
        message="internal server error",
        response=MagicMock(status_code=500),
        body={"error": {"type": "internal_server_error"}},
    )
    provider._client.messages.create = AsyncMock(side_effect=exc)

    with pytest.raises(ProviderError) as exc_info:
        await provider.chat(_make_request())
    assert exc_info.value.status == 500
    assert not isinstance(exc_info.value, RateLimitError)
    assert not isinstance(exc_info.value, AuthenticationError)


# ---------------------------------------------------------------------------
# stream() tests
# ---------------------------------------------------------------------------


async def test_stream_yields_text_delta_and_stream_end(
    provider: AnthropicProvider,
) -> None:
    """Mock the messages.stream context manager."""
    final_msg = _make_anthropic_response(input_tokens=10, output_tokens=5)

    async def _text_stream():
        yield "Hello"
        yield " world"

    mock_stream = MagicMock()
    mock_stream.text_stream = _text_stream()
    mock_stream.get_final_message = AsyncMock(return_value=final_msg)

    @asynccontextmanager
    async def _mock_stream_cm(*args: Any, **kwargs: Any):
        yield mock_stream

    provider._client.messages.stream = _mock_stream_cm

    events = []
    async for event in provider.stream(_make_request()):
        events.append(event)

    text_deltas = [e for e in events if isinstance(e, TextDelta)]
    stream_ends = [e for e in events if isinstance(e, StreamEnd)]

    assert len(text_deltas) == 2
    assert text_deltas[0].text == "Hello"
    assert text_deltas[1].text == " world"
    assert len(stream_ends) == 1
    assert stream_ends[0].finish_reason == "stop"
    assert stream_ends[0].usage is not None
    assert stream_ends[0].usage.input_tokens == 10


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_anthropic_provider_name() -> None:
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        p = AnthropicProvider()
    assert p.name == "anthropic"


async def test_aclose_closes_client(provider: AnthropicProvider) -> None:
    provider._client.close = AsyncMock()
    await provider.aclose()
    provider._client.close.assert_called_once()


# ---------------------------------------------------------------------------
# TASK-7: Tool-call support — additional tests
# ---------------------------------------------------------------------------


async def test_chat_tool_use_finish_reason_is_tool_use(
    provider: AnthropicProvider,
) -> None:
    """Verify finish_reason=="tool_use" when stop_reason is tool_use."""
    tool_use = {"id": "call_xyz", "name": "get_weather", "input": {"city": "Tokyo"}}
    mock_response = _make_anthropic_response(stop_reason="tool_use", tool_use=tool_use)
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    tools = [ToolSpec(name="get_weather", description="Get weather", parameters={})]
    response = await provider.chat(_make_request(tools=tools))

    assert response.finish_reason == "tool_use"


async def test_chat_tool_result_part_in_messages_accepted(
    provider: AnthropicProvider,
) -> None:
    """ToolResultPart in message content should be serialized without error."""
    from aiproxy.types import ToolResultPart

    mock_response = _make_anthropic_response()
    provider._client.messages.create = AsyncMock(return_value=mock_response)

    # Message with a tool result — simulates a multi-turn tool-use conversation
    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(
                role="user",
                content=[
                    ToolResultPart(tool_use_id="call_1", content='{"temp": 20}'),
                ],
            )
        ],
        max_tokens=128,
    )
    # Should not raise — ToolResultPart must serialize correctly
    response = await provider.chat(request)
    assert isinstance(response, ChatResponse)

    call_kwargs = provider._client.messages.create.call_args.kwargs
    messages = call_kwargs["messages"]
    # The ToolResultPart should appear as a tool_result content block
    assert messages[0]["content"][0]["type"] == "tool_result"
    assert messages[0]["content"][0]["tool_use_id"] == "call_1"
