"""Unit tests for json_mode.py — json_chat and provider_name property."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest

from norreroute.client import Client
from norreroute.errors import JSONValidationError
from norreroute.json_mode import json_chat
from norreroute.streaming import StreamEvent
from norreroute.types import ChatRequest, ChatResponse, Message, TextPart, Usage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _Point:
    x: int
    y: int


class _PointTypedDict:
    """Minimal TypedDict-like class with __annotations__."""

    __annotations__ = {"x": int, "y": int}


def _make_request(extra: dict[str, Any] | None = None) -> ChatRequest:
    return ChatRequest(
        model="test-model",
        messages=[Message(role="user", content=[TextPart(text="return json")])],
        extra=extra or {},
    )


def _make_response(text: str, model: str = "test-model") -> ChatResponse:
    return ChatResponse(
        model=model,
        content=[TextPart(text=text)],
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=10),
        raw={},
    )


class FakeProvider:
    """Provider that echoes back the last request and returns a scripted response."""

    def __init__(self, name: str, response_text: str) -> None:
        self.name = name
        self._text = response_text
        self.last_request: ChatRequest | None = None

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self.last_request = request
        return _make_response(self._text)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# provider_name tests
# ---------------------------------------------------------------------------


class TestClientProviderName:
    def test_provider_name_anthropic(self) -> None:
        provider = FakeProvider("anthropic", "{}")
        client = Client(provider=provider)
        assert client.provider_name == "anthropic"

    def test_provider_name_ollama(self) -> None:
        provider = FakeProvider("ollama", "{}")
        client = Client(provider=provider)
        assert client.provider_name == "ollama"

    def test_provider_name_custom(self) -> None:
        provider = FakeProvider("my-provider", "{}")
        client = Client(provider=provider)
        assert client.provider_name == "my-provider"


# ---------------------------------------------------------------------------
# json_chat — provider hint merging
# ---------------------------------------------------------------------------


class TestJsonChatHints:
    @pytest.mark.asyncio
    async def test_anthropic_hint_merged(self) -> None:
        provider = FakeProvider("anthropic", '{"key": "val"}')
        client = Client(provider=provider)
        req = _make_request()
        await json_chat(client, req)
        assert provider.last_request is not None
        assert provider.last_request.extra.get("response_format") == {
            "type": "json_object"
        }

    @pytest.mark.asyncio
    async def test_ollama_hint_merged(self) -> None:
        provider = FakeProvider("ollama", '{"key": "val"}')
        client = Client(provider=provider)
        req = _make_request()
        await json_chat(client, req)
        assert provider.last_request is not None
        assert provider.last_request.extra.get("format") == "json"

    @pytest.mark.asyncio
    async def test_unknown_provider_no_hint(self) -> None:
        provider = FakeProvider("unknown-llm", '{"key": "val"}')
        client = Client(provider=provider)
        req = _make_request()
        await json_chat(client, req)
        assert provider.last_request is not None
        assert provider.last_request.extra == {}

    @pytest.mark.asyncio
    async def test_original_request_not_mutated(self) -> None:
        provider = FakeProvider("anthropic", '{"key": "val"}')
        client = Client(provider=provider)
        req = _make_request(extra={"my_key": "my_val"})
        await json_chat(client, req)
        # Original should be unchanged
        assert req.extra == {"my_key": "my_val"}
        # Augmented should have both
        assert provider.last_request is not None
        assert "my_key" in provider.last_request.extra
        assert "response_format" in provider.last_request.extra

    @pytest.mark.asyncio
    async def test_existing_extra_preserved(self) -> None:
        provider = FakeProvider("ollama", '{"a": 1}')
        client = Client(provider=provider)
        req = _make_request(extra={"stream": False})
        await json_chat(client, req)
        assert provider.last_request is not None
        assert provider.last_request.extra["stream"] is False
        assert provider.last_request.extra["format"] == "json"


# ---------------------------------------------------------------------------
# json_chat — schema=None (returns dict)
# ---------------------------------------------------------------------------


class TestJsonChatNoSchema:
    @pytest.mark.asyncio
    async def test_returns_parsed_dict(self) -> None:
        provider = FakeProvider("fake", '{"x": 1, "y": 2}')
        client = Client(provider=provider)
        resp, parsed = await json_chat(client, _make_request())
        assert isinstance(parsed, dict)
        assert parsed == {"x": 1, "y": 2}

    @pytest.mark.asyncio
    async def test_invalid_json_strict_raises(self) -> None:
        provider = FakeProvider("fake", "not json at all")
        client = Client(provider=provider)
        with pytest.raises(JSONValidationError):
            await json_chat(client, _make_request(), strict=True)

    @pytest.mark.asyncio
    async def test_invalid_json_not_strict_returns_none(self) -> None:
        provider = FakeProvider("fake", "not json")
        client = Client(provider=provider)
        resp, parsed = await json_chat(client, _make_request(), strict=False)
        assert parsed is None


# ---------------------------------------------------------------------------
# json_chat — dataclass coercion
# ---------------------------------------------------------------------------


class TestJsonChatDataclassCoercion:
    @pytest.mark.asyncio
    async def test_dataclass_happy_path(self) -> None:
        provider = FakeProvider("fake", '{"x": 10, "y": 20}')
        client = Client(provider=provider)
        resp, point = await json_chat(client, _make_request(), schema=_Point)
        assert isinstance(point, _Point)
        assert point.x == 10
        assert point.y == 20

    @pytest.mark.asyncio
    async def test_dataclass_missing_field_strict_raises(self) -> None:
        provider = FakeProvider("fake", '{"x": 10}')  # missing "y"
        client = Client(provider=provider)
        with pytest.raises(JSONValidationError):
            await json_chat(client, _make_request(), schema=_Point, strict=True)

    @pytest.mark.asyncio
    async def test_dataclass_missing_field_not_strict_returns_none(self) -> None:
        provider = FakeProvider("fake", '{"x": 10}')
        client = Client(provider=provider)
        resp, result = await json_chat(
            client, _make_request(), schema=_Point, strict=False
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_dataclass_extra_field_raises_strict(self) -> None:
        """Extra fields cause TypeError from the dataclass constructor."""
        provider = FakeProvider("fake", '{"x": 10, "y": 20, "z": 30}')
        client = Client(provider=provider)
        with pytest.raises(JSONValidationError):
            await json_chat(client, _make_request(), schema=_Point, strict=True)

    @pytest.mark.asyncio
    async def test_dataclass_extra_field_not_strict_returns_none(self) -> None:
        provider = FakeProvider("fake", '{"x": 10, "y": 20, "z": 30}')
        client = Client(provider=provider)
        resp, result = await json_chat(
            client, _make_request(), schema=_Point, strict=False
        )
        assert result is None


# ---------------------------------------------------------------------------
# json_chat — TypedDict-like coercion
# ---------------------------------------------------------------------------


class TestJsonChatTypedDictCoercion:
    @pytest.mark.asyncio
    async def test_typeddict_happy_path_returns_dict(self) -> None:
        provider = FakeProvider("fake", '{"x": 10, "y": 20}')
        client = Client(provider=provider)
        resp, result = await json_chat(
            client,
            _make_request(),
            schema=_PointTypedDict,  # type: ignore[type-abstract]
        )
        assert isinstance(result, dict)
        assert result["x"] == 10

    @pytest.mark.asyncio
    async def test_typeddict_missing_key_strict_raises(self) -> None:
        provider = FakeProvider("fake", '{"x": 10}')  # missing "y"
        client = Client(provider=provider)
        with pytest.raises(JSONValidationError):
            await json_chat(
                client,
                _make_request(),
                schema=_PointTypedDict,  # type: ignore[type-abstract]
                strict=True,
            )
