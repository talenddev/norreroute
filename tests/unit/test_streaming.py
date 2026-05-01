"""Tests for aiproxy.streaming event types."""

from __future__ import annotations

import pytest

from aiproxy.streaming import StreamEnd, StreamEvent, TextDelta, ToolCallDelta
from aiproxy.types import Usage


# ---------------------------------------------------------------------------
# TextDelta
# ---------------------------------------------------------------------------


def test_text_delta_fields() -> None:
    d = TextDelta(text="hello")
    assert d.text == "hello"
    assert d.type == "text_delta"


def test_text_delta_frozen() -> None:
    d = TextDelta(text="x")
    with pytest.raises(Exception):
        d.text = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolCallDelta
# ---------------------------------------------------------------------------


def test_tool_call_delta_fields() -> None:
    d = ToolCallDelta(id="call_1", name="get_weather", arguments_json='{"city": "Paris"}')
    assert d.id == "call_1"
    assert d.name == "get_weather"
    assert d.arguments_json == '{"city": "Paris"}'
    assert d.type == "tool_call_delta"


def test_tool_call_delta_nullable_name() -> None:
    d = ToolCallDelta(id="1", name=None, arguments_json='{"city"')
    assert d.name is None


def test_tool_call_delta_frozen() -> None:
    d = ToolCallDelta(id="1", name="fn", arguments_json="{}")
    with pytest.raises(Exception):
        d.id = "2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StreamEnd
# ---------------------------------------------------------------------------


def test_stream_end_nullable_usage() -> None:
    e = StreamEnd(finish_reason="stop", usage=None)
    assert e.usage is None
    assert e.finish_reason == "stop"
    assert e.type == "end"


def test_stream_end_with_usage() -> None:
    u = Usage(input_tokens=10, output_tokens=5)
    e = StreamEnd(finish_reason="tool_use", usage=u)
    assert e.usage is not None
    assert e.usage.input_tokens == 10
    assert e.usage.output_tokens == 5


def test_stream_end_frozen() -> None:
    e = StreamEnd(finish_reason="stop", usage=None)
    with pytest.raises(Exception):
        e.finish_reason = "length"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# StreamEvent union isinstance checks
# ---------------------------------------------------------------------------


def test_stream_event_isinstance_text_delta() -> None:
    event: StreamEvent = TextDelta(text="chunk")
    assert isinstance(event, TextDelta)


def test_stream_event_isinstance_tool_call_delta() -> None:
    event: StreamEvent = ToolCallDelta(id="1", name="fn", arguments_json="{}")
    assert isinstance(event, ToolCallDelta)


def test_stream_event_isinstance_stream_end() -> None:
    event: StreamEvent = StreamEnd(finish_reason="stop", usage=None)
    assert isinstance(event, StreamEnd)


def test_stream_event_list_all_variants() -> None:
    events: list[StreamEvent] = [
        TextDelta(text="hello"),
        ToolCallDelta(id="1", name="fn", arguments_json="{}"),
        StreamEnd(finish_reason="stop", usage=None),
    ]
    assert len(events) == 3
    assert isinstance(events[0], TextDelta)
    assert isinstance(events[1], ToolCallDelta)
    assert isinstance(events[2], StreamEnd)
