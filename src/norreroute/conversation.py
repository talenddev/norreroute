"""Conversation / session management with optional history trimming."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass
from typing import Any

from .client import Client
from .errors import ConversationOverflowError
from .streaming import StreamEnd, StreamEvent, TextDelta
from .types import ChatRequest, ChatResponse, ContentPart, Message, TextPart

# Try to import the real token counter; fall back to inline char/4 estimate.
try:
    from .pricing import count_tokens_approx as _count_tokens_approx
except ImportError:

    def _count_tokens_approx(request: ChatRequest) -> int:  # noqa: F811
        """Inline fallback: char/4 heuristic."""
        total = 0
        if request.system:
            total += len(request.system)
        for msg in request.messages:
            for part in msg.content:
                if isinstance(part, TextPart):
                    total += len(part.text)
        return total // 4


@dataclass(frozen=True)
class TrimStrategy:
    """Configuration for sliding-window history trimming.

    Attributes:
        max_input_tokens: Maximum approximate token budget for the request.
        keep_system: If True, the system prompt (if any) is never dropped.
        keep_last_n: Always keep the last N messages regardless of budget.
    """

    max_input_tokens: int
    keep_system: bool = True
    keep_last_n: int = 2


# ---------------------------------------------------------------------------
# Message serialisation helpers (pure functions — types.py is untouched)
# ---------------------------------------------------------------------------


def _message_to_dict(msg: Message) -> dict[str, Any]:
    """Serialise a Message to a plain dict."""
    parts: list[dict[str, Any]] = []
    for part in msg.content:
        parts.append(asdict(part))
    return {"role": msg.role, "content": parts}


def _dict_to_message(d: dict[str, Any]) -> Message:
    """Deserialise a dict (from JSON) back to a Message."""
    from .types import ToolResultPart, ToolUsePart

    content: list[ContentPart] = []
    for p in d["content"]:
        t = p.get("type", "text")
        if t == "text":
            content.append(TextPart(text=p["text"]))
        elif t == "tool_use":
            content.append(
                ToolUsePart(
                    id=p["id"],
                    name=p["name"],
                    arguments=p["arguments"],
                )
            )
        elif t == "tool_result":
            content.append(
                ToolResultPart(
                    tool_use_id=p["tool_use_id"],
                    content=p["content"],
                    is_error=p.get("is_error", False),
                )
            )
    return Message(role=d["role"], content=content)


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class Conversation:
    """A stateful conversation session that accumulates messages and calls the LLM.

    History is an append-only log. Trimming occurs at send/stream time:
    a window of messages is derived from the full history before each request.

    Args:
        client: The Client to use for chat calls.
        model: The model to request.
        system: Optional system prompt (not stored in message history).
        trim: Optional TrimStrategy; if None, the full history is always sent.
        history: Seed history for the conversation (e.g. from ``from_json``).
    """

    def __init__(
        self,
        client: Client,
        *,
        model: str,
        system: str | None = None,
        trim: TrimStrategy | None = None,
        history: list[Message] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._system = system
        self._trim = trim
        self._history: list[Message] = list(history or [])

    @property
    def messages(self) -> tuple[Message, ...]:
        """Immutable view of the full conversation history."""
        return tuple(self._history)

    def _build_request(self, extra: dict[str, Any]) -> ChatRequest:
        """Build a ChatRequest from current trimmed history."""
        messages = self._trim_messages()
        return ChatRequest(
            model=self._model,
            messages=messages,
            system=self._system,
            extra=extra,
        )

    def _trim_messages(self) -> list[Message]:
        """Derive the message window to send, respecting TrimStrategy."""
        if self._trim is None:
            return list(self._history)

        trim = self._trim
        history = list(self._history)

        if not history:
            return history

        # Always keep the last keep_last_n messages
        tail = history[-trim.keep_last_n :] if trim.keep_last_n > 0 else []
        head = history[: len(history) - len(tail)]

        # Build trial request to measure tokens
        def _measure(msgs: list[Message]) -> int:
            req = ChatRequest(
                model=self._model,
                messages=msgs,
                system=self._system,
            )
            return _count_tokens_approx(req)

        # Start with head + tail and drop oldest head messages until within budget
        window = list(head) + list(tail)
        while _measure(window) > trim.max_input_tokens:
            if not head:
                # Nothing left in head to drop — budget impossible
                raise ConversationOverflowError(
                    f"Cannot trim conversation to fit {trim.max_input_tokens} tokens "
                    f"while keeping the last {trim.keep_last_n} messages. "
                    "The pinned messages alone exceed the budget."
                )
            head.pop(0)
            window = list(head) + list(tail)

        return window

    async def send(self, text: str, **extra: Any) -> ChatResponse:
        """Append a user message, call the LLM, and append the assistant reply.

        Args:
            text: The user's message text.
            **extra: Additional fields forwarded to ChatRequest.extra.

        Returns:
            The ChatResponse from the LLM.
        """
        user_msg = Message(role="user", content=[TextPart(text=text)])
        return await self.send_message(user_msg, **extra)

    async def send_message(self, msg: Message, **extra: Any) -> ChatResponse:
        """Append an arbitrary Message, call the LLM, and append the reply.

        Args:
            msg: The message to append.
            **extra: Additional fields forwarded to ChatRequest.extra.

        Returns:
            The ChatResponse from the LLM.
        """
        self._history.append(msg)
        request = self._build_request(extra)
        response = await self._client.chat(request)

        # Extract assistant text and append to history
        text_parts = [p for p in response.content if isinstance(p, TextPart)]
        reply_text = "".join(p.text for p in text_parts)
        assistant_msg = Message(role="assistant", content=[TextPart(text=reply_text)])
        self._history.append(assistant_msg)
        return response

    async def _stream_impl(
        self, msg: Message, **extra: Any
    ) -> AsyncIterator[StreamEvent]:
        """Internal streaming implementation.

        Appends the user message before streaming and the assistant reply
        only after a StreamEnd event is received. Partial output on an
        interrupted stream is NOT appended.
        """
        self._history.append(msg)
        request = self._build_request(extra)

        accumulated_text = ""
        got_end = False

        async for event in self._client.stream(request):
            if isinstance(event, TextDelta):
                accumulated_text += event.text
            elif isinstance(event, StreamEnd):
                got_end = True
            yield event

        if got_end and accumulated_text:
            assistant_msg = Message(
                role="assistant", content=[TextPart(text=accumulated_text)]
            )
            self._history.append(assistant_msg)

    def stream(self, text: str, **extra: Any) -> AsyncIterator[StreamEvent]:
        """Stream a response to the given user text.

        Appends user message before streaming. Appends assistant message only
        after a StreamEnd event. Interrupted streams (caller breaks early) do
        NOT modify history.

        Args:
            text: The user's message text.
            **extra: Additional fields forwarded to ChatRequest.extra.

        Returns:
            An async iterator of StreamEvent objects.
        """
        user_msg = Message(role="user", content=[TextPart(text=text)])
        return self._stream_impl(user_msg, **extra)

    # ---------------------------------------------------------------------------
    # Serialisation
    # ---------------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialise the conversation to a JSON string.

        Returns:
            A JSON string with schema version 1.
        """
        trim_dict = None
        if self._trim is not None:
            trim_dict = {
                "max_input_tokens": self._trim.max_input_tokens,
                "keep_system": self._trim.keep_system,
                "keep_last_n": self._trim.keep_last_n,
            }

        data = {
            "version": 1,
            "model": self._model,
            "system": self._system,
            "trim": trim_dict,
            "messages": [_message_to_dict(m) for m in self._history],
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str, client: Client) -> Conversation:
        """Reconstruct a Conversation from a JSON string produced by ``to_json``.

        Args:
            data: The JSON string.
            client: The Client to use for subsequent requests.

        Returns:
            A Conversation with the same model, system, trim, and history.
        """
        d = json.loads(data)
        trim = None
        if d.get("trim") is not None:
            t = d["trim"]
            trim = TrimStrategy(
                max_input_tokens=t["max_input_tokens"],
                keep_system=t.get("keep_system", True),
                keep_last_n=t.get("keep_last_n", 2),
            )
        history = [_dict_to_message(m) for m in d.get("messages", [])]
        return cls(
            client,
            model=d["model"],
            system=d.get("system"),
            trim=trim,
            history=history,
        )


__all__ = ["TrimStrategy", "Conversation"]
