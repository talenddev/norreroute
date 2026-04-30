"""Unit tests for tracing.py — OTel span attributes and no-op when disabled."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from norreroute.client import Client
from norreroute.errors import AIProxyError
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.tracing import chat_span, get_tracer, stream_span
from norreroute.types import ChatRequest, ChatResponse, Message, TextPart, Usage

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_tracer() -> tuple[Any, InMemorySpanExporter]:
    """Create an in-memory tracer and exporter pair for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    return tracer, exporter


def _make_request(
    model: str = "test-model",
    max_tokens: int | None = 256,
    temperature: float | None = 0.5,
) -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=[Message(role="user", content=[TextPart(text="hi")])],
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _make_response(model: str = "test-model") -> ChatResponse:
    return ChatResponse(
        model=model,
        content=[TextPart(text="ok")],
        finish_reason="stop",
        usage=Usage(input_tokens=5, output_tokens=5),
        raw={},
    )


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        response: ChatResponse | None = None,
        stream_events: list[Any] | None = None,
    ) -> None:
        self._response = response or _make_response()
        self._stream_events = stream_events or [
            TextDelta(text="hi"),
            StreamEnd(finish_reason="stop", usage=None),
        ]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return self._response

    async def _gen(self, events: list[Any]) -> AsyncIterator[StreamEvent]:
        for event in events:
            if isinstance(event, BaseException):
                raise event
            yield event  # type: ignore[misc]

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._gen(self._stream_events)

    async def aclose(self) -> None:
        pass


# ---------------------------------------------------------------------------
# get_tracer
# ---------------------------------------------------------------------------


class TestGetTracer:
    def test_disabled_returns_none(self) -> None:
        assert get_tracer(False, None) is None

    def test_custom_tracer_returned(self) -> None:
        sentinel = object()
        result = get_tracer(False, sentinel)
        assert result is sentinel

    def test_trace_true_returns_tracer(self) -> None:
        result = get_tracer(True, None)
        assert result is not None

    def test_trace_true_missing_otel_raises(self) -> None:
        with (
            patch.dict(sys.modules, {"opentelemetry": None}),
            pytest.raises(AIProxyError, match="norreroute\\[otel\\]"),
        ):
            get_tracer(True, None)


# ---------------------------------------------------------------------------
# chat_span — no-op
# ---------------------------------------------------------------------------


class TestChatSpanNoop:
    def test_none_tracer_is_noop(self) -> None:
        """chat_span with tracer=None must not raise and must be a context manager."""
        req = _make_request()
        with chat_span(None, req):
            pass  # Should not raise

    def test_none_tracer_does_not_require_otel(self) -> None:
        req = _make_request()
        with patch.dict(sys.modules, {"opentelemetry": None}), chat_span(None, req):
            pass


# ---------------------------------------------------------------------------
# chat_span — span attributes
# ---------------------------------------------------------------------------


class TestChatSpanAttributes:
    def test_request_attributes_set(self) -> None:
        tracer, exporter = _make_tracer()
        req = _make_request(model="my-model", max_tokens=512, temperature=0.7)
        with chat_span(tracer, req):
            pass
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs["gen_ai.system"] == "norreroute"
        assert attrs["gen_ai.request.model"] == "my-model"
        assert attrs["gen_ai.request.max_tokens"] == 512
        assert attrs["gen_ai.request.temperature"] == pytest.approx(0.7)

    def test_optional_attributes_omitted_when_none(self) -> None:
        tracer, exporter = _make_tracer()
        req = _make_request(max_tokens=None, temperature=None)
        with chat_span(tracer, req):
            pass
        spans = exporter.get_finished_spans()
        attrs = spans[0].attributes
        assert "gen_ai.request.max_tokens" not in attrs
        assert "gen_ai.request.temperature" not in attrs

    def test_exception_sets_error_status(self) -> None:
        tracer, exporter = _make_tracer()
        req = _make_request()
        with pytest.raises(ValueError), chat_span(tracer, req):
            raise ValueError("boom")
        spans = exporter.get_finished_spans()
        from opentelemetry.trace import StatusCode

        assert spans[0].status.status_code == StatusCode.ERROR


# ---------------------------------------------------------------------------
# stream_span — no-op
# ---------------------------------------------------------------------------


class TestStreamSpanNoop:
    def test_none_tracer_is_noop(self) -> None:
        req = _make_request()
        with stream_span(None, req):
            pass

    def test_span_closes_once_on_early_break(self) -> None:
        """stream_span must close exactly once even if caller breaks early."""
        tracer, exporter = _make_tracer()
        req = _make_request()
        with stream_span(tracer, req):
            pass  # Simulate an early break (no events consumed)
        # Span must be finished exactly once
        spans = exporter.get_finished_spans()
        assert len(spans) == 1


# ---------------------------------------------------------------------------
# stream_span — span attributes and close-once
# ---------------------------------------------------------------------------


class TestStreamSpanAttributes:
    def test_request_attributes_set(self) -> None:
        tracer, exporter = _make_tracer()
        req = _make_request(model="stream-model", max_tokens=100, temperature=0.3)
        with stream_span(tracer, req):
            pass
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs["gen_ai.system"] == "norreroute"
        assert attrs["gen_ai.request.model"] == "stream-model"
        assert attrs["gen_ai.request.max_tokens"] == 100

    def test_exception_sets_error_status(self) -> None:
        tracer, exporter = _make_tracer()
        req = _make_request()
        with pytest.raises(RuntimeError), stream_span(tracer, req):
            raise RuntimeError("stream error")
        spans = exporter.get_finished_spans()
        from opentelemetry.trace import StatusCode

        assert spans[0].status.status_code == StatusCode.ERROR


# ---------------------------------------------------------------------------
# Client integration tests
# ---------------------------------------------------------------------------


class TestClientTracing:
    @pytest.mark.asyncio
    async def test_trace_false_no_overhead(self) -> None:
        """Client(trace=False) must work with no OTel installed."""
        provider = FakeProvider()
        with patch.dict(sys.modules, {"opentelemetry": None}):
            # trace=False should not import opentelemetry at all
            client = Client(provider=provider)
            assert client._tracer is None

    @pytest.mark.asyncio
    async def test_client_trace_true_produces_span(self) -> None:
        tracer, exporter = _make_tracer()
        provider = FakeProvider()
        client = Client(provider=provider, tracer=tracer)
        req = _make_request()
        await client.chat(req)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = spans[0].attributes
        assert attrs["gen_ai.request.model"] == "test-model"
        assert attrs["gen_ai.usage.input_tokens"] == 5
        assert attrs["gen_ai.usage.output_tokens"] == 5
        assert attrs["gen_ai.response.finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_client_stream_span_closes_on_early_break(self) -> None:
        import gc

        tracer, exporter = _make_tracer()
        provider = FakeProvider()
        client = Client(provider=provider, tracer=tracer)
        req = _make_request()
        # Explicitly manage the async iterator so we can close it
        agen = client.stream(req).__aiter__()
        try:
            await agen.__anext__()  # consume one event
        finally:
            # Explicitly close the generator — triggers the finally: span.end()
            await agen.aclose()
        # Force GC to ensure finalizers run
        gc.collect()
        # Span must be finished exactly once
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

    @pytest.mark.asyncio
    async def test_client_no_tracer_chat_works(self) -> None:
        provider = FakeProvider()
        client = Client(provider=provider)  # no trace=, no tracer=
        req = _make_request()
        resp = await client.chat(req)
        assert resp.model == "test-model"
