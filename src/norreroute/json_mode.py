"""Structured output / JSON-mode helper."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from .client import Client
from .errors import JSONValidationError
from .types import ChatRequest, ChatResponse, TextPart

# Provider-specific hints merged into ChatRequest.extra
_PROVIDER_HINTS: dict[str, dict[str, Any]] = {
    "anthropic": {"response_format": {"type": "json_object"}},
    "ollama": {"format": "json"},
}


def _merge_extra(request: ChatRequest, hint: dict[str, Any]) -> ChatRequest:
    """Return a new ChatRequest with hint merged into extra.

    Uses dataclasses.replace so the original is never mutated.
    """
    merged = {**request.extra, **hint}
    return dataclasses.replace(request, extra=merged)


def _extract_text(response: ChatResponse) -> str:
    """Extract the first TextPart from the response content."""
    for part in response.content:
        if isinstance(part, TextPart):
            return part.text
    return ""


def _parse_json(text: str, *, strict: bool) -> dict[str, Any] | None:
    """Parse JSON text; raise or return None on failure based on strict flag."""
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        return parsed
    except json.JSONDecodeError as exc:
        if strict:
            raise JSONValidationError(f"Response is not valid JSON: {exc}") from exc
        return None


def _coerce[T](
    parsed: dict[str, Any],
    schema: type[T],
    *,
    strict: bool,
) -> T | dict[str, Any] | None:
    """Coerce a parsed dict to the target schema type.

    Supports dataclasses (cls(**parsed)) and TypedDict (shallow key check).
    Returns the coerced instance, the raw dict, or None (strict=False on error).
    """
    if dataclasses.is_dataclass(schema):
        try:
            return schema(**parsed)
        except TypeError as exc:
            if strict:
                raise JSONValidationError(
                    f"Could not coerce JSON to {schema.__name__}: {exc}"
                ) from exc
            return None

    # TypedDict or other: shallow key check (best-effort, documented)
    hints = getattr(schema, "__annotations__", {})
    if hints:
        missing = [k for k in hints if k not in parsed]
        if missing and strict:
            raise JSONValidationError(
                f"JSON response missing required keys for {schema.__name__}: {missing}"
            )
    return parsed


async def json_chat[T](
    client: Client,
    request: ChatRequest,
    *,
    schema: type[T] | None = None,
    strict: bool = True,
) -> tuple[ChatResponse, T | dict[str, Any] | None]:
    """Send a chat request in JSON mode and parse/coerce the response.

    Merges a provider-specific JSON hint into ``request.extra`` before calling
    the provider. The original ``request`` is never mutated.

    Args:
        client: The Client to send the request through.
        request: The chat request. ``extra`` may already contain values; the
            hint is merged in (hint wins on key conflicts).
        schema: Optional dataclass or TypedDict class to coerce the parsed
            JSON into. ``None`` returns a raw ``dict``.
        strict: When ``True`` (default), invalid JSON or coercion failures raise
            ``JSONValidationError``. When ``False``, returns ``(response, None)``
            on failure.

    Returns:
        A tuple of (ChatResponse, parsed_value) where parsed_value is:
        - A schema instance if schema was given and coercion succeeded.
        - A ``dict`` if schema is None or schema is a TypedDict.
        - ``None`` if strict=False and parsing/coercion failed.

    Raises:
        JSONValidationError: On parse or coercion failure when strict=True.
    """
    hint = _PROVIDER_HINTS.get(client.provider_name, {})
    augmented = _merge_extra(request, hint) if hint else request

    response = await client.chat(augmented)

    text = _extract_text(response)
    parsed = _parse_json(text, strict=strict)
    if parsed is None:
        return response, None

    if schema is None:
        return response, parsed

    coerced = _coerce(parsed, schema, strict=strict)
    return response, coerced


__all__ = ["json_chat"]
