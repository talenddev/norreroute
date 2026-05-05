"""Tests for ImagePart, ChatResponse.text, and Message.user/system — TASK-1."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from norreroute.types import (
    ChatResponse,
    ImagePart,
    Message,
    TextPart,
    ToolUsePart,
    Usage,
)

# ---------------------------------------------------------------------------
# ImagePart
# ---------------------------------------------------------------------------


def test_image_part_is_frozen_and_typed() -> None:
    part = ImagePart(data=b"\xff\xd8")
    assert part.type == "image"
    with pytest.raises(FrozenInstanceError):
        part.data = b"\x00"  # type: ignore[misc]


def test_image_part_preserves_bytes() -> None:
    data = b"\xff\xd8\xff\xe0"
    part = ImagePart(data=data, media_type="image/png")
    assert part.data == data
    assert part.media_type == "image/png"
    assert part.type == "image"


def test_image_part_default_media_type() -> None:
    part = ImagePart(data=b"\x00")
    assert part.media_type == "image/jpeg"


def test_image_part_is_hashable() -> None:
    part = ImagePart(data=b"\xff\xd8")
    # Should not raise — frozen dataclasses are hashable
    assert hash(part) == hash(ImagePart(data=b"\xff\xd8"))


# ---------------------------------------------------------------------------
# ChatResponse.text
# ---------------------------------------------------------------------------


def test_chat_response_text_concatenates_text_parts() -> None:
    response = ChatResponse(
        model="llava",
        content=[TextPart(text="Hello, "), TextPart(text="world.")],
        finish_reason="stop",
        usage=Usage(input_tokens=5, output_tokens=3),
        raw={},
    )
    assert response.text == "Hello, world."


def test_chat_response_text_empty_when_only_tool_use() -> None:
    response = ChatResponse(
        model="claude-3",
        content=[
            ToolUsePart(id="call_1", name="get_weather", arguments={"city": "NY"})
        ],
        finish_reason="tool_use",
        usage=Usage(input_tokens=10, output_tokens=5),
        raw={},
    )
    assert response.text == ""


def test_chat_response_text_single_text_part() -> None:
    response = ChatResponse(
        model="llava",
        content=[TextPart(text="A cat.")],
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=3),
        raw={},
    )
    assert response.text == "A cat."


def test_chat_response_text_empty_content() -> None:
    response = ChatResponse(
        model="llava",
        content=[],
        finish_reason="stop",
        usage=Usage(input_tokens=0, output_tokens=0),
        raw={},
    )
    assert response.text == ""


# ---------------------------------------------------------------------------
# Message.user
# ---------------------------------------------------------------------------


def test_message_user_text_only() -> None:
    msg = Message.user("hi")
    assert msg.role == "user"
    assert list(msg.content) == [TextPart(text="hi")]


def test_message_user_images_only() -> None:
    msg = Message.user(images=[b"x"])
    assert msg.role == "user"
    assert len(msg.content) == 1
    assert isinstance(msg.content[0], ImagePart)
    # No TextPart when text is empty
    assert not any(isinstance(p, TextPart) for p in msg.content)


def test_message_user_text_and_images() -> None:
    msg = Message.user("hi", images=[b"\xff\xd8"])
    assert msg.role == "user"
    assert len(msg.content) == 2
    assert msg.content[0] == TextPart(text="hi")
    assert isinstance(msg.content[1], ImagePart)
    assert msg.content[1].data == b"\xff\xd8"  # type: ignore[union-attr]


def test_message_user_no_args() -> None:
    msg = Message.user()
    assert msg.role == "user"
    assert list(msg.content) == []


def test_message_user_multiple_images_preserves_order() -> None:
    img1, img2 = b"\x01", b"\x02"
    msg = Message.user("describe", images=[img1, img2])
    assert msg.content[0] == TextPart(text="describe")
    assert msg.content[1].data == img1  # type: ignore[union-attr]
    assert msg.content[2].data == img2  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Message.system
# ---------------------------------------------------------------------------


def test_message_system_single_text_part() -> None:
    msg = Message.system("be brief")
    assert msg.role == "system"
    assert list(msg.content) == [TextPart(text="be brief")]
