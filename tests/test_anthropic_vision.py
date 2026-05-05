"""Tests for Anthropic vision serialisation — TASK-3."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from norreroute.providers.anthropic import AnthropicProvider, _messages_to_anthropic
from norreroute.types import (
    ChatRequest,
    ImagePart,
    Message,
    TextPart,
    ToolResultPart,
)

# ---------------------------------------------------------------------------
# _messages_to_anthropic unit tests
# ---------------------------------------------------------------------------


def _make_request(messages: list[Message]) -> ChatRequest:
    return ChatRequest(model="claude-3-5-sonnet-20241022", messages=messages)


def test_anthropic_serialiser_image_block_shape() -> None:
    data = b"\xff\xd8"
    request = _make_request(
        [Message(role="user", content=[ImagePart(data=data, media_type="image/png")])]
    )
    serialised = _messages_to_anthropic(request)
    assert len(serialised) == 1
    # Image-only message should NOT be flattened — it's a list with one image block
    content = serialised[0]["content"]
    assert isinstance(content, list)
    block = content[0]
    assert block["type"] == "image"
    assert block["source"]["type"] == "base64"
    assert block["source"]["media_type"] == "image/png"
    assert block["source"]["data"] == base64.b64encode(data).decode("ascii")


def test_anthropic_serialiser_text_and_image_no_flatten() -> None:
    data = b"\xff\xd8"
    request = _make_request(
        [
            Message(
                role="user",
                content=[
                    TextPart(text="Describe this"),
                    ImagePart(data=data),
                ],
            )
        ]
    )
    serialised = _messages_to_anthropic(request)
    content = serialised[0]["content"]
    assert isinstance(content, list)
    assert len(content) == 2
    assert content[0] == {"type": "text", "text": "Describe this"}
    assert content[1]["type"] == "image"
    assert content[1]["source"]["media_type"] == "image/jpeg"


def test_anthropic_serialiser_text_only_still_flattens() -> None:
    request = _make_request([Message(role="user", content=[TextPart(text="Hello")])])
    serialised = _messages_to_anthropic(request)
    # Single text block -> plain string (regression)
    assert serialised[0]["content"] == "Hello"
    assert isinstance(serialised[0]["content"], str)


def test_anthropic_serialiser_unknown_part_raises_type_error() -> None:
    class UnknownPart:
        pass

    request = ChatRequest(
        model="claude-3-5-sonnet-20241022",
        messages=[Message(role="user", content=[UnknownPart()])],  # type: ignore[list-item]
    )
    with pytest.raises(TypeError, match="UnknownPart"):
        _messages_to_anthropic(request)


def test_anthropic_serialiser_default_jpeg_media_type() -> None:
    data = b"\xff\xd8"
    request = _make_request([Message(role="user", content=[ImagePart(data=data)])])
    serialised = _messages_to_anthropic(request)
    block = serialised[0]["content"][0]
    assert block["source"]["media_type"] == "image/jpeg"


def test_anthropic_serialiser_tool_result_part_still_works() -> None:
    request = _make_request(
        [
            Message(
                role="tool",
                content=[
                    ToolResultPart(tool_use_id="call_1", content="42", is_error=False)
                ],
            )
        ]
    )
    serialised = _messages_to_anthropic(request)
    # Single ToolResultPart — not flattened (not a text block)
    content = serialised[0]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "tool_result"
    assert content[0]["tool_use_id"] == "call_1"


# ---------------------------------------------------------------------------
# E2E test with mocked anthropic SDK
# ---------------------------------------------------------------------------


def _make_anthropic_response(text: str = "A cat.") -> MagicMock:
    """Build a mock anthropic.Message response."""
    resp = MagicMock(spec=anthropic.types.Message)
    resp.model = "claude-3-5-sonnet-20241022"
    resp.stop_reason = "end_turn"
    resp.stop_sequence = None
    resp.id = "msg_001"
    resp.type = "message"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    resp.content = [text_block]

    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_anthropic_chat_with_image_e2e(mocker: Any) -> None:
    """E2E test: send a message with ImagePart, verify the SDK receives image block."""
    jpeg = b"\xff\xd8\xff\xe0"

    mock_response = _make_anthropic_response("A cat sitting.")
    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_response)

    # Patch AnthropicProvider's client creation
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._settings = MagicMock()
    provider._settings.api_key.get_secret_value.return_value = "test-key"
    provider._client = MagicMock()
    provider._client.messages = mock_messages

    request = ChatRequest(
        model="claude-3-5-sonnet-20241022",
        messages=[
            Message(
                role="user",
                content=[
                    TextPart(text="Describe"),
                    ImagePart(data=jpeg, media_type="image/jpeg"),
                ],
            )
        ],
        max_tokens=256,
    )
    response = await provider.chat(request)
    assert response.text == "A cat sitting."

    # Verify the messages sent to the SDK included an image block
    call_kwargs = mock_messages.create.call_args.kwargs
    msg_content = call_kwargs["messages"][0]["content"]
    assert isinstance(msg_content, list)
    assert len(msg_content) == 2
    assert msg_content[0] == {"type": "text", "text": "Describe"}
    image_block = msg_content[1]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert image_block["source"]["data"] == base64.b64encode(jpeg).decode("ascii")
