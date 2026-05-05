"""Tests for Ollama vision serialisation — TASK-2."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from norreroute.providers.ollama import OllamaProvider, _messages_to_ollama
from norreroute.types import (
    ChatRequest,
    ImagePart,
    Message,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)

BASE_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# _messages_to_ollama unit tests
# ---------------------------------------------------------------------------


def _make_request(messages: list[Message], system: str | None = None) -> ChatRequest:
    return ChatRequest(model="llava", messages=messages, system=system)


def test_ollama_serialiser_includes_base64_images() -> None:
    jpeg = b"\xff\xd8\xff\xe0"
    request = _make_request(
        [
            Message(
                role="user",
                content=[
                    TextPart(text="What is this?"),
                    ImagePart(data=jpeg),
                ],
            )
        ]
    )
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 1
    msg = serialised[0]
    assert msg["content"] == "What is this?"
    assert msg["images"] == [base64.b64encode(jpeg).decode("ascii")]


def test_ollama_serialiser_image_only_message() -> None:
    data = b"\x89PNG"
    request = _make_request(
        [Message(role="user", content=[ImagePart(data=data, media_type="image/png")])]
    )
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 1
    msg = serialised[0]
    assert msg["content"] == ""
    assert msg["images"] == [base64.b64encode(data).decode("ascii")]


def test_ollama_serialiser_no_images_unchanged() -> None:
    request = _make_request([Message(role="user", content=[TextPart(text="Hello")])])
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 1
    msg = serialised[0]
    assert msg["content"] == "Hello"
    assert "images" not in msg


def test_ollama_serialiser_multiple_messages_with_images() -> None:
    img1 = b"\x01\x02"
    img2 = b"\x03\x04"
    request = _make_request(
        [
            Message(
                role="user", content=[TextPart(text="first"), ImagePart(data=img1)]
            ),
            Message(role="assistant", content=[TextPart(text="answer")]),
            Message(role="user", content=[ImagePart(data=img2)]),
        ]
    )
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 3
    assert serialised[0]["images"] == [base64.b64encode(img1).decode("ascii")]
    assert "images" not in serialised[1]
    assert serialised[2]["images"] == [base64.b64encode(img2).decode("ascii")]
    assert serialised[2]["content"] == ""


def test_ollama_serialiser_images_dropped_in_tool_use_message() -> None:
    img = b"\xff\xd8"
    request = _make_request(
        [
            Message(
                role="assistant",
                content=[
                    ToolUsePart(id="call_1", name="search", arguments={"q": "cats"}),
                    ImagePart(data=img),
                ],
            )
        ]
    )
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 1
    # Images are dropped in tool-use context
    assert "images" not in serialised[0]
    assert "tool_calls" in serialised[0]


def test_ollama_serialiser_images_dropped_in_tool_result_message() -> None:
    img = b"\xff\xd8"
    request = _make_request(
        [
            Message(
                role="tool",
                content=[
                    ToolResultPart(tool_use_id="call_1", content="result"),
                    ImagePart(data=img),
                ],
            )
        ]
    )
    serialised = _messages_to_ollama(request)
    # tool result generates one entry per ToolResultPart, images dropped
    assert len(serialised) == 1
    assert serialised[0]["role"] == "tool"
    assert "images" not in serialised[0]


def test_ollama_serialiser_multiple_images_in_one_message() -> None:
    img1, img2, img3 = b"\x01", b"\x02", b"\x03"
    request = _make_request(
        [
            Message(
                role="user",
                content=[
                    TextPart(text="compare"),
                    ImagePart(data=img1),
                    ImagePart(data=img2),
                    ImagePart(data=img3),
                ],
            )
        ]
    )
    serialised = _messages_to_ollama(request)
    assert serialised[0]["images"] == [
        base64.b64encode(img1).decode("ascii"),
        base64.b64encode(img2).decode("ascii"),
        base64.b64encode(img3).decode("ascii"),
    ]


# ---------------------------------------------------------------------------
# E2E tests with respx
# ---------------------------------------------------------------------------


@pytest.fixture
def provider() -> OllamaProvider:
    return OllamaProvider(base_url=BASE_URL)


def _chat_response_body(text: str = "A cat.") -> dict:
    return {
        "model": "llava",
        "message": {"role": "assistant", "content": text},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 10,
        "eval_count": 5,
    }


@respx.mock
@pytest.mark.asyncio
async def test_ollama_chat_with_image_e2e(provider: OllamaProvider) -> None:
    jpeg = b"\xff\xd8\xff\xe0"
    route = respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(200, json=_chat_response_body("A cat."))
    )

    request = ChatRequest(
        model="llava",
        messages=[
            Message(
                role="user",
                content=[
                    TextPart(text="Describe"),
                    ImagePart(data=jpeg),
                ],
            )
        ],
    )
    response = await provider.chat(request)
    assert response.content[0].text == "A cat."  # type: ignore[union-attr]

    # Verify the request body sent to Ollama contained the images field
    sent_body = json.loads(route.calls[0].request.content)
    msg = sent_body["messages"][0]
    assert msg["images"] == [base64.b64encode(jpeg).decode("ascii")]
    assert msg["content"] == "Describe"


@respx.mock
@pytest.mark.asyncio
async def test_ollama_stream_with_image(provider: OllamaProvider) -> None:
    jpeg = b"\xff\xd8"
    stream_lines = [
        json.dumps({"message": {"content": "A "}, "done": False}),
        json.dumps(
            {
                "message": {"content": "cat."},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 5,
                "eval_count": 3,
            }
        ),
    ]
    route = respx.post(f"{BASE_URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            content="\n".join(stream_lines).encode(),
            headers={"content-type": "application/x-ndjson"},
        )
    )

    request = ChatRequest(
        model="llava",
        messages=[Message(role="user", content=[ImagePart(data=jpeg)])],
    )
    events = []
    async for event in provider.stream(request):
        events.append(event)

    # Verify the request body contained images
    sent_body = json.loads(route.calls[0].request.content)
    msg = sent_body["messages"][0]
    assert msg["images"] == [base64.b64encode(jpeg).decode("ascii")]
    assert msg["content"] == ""
    assert len(events) >= 1
