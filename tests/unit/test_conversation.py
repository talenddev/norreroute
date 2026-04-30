"""Unit tests for conversation.py — Conversation and TrimStrategy."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from norreroute.client import Client
from norreroute.conversation import (
    Conversation,
    TrimStrategy,
    _dict_to_message,
    _message_to_dict,
)
from norreroute.errors import ConversationOverflowError
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import ChatRequest, ChatResponse, Message, TextPart, Usage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(text: str = "assistant reply") -> ChatResponse:
    return ChatResponse(
        model="test-model",
        content=[TextPart(text=text)],
        finish_reason="stop",
        usage=Usage(input_tokens=5, output_tokens=5),
        raw={},
    )


class FakeProvider:
    """Scripted fake provider."""

    name = "fake"

    def __init__(
        self,
        responses: list[ChatResponse] | None = None,
        stream_events: list[Any] | None = None,
    ) -> None:
        self._responses = list(responses or [_make_response()])
        self._stream_events = list(
            stream_events
            or [
                TextDelta(text="streamed reply"),
                StreamEnd(finish_reason="stop", usage=None),
            ]
        )
        self.last_request: ChatRequest | None = None
        self._call_count = 0

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.last_request = request
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]

    async def _gen(self, events: list[Any]) -> AsyncIterator[StreamEvent]:
        for event in events:
            yield event  # type: ignore[misc]

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.last_request = request
        return self._gen(self._stream_events)

    async def aclose(self) -> None:
        pass


def _make_client(provider: FakeProvider | None = None) -> Client:
    p = provider or FakeProvider()
    return Client(provider=p)


# ---------------------------------------------------------------------------
# TrimStrategy
# ---------------------------------------------------------------------------


class TestTrimStrategy:
    def test_frozen(self) -> None:
        ts = TrimStrategy(max_input_tokens=1000)
        with pytest.raises(AttributeError):
            ts.max_input_tokens = 2000  # type: ignore[misc]

    def test_defaults(self) -> None:
        ts = TrimStrategy(max_input_tokens=500)
        assert ts.keep_system is True
        assert ts.keep_last_n == 2

    def test_custom_values(self) -> None:
        ts = TrimStrategy(max_input_tokens=100, keep_system=False, keep_last_n=4)
        assert ts.max_input_tokens == 100
        assert ts.keep_system is False
        assert ts.keep_last_n == 4


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


class TestMessageSerialisation:
    def test_text_roundtrip(self) -> None:
        msg = Message(role="user", content=[TextPart(text="hello")])
        d = _message_to_dict(msg)
        assert d["role"] == "user"
        assert d["content"][0]["text"] == "hello"
        restored = _dict_to_message(d)
        assert restored.role == "user"
        assert isinstance(restored.content[0], TextPart)
        assert restored.content[0].text == "hello"

    def test_assistant_role_preserved(self) -> None:
        msg = Message(role="assistant", content=[TextPart(text="reply")])
        restored = _dict_to_message(_message_to_dict(msg))
        assert restored.role == "assistant"

    def test_tool_use_roundtrip(self) -> None:
        from norreroute.types import ToolUsePart

        msg = Message(
            role="assistant",
            content=[ToolUsePart(id="tu-1", name="get_time", arguments={"tz": "UTC"})],
        )
        d = _message_to_dict(msg)
        restored = _dict_to_message(d)
        from norreroute.types import ToolUsePart as TUP

        part = restored.content[0]
        assert isinstance(part, TUP)
        assert part.id == "tu-1"
        assert part.name == "get_time"
        assert part.arguments == {"tz": "UTC"}

    def test_tool_result_roundtrip(self) -> None:
        from norreroute.types import ToolResultPart

        msg = Message(
            role="user",
            content=[
                ToolResultPart(tool_use_id="tu-1", content="12:00 UTC", is_error=False)
            ],
        )
        d = _message_to_dict(msg)
        restored = _dict_to_message(d)
        from norreroute.types import ToolResultPart as TRP

        part = restored.content[0]
        assert isinstance(part, TRP)
        assert part.tool_use_id == "tu-1"
        assert part.content == "12:00 UTC"
        assert part.is_error is False

    def test_tool_result_is_error_default(self) -> None:
        """Missing is_error key in JSON defaults to False."""
        from norreroute.types import ToolResultPart

        d: dict[str, Any] = {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu-1", "content": "ok"}
            ],
        }
        restored = _dict_to_message(d)
        part = restored.content[0]
        assert isinstance(part, ToolResultPart)
        assert part.is_error is False


# ---------------------------------------------------------------------------
# Conversation.send
# ---------------------------------------------------------------------------


class TestConversationSend:
    @pytest.mark.asyncio
    async def test_send_appends_user_and_assistant(self) -> None:
        provider = FakeProvider(responses=[_make_response("pong")])
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        resp = await conv.send("ping")
        assert resp.content[0].text == "pong"  # type: ignore[union-attr]
        msgs = conv.messages
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content[0].text == "ping"  # type: ignore[union-attr]
        assert msgs[1].role == "assistant"
        assert msgs[1].content[0].text == "pong"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_send_multiple_turns(self) -> None:
        provider = FakeProvider(
            responses=[_make_response("a1"), _make_response("a2")]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("q1")
        await conv.send("q2")
        msgs = conv.messages
        assert len(msgs) == 4
        assert msgs[2].role == "user"
        assert msgs[3].role == "assistant"

    @pytest.mark.asyncio
    async def test_request_includes_prior_history(self) -> None:
        provider = FakeProvider(
            responses=[_make_response("a1"), _make_response("a2")]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("first")
        await conv.send("second")
        # Second request must carry full history (3 prior + 1 new = 3 sent)
        assert provider.last_request is not None
        assert len(provider.last_request.messages) == 3

    @pytest.mark.asyncio
    async def test_system_prompt_forwarded(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model", system="Be terse.")
        await conv.send("hi")
        assert provider.last_request is not None
        assert provider.last_request.system == "Be terse."


# ---------------------------------------------------------------------------
# Conversation.stream
# ---------------------------------------------------------------------------


class TestConversationStream:
    @pytest.mark.asyncio
    async def test_stream_appends_after_end(self) -> None:
        provider = FakeProvider(
            stream_events=[
                TextDelta(text="hello "),
                TextDelta(text="world"),
                StreamEnd(finish_reason="stop", usage=None),
            ]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")

        collected: list[str] = []
        async for event in conv.stream("hi"):
            if isinstance(event, TextDelta):
                collected.append(event.text)

        assert "".join(collected) == "hello world"
        msgs = conv.messages
        assert len(msgs) == 2
        assert msgs[1].role == "assistant"
        assert msgs[1].content[0].text == "hello world"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_stream_no_append_on_interrupted(self) -> None:
        """Breaking out of the stream before StreamEnd must NOT append assistant msg."""
        provider = FakeProvider(
            stream_events=[
                TextDelta(text="partial"),
                TextDelta(text=" text"),
                StreamEnd(finish_reason="stop", usage=None),
            ]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")

        async for event in conv.stream("hi"):
            if isinstance(event, TextDelta):
                break  # early exit before StreamEnd

        # User message was added, but NO assistant message
        msgs = conv.messages
        assert len(msgs) == 1
        assert msgs[0].role == "user"

    @pytest.mark.asyncio
    async def test_stream_user_message_added_once_iteration_starts(self) -> None:
        """User message appears in history after the first event is consumed."""
        provider = FakeProvider(
            stream_events=[
                TextDelta(text="hi"),
                StreamEnd(finish_reason="stop", usage=None),
            ]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")

        # Consume one event to start the generator body (which appends user msg)
        _agen = conv.stream("hello").__aiter__()
        await _agen.__anext__()
        await _agen.aclose()

        msgs = conv.messages
        assert len(msgs) == 1
        assert msgs[0].role == "user"
        assert msgs[0].content[0].text == "hello"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Conversation.send_message
# ---------------------------------------------------------------------------


class TestConversationSendMessage:
    @pytest.mark.asyncio
    async def test_send_arbitrary_message(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        msg = Message(role="user", content=[TextPart(text="custom")])
        await conv.send_message(msg)
        assert conv.messages[0].content[0].text == "custom"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Trim behaviour
# ---------------------------------------------------------------------------


class TestTrimBehaviour:
    @pytest.mark.asyncio
    async def test_no_trim_sends_full_history(self) -> None:
        provider = FakeProvider(
            responses=[_make_response("a1"), _make_response("a2"), _make_response("a3")]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("q1")
        await conv.send("q2")
        await conv.send("q3")
        assert provider.last_request is not None
        # 5 messages: q1, a1, q2, a2, q3 — no trim, all sent
        assert len(provider.last_request.messages) == 5

    @pytest.mark.asyncio
    async def test_trim_drops_oldest_when_over_budget(self) -> None:
        """With a tight budget, oldest messages are trimmed."""
        # Use char/4 estimate. Each 'long_message_N' is ~16 chars → 4 tokens each.
        # 5 messages x 4 tokens = 20 tokens total. Budget=10 forces trimming.
        long_q1 = "long_message_1aaa"  # ~17 chars → 4 tokens
        long_q2 = "long_message_2bbb"
        long_q3 = "long_message_3ccc"
        long_a = "long_answer_reply"  # assistant reply also ~4 tokens

        provider = FakeProvider(
            responses=[
                _make_response(long_a),
                _make_response(long_a),
                _make_response(long_a),
            ]
        )
        client = _make_client(provider)
        # Budget 10 tokens, keep_last_n=2 (pins a2 + new user msg q3)
        trim = TrimStrategy(max_input_tokens=10, keep_last_n=2)
        conv = Conversation(client, model="test-model", trim=trim)

        await conv.send(long_q1)  # history: q1, a1
        await conv.send(long_q2)  # history: q1, a1, q2, a2
        await conv.send(long_q3)  # history before trim: q1,a1,q2,a2,q3 (5 msgs ~20 tok)

        # Trim must have dropped q1 (oldest head) to fit in budget
        assert provider.last_request is not None
        n = len(provider.last_request.messages)
        assert n < 5

    @pytest.mark.asyncio
    async def test_trim_raises_when_tail_exceeds_budget(self) -> None:
        """ConversationOverflowError when tail alone exceeds budget."""
        provider = FakeProvider(
            responses=[_make_response("ok"), _make_response("ok")]
        )
        client = _make_client(provider)
        # keep_last_n=2 means 2 messages always pinned; budget=0 forces overflow
        trim = TrimStrategy(max_input_tokens=0, keep_last_n=2)
        conv = Conversation(client, model="test-model", trim=trim)

        # First send: only 1 message → tail covers it, head is empty → no overflow
        await conv.send("q1")
        # Second send: history has 3 msgs; tail=2, head=[q1], total > 0 → head dropped
        # After dropping all of head, tail alone (2 msgs + new) still > 0 → overflow
        with pytest.raises(ConversationOverflowError):
            await conv.send("q2")

    @pytest.mark.asyncio
    async def test_trim_keep_last_n_zero(self) -> None:
        """keep_last_n=0 means no pinned messages."""
        provider = FakeProvider(
            responses=[_make_response("ok"), _make_response("ok")]
        )
        client = _make_client(provider)
        trim = TrimStrategy(max_input_tokens=1000, keep_last_n=0)
        conv = Conversation(client, model="test-model", trim=trim)
        await conv.send("q1")
        await conv.send("q2")
        assert provider.last_request is not None
        assert len(provider.last_request.messages) == 3


# ---------------------------------------------------------------------------
# JSON serialisation (to_json / from_json)
# ---------------------------------------------------------------------------


class TestConversationSerialisation:
    @pytest.mark.asyncio
    async def test_to_json_schema_version(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="m1")
        data = json.loads(conv.to_json())
        assert data["version"] == 1

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_model_and_system(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="gpt-4", system="Be concise.")
        await conv.send("hi")
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        assert restored._model == "gpt-4"
        assert restored._system == "Be concise."

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_message_history(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("hello")
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        msgs = restored.messages
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].content[0].text == "hello"  # type: ignore[union-attr]
        assert msgs[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_trim_strategy(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        trim = TrimStrategy(max_input_tokens=500, keep_system=False, keep_last_n=4)
        conv = Conversation(client, model="test-model", trim=trim)
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        assert restored._trim is not None
        assert restored._trim.max_input_tokens == 500
        assert restored._trim.keep_system is False
        assert restored._trim.keep_last_n == 4

    @pytest.mark.asyncio
    async def test_roundtrip_no_trim(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        j = conv.to_json()
        data = json.loads(j)
        assert data["trim"] is None
        restored = Conversation.from_json(j, client)
        assert restored._trim is None

    @pytest.mark.asyncio
    async def test_from_json_empty_history(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        assert restored.messages == ()

    @pytest.mark.asyncio
    async def test_roundtrip_system_none(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        assert restored._system is None

    @pytest.mark.asyncio
    async def test_restored_conversation_can_continue(self) -> None:
        provider = FakeProvider(
            responses=[_make_response("r1"), _make_response("r2")]
        )
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("turn1")
        j = conv.to_json()
        restored = Conversation.from_json(j, client)
        resp = await restored.send("turn2")
        assert resp.content[0].text == "r2"  # type: ignore[union-attr]
        # Prior history included in request
        assert provider.last_request is not None
        assert len(provider.last_request.messages) == 3  # t1,a1,t2


# ---------------------------------------------------------------------------
# messages property
# ---------------------------------------------------------------------------


class TestMessagesProperty:
    def test_messages_returns_tuple(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        assert isinstance(conv.messages, tuple)
        assert len(conv.messages) == 0

    @pytest.mark.asyncio
    async def test_messages_immutable(self) -> None:
        provider = FakeProvider()
        client = _make_client(provider)
        conv = Conversation(client, model="test-model")
        await conv.send("hi")
        msgs = conv.messages
        assert isinstance(msgs, tuple)
        # Tuple cannot be mutated
        with pytest.raises(TypeError):
            msgs[0] = Message(role="user", content=[])  # type: ignore[index]
