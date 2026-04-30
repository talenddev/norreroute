"""Tests for aiproxy.types domain model."""

from __future__ import annotations

import pytest

from aiproxy.types import (
    ChatRequest,
    ChatResponse,
    ContentPart,
    Message,
    TextPart,
    ToolResultPart,
    ToolSpec,
    ToolUsePart,
    Usage,
)
from aiproxy.streaming import StreamEnd, StreamEvent, TextDelta, ToolCallDelta


# ---------------------------------------------------------------------------
# TextPart
# ---------------------------------------------------------------------------


def test_text_part_fields() -> None:
    p = TextPart(text="hello")
    assert p.text == "hello"
    assert p.type == "text"


def test_text_part_frozen() -> None:
    p = TextPart(text="hello")
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        p.text = "world"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolUsePart
# ---------------------------------------------------------------------------


def test_tool_use_part_fields() -> None:
    p = ToolUsePart(id="call_1", name="get_weather", arguments={"city": "London"})
    assert p.id == "call_1"
    assert p.name == "get_weather"
    assert p.arguments == {"city": "London"}
    assert p.type == "tool_use"


def test_tool_use_part_frozen() -> None:
    p = ToolUsePart(id="x", name="y", arguments={})
    with pytest.raises(Exception):
        p.id = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolResultPart
# ---------------------------------------------------------------------------


def test_tool_result_part_defaults() -> None:
    p = ToolResultPart(tool_use_id="call_1", content='{"temp": 20}')
    assert p.is_error is False
    assert p.type == "tool_result"


def test_tool_result_part_error_flag() -> None:
    p = ToolResultPart(tool_use_id="call_1", content="error", is_error=True)
    assert p.is_error is True


# ---------------------------------------------------------------------------
# ContentPart union isinstance checks
# ---------------------------------------------------------------------------


def test_content_part_isinstance_text() -> None:
    p: ContentPart = TextPart(text="hi")
    assert isinstance(p, TextPart)


def test_content_part_isinstance_tool_use() -> None:
    p: ContentPart = ToolUsePart(id="1", name="fn", arguments={})
    assert isinstance(p, ToolUsePart)


def test_content_part_isinstance_tool_result() -> None:
    p: ContentPart = ToolResultPart(tool_use_id="1", content="ok")
    assert isinstance(p, ToolResultPart)


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


def test_message_fields() -> None:
    msg = Message(role="user", content=[TextPart(text="hello")])
    assert msg.role == "user"
    assert len(msg.content) == 1


def test_message_frozen() -> None:
    msg = Message(role="user", content=[])
    with pytest.raises(Exception):
        msg.role = "assistant"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------


def test_tool_spec_fields() -> None:
    spec = ToolSpec(
        name="get_weather",
        description="Get the weather for a city",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    )
    assert spec.name == "get_weather"
    assert "city" in spec.parameters["properties"]


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------


def test_chat_request_defaults() -> None:
    req = ChatRequest(
        model="gpt-4",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    assert req.system is None
    assert req.tools == ()
    assert req.temperature is None
    assert req.max_tokens is None
    assert req.stop == ()
    assert req.extra == {}


def test_chat_request_extra_is_independent() -> None:
    """Each ChatRequest should get its own extra dict (not shared mutable default)."""
    req1 = ChatRequest(model="m", messages=[])
    req2 = ChatRequest(model="m", messages=[])
    # They should be equal but not the same object
    assert req1.extra == req2.extra
    # Modifying a copy does not affect original frozen instances — immutability check
    assert req1.extra is not req2.extra


def test_chat_request_frozen() -> None:
    req = ChatRequest(model="m", messages=[])
    with pytest.raises(Exception):
        req.model = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


def test_usage_fields() -> None:
    u = Usage(input_tokens=10, output_tokens=20)
    assert u.input_tokens == 10
    assert u.output_tokens == 20


def test_usage_frozen() -> None:
    u = Usage(input_tokens=1, output_tokens=2)
    with pytest.raises(Exception):
        u.input_tokens = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------


def test_chat_response_fields() -> None:
    resp = ChatResponse(
        model="claude-3",
        content=[TextPart(text="hello")],
        finish_reason="stop",
        usage=Usage(input_tokens=5, output_tokens=3),
        raw={"id": "msg_1"},
    )
    assert resp.model == "claude-3"
    assert resp.finish_reason == "stop"
    assert resp.raw == {"id": "msg_1"}


def test_chat_response_frozen() -> None:
    resp = ChatResponse(
        model="m",
        content=[],
        finish_reason="stop",
        usage=Usage(input_tokens=0, output_tokens=0),
        raw={},
    )
    with pytest.raises(Exception):
        resp.model = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Streaming types
# ---------------------------------------------------------------------------


def test_text_delta_fields() -> None:
    d = TextDelta(text="chunk")
    assert d.text == "chunk"
    assert d.type == "text_delta"


def test_text_delta_frozen() -> None:
    d = TextDelta(text="x")
    with pytest.raises(Exception):
        d.text = "y"  # type: ignore[misc]


def test_tool_call_delta_nullable_name() -> None:
    d = ToolCallDelta(id="1", name=None, arguments_json='{"city"')
    assert d.name is None


def test_stream_end_nullable_usage() -> None:
    e = StreamEnd(finish_reason="stop", usage=None)
    assert e.usage is None
    assert e.type == "end"


def test_stream_end_with_usage() -> None:
    e = StreamEnd(finish_reason="stop", usage=Usage(input_tokens=5, output_tokens=3))
    assert e.usage is not None
    assert e.usage.input_tokens == 5


def test_stream_event_isinstance() -> None:
    events: list[StreamEvent] = [
        TextDelta(text="hello"),
        ToolCallDelta(id="1", name="fn", arguments_json="{}"),
        StreamEnd(finish_reason="stop", usage=None),
    ]
    assert isinstance(events[0], TextDelta)
    assert isinstance(events[1], ToolCallDelta)
    assert isinstance(events[2], StreamEnd)
