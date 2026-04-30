"""OpenTelemetry tracing support — lazy import, no-op when disabled.

This module MUST NOT import opentelemetry at module scope.
All imports happen inside functions so the library loads cleanly
even when opentelemetry-api is not installed.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from typing import Any

from .errors import AIProxyError
from .types import ChatRequest, ChatResponse

_VERSION = "0.2.0"

# Sentinel for "no tracer" so we can distinguish from user-supplied None
_NO_TRACER = object()


def _lazy_import_otel_tracer() -> Any:
    """Import opentelemetry lazily; raise AIProxyError if not installed."""
    try:
        from opentelemetry import trace  # noqa: PLC0415

        return trace.get_tracer("norreroute", _VERSION)
    except ImportError as exc:
        raise AIProxyError(
            "trace=True requires `pip install norreroute[otel]`"
        ) from exc


def get_tracer(enabled: bool, custom: Any) -> Any:
    """Resolve the tracer to use.

    Args:
        enabled: True if ``Client(trace=True)`` was passed.
        custom: A custom tracer object if ``Client(tracer=...)`` was passed,
                else None.

    Returns:
        A tracer object, or None when tracing is disabled.

    Raises:
        AIProxyError: When enabled=True but opentelemetry-api is not installed.
    """
    if custom is not None:
        return custom
    if enabled:
        return _lazy_import_otel_tracer()
    return None


@contextlib.contextmanager
def chat_span(tracer: Any, request: ChatRequest) -> Generator[None, None, None]:
    """Context manager that wraps a chat call in an OTel span.

    When tracer is None, this is a no-op context manager.

    Args:
        tracer: An OTel Tracer object, or None for no-op.
        request: The ChatRequest being processed (used for span attributes).

    Yields:
        None — the span is automatically closed on exit.
    """
    if tracer is None:
        yield
        return

    from opentelemetry.trace import StatusCode  # noqa: PLC0415

    with tracer.start_as_current_span("norreroute.chat") as span:
        span.set_attribute("gen_ai.system", "norreroute")
        span.set_attribute("gen_ai.request.model", request.model)
        if request.max_tokens is not None:
            span.set_attribute("gen_ai.request.max_tokens", request.max_tokens)
        if request.temperature is not None:
            span.set_attribute("gen_ai.request.temperature", request.temperature)
        try:
            yield
        except Exception as exc:
            span.set_status(StatusCode.ERROR)
            span.record_exception(exc)
            raise


def _set_response_attributes(span: Any, response: ChatResponse) -> None:
    """Set span attributes from a ChatResponse."""
    span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
    span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)
    span.set_attribute("gen_ai.response.finish_reason", response.finish_reason)
    span.set_attribute("gen_ai.response.model", response.model)


@contextlib.contextmanager
def stream_span(tracer: Any, request: ChatRequest) -> Generator[None, None, None]:
    """Context manager that wraps a stream call in an OTel span.

    The span is closed exactly once, even when the caller breaks out early
    (via a break in async for, or an exception). When tracer is None, this
    is a no-op context manager.

    Args:
        tracer: An OTel Tracer object, or None for no-op.
        request: The ChatRequest being processed (used for span attributes).

    Yields:
        None — the span is automatically closed on exit.
    """
    if tracer is None:
        yield
        return

    from opentelemetry.trace import StatusCode  # noqa: PLC0415

    with tracer.start_as_current_span("norreroute.stream") as span:
        span.set_attribute("gen_ai.system", "norreroute")
        span.set_attribute("gen_ai.request.model", request.model)
        if request.max_tokens is not None:
            span.set_attribute("gen_ai.request.max_tokens", request.max_tokens)
        if request.temperature is not None:
            span.set_attribute("gen_ai.request.temperature", request.temperature)
        try:
            yield
        except Exception as exc:
            span.set_status(StatusCode.ERROR)
            span.record_exception(exc)
            raise


__all__ = ["get_tracer", "chat_span", "stream_span"]
