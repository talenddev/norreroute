"""Tests for OllamaProvider — HTTP mocked via respx."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from aiproxy.errors import ProviderError
from aiproxy.providers.ollama import OllamaProvider
from aiproxy.streaming import StreamEnd, TextDelta
from aiproxy.types import (
    ChatRequest,
    ChatResponse,
    Message,
    TextPart,
    ToolSpec,
    ToolUsePart,
)

BASE_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    system: str | None = None,
    tools: list[ToolSpec] | None = None,
) -> ChatRequest:
    return ChatRequest(
        model="llama3",
        messages=[Message(role="user", content=[TextPart(text="Hello")])],
        system=system,
        tools=tuple(tools) if tools else (),
        max_tokens=128,
    )


def _chat_response_body(
    text: str = "Hello from Ollama",
    done_reason: str = "stop",
    tool_calls: list[dict] | None = None,
) -> dict:
    msg: dict = {"role": "assistant"}
    if tool_calls:
        msg["content"] = ""
        msg["tool_calls"] = tool_calls
    else:
        msg["content"] = text
    return {
        "model": "llama3",
        "message": msg,
        "done": True,
        "done_reason": done_reason,
        "prompt_eval_count": 12,
        "eval_count": 8,
    }


@pytest.fixture
def provider() -> OllamaProvider:
    return OllamaProvider(base_url=BASE_URL)


# ---------------------------------------------------------------------------
# chat() tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_chat_returns_text_response(provider: OllamaProvider) -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(200, json=_chat_response_body())
    )

    response = await provider.chat(_make_request())

    assert isinstance(response, ChatResponse)
    assert response.finish_reason == "stop"
    assert len(response.content) == 1
    assert isinstance(response.content[0], TextPart)
    assert response.content[0].text == "Hello from Ollama"


@respx.mock
async def test_chat_usage_populated(provider: OllamaProvider) -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(200, json=_chat_response_body())
    )

    response = await provider.chat(_make_request())

    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 8


@respx.mock
async def test_chat_with_system_prepends_message(provider: OllamaProvider) -> None:
    captured_body: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_body.append(body)
        return httpx.Response(200, json=_chat_response_body())

    respx.post(f"{BASE_URL}/api/chat").mock(side_effect=capture)

    await provider.chat(_make_request(system="You are helpful."))

    messages = captured_body[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are helpful."


@respx.mock
async def test_chat_without_system_no_prepend(provider: OllamaProvider) -> None:
    captured_body: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        captured_body.append(json.loads(request.content))
        return httpx.Response(200, json=_chat_response_body())

    respx.post(f"{BASE_URL}/api/chat").mock(side_effect=capture)

    await provider.chat(_make_request(system=None))

    messages = captured_body[0]["messages"]
    assert messages[0]["role"] == "user"


@respx.mock
async def test_chat_with_tools_returns_tool_use_part(provider: OllamaProvider) -> None:
    tool_calls = [
        {
            "id": "call_weather_1",
            "function": {"name": "get_weather", "arguments": {"city": "Paris"}},
        }
    ]
    body = _chat_response_body(tool_calls=tool_calls, done_reason="stop")
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(200, json=body)
    )

    tools = [ToolSpec(name="get_weather", description="Get weather", parameters={})]
    response = await provider.chat(_make_request(tools=tools))

    assert response.finish_reason == "tool_use"
    assert len(response.content) == 1
    part = response.content[0]
    assert isinstance(part, ToolUsePart)
    assert part.name == "get_weather"
    assert part.arguments == {"city": "Paris"}


# ---------------------------------------------------------------------------
# Error mapping tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_chat_404_raises_provider_error(provider: OllamaProvider) -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(404, json={"error": "model not found"})
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.chat(_make_request())
    assert exc_info.value.status == 404
    assert "not found" in str(exc_info.value)


@respx.mock
async def test_chat_500_raises_provider_error(provider: OllamaProvider) -> None:
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(500, text="internal error")
    )

    with pytest.raises(ProviderError) as exc_info:
        await provider.chat(_make_request())
    assert exc_info.value.status == 500


# ---------------------------------------------------------------------------
# stream() tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_stream_yields_text_deltas_and_stream_end(
    provider: OllamaProvider,
) -> None:
    chunks = [
        {"message": {"content": "Hello"}, "done": False},
        {"message": {"content": " world"}, "done": False},
        {
            "message": {"content": ""},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 3,
        },
    ]
    ndjson = "\n".join(json.dumps(c) for c in chunks)

    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            content=ndjson.encode(),
            headers={"content-type": "application/x-ndjson"},
        )
    )

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
    assert stream_ends[0].usage.input_tokens == 5


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_ollama_provider_name() -> None:
    p = OllamaProvider(base_url=BASE_URL)
    assert p.name == "ollama"


async def test_aclose_closes_client() -> None:
    provider = OllamaProvider(base_url=BASE_URL)
    # Should not raise
    await provider.aclose()

# ---------------------------------------------------------------------------
# TASK-7: Tool-call support — additional tests
# ---------------------------------------------------------------------------


@respx.mock
async def test_chat_tool_use_finish_reason_is_tool_use(
    provider: OllamaProvider,
) -> None:
    """Verify finish_reason=="tool_use" when response has tool_calls."""
    tool_calls = [
        {
            "id": "call_w1",
            "function": {"name": "get_weather", "arguments": {"city": "Berlin"}},
        }
    ]
    body = _chat_response_body(tool_calls=tool_calls, done_reason="stop")
    respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(200, json=body)
    )

    tools = [ToolSpec(name="get_weather", description="Get weather", parameters={})]
    response = await provider.chat(_make_request(tools=tools))

    assert response.finish_reason == "tool_use"
    assert isinstance(response.content[0], ToolUsePart)
    assert response.content[0].arguments == {"city": "Berlin"}


@respx.mock
async def test_chat_tool_result_part_in_messages_accepted(
    provider: OllamaProvider,
) -> None:
    """ToolResultPart in message content should be serialized without error."""
    from aiproxy.types import ToolResultPart

    captured_body: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        captured_body.append(json.loads(request.content))
        return httpx.Response(200, json=_chat_response_body())

    respx.post(f"{BASE_URL}/api/chat").mock(side_effect=capture)

    request = ChatRequest(
        model="llama3",
        messages=[
            Message(
                role="tool",
                content=[
                    ToolResultPart(tool_use_id="call_1", content='{"temp": 20}'),
                ],
            )
        ],
        max_tokens=64,
    )
    response = await provider.chat(request)
    assert isinstance(response, ChatResponse)

    # The ToolResultPart should be serialized as a tool role message
    messages = captured_body[0]["messages"]
    assert messages[0]["role"] == "tool"
    assert messages[0]["content"] == '{"temp": 20}'
