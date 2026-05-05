"""Anthropic Claude provider."""

from __future__ import annotations

import base64
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import anthropic
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from norreroute.errors import AuthenticationError, ProviderError, RateLimitError
from norreroute.registry import register
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import (
    ChatRequest,
    ChatResponse,
    ContentPart,
    ImagePart,
    TextPart,
    ToolResultPart,
    ToolSpec,
    ToolUsePart,
    Usage,
)


class AnthropicSettings(BaseSettings):
    """Configuration for the Anthropic provider.

    Reads from environment variables with the prefix ``ANTHROPIC_``.
    """

    api_key: SecretStr
    base_url: str = "https://api.anthropic.com"
    api_version: str = "2023-06-01"
    timeout_s: float = 60.0

    model_config = SettingsConfigDict(
        env_prefix="ANTHROPIC_",
        env_file=".env",
        extra="ignore",
    )


def _map_http_error(exc: anthropic.APIStatusError, provider_name: str) -> ProviderError:
    """Map an Anthropic SDK HTTP error to an aiproxy error."""
    status = exc.status_code
    raw: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        raw = exc.body if isinstance(exc.body, dict) else {}

    if status == 401:
        return AuthenticationError(
            str(exc), provider=provider_name, status=status, raw=raw
        )
    if status == 429:
        return RateLimitError(str(exc), provider=provider_name, status=status, raw=raw)
    return ProviderError(str(exc), provider=provider_name, status=status, raw=raw)


def _tool_specs_to_anthropic(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Convert ToolSpec list to Anthropic tool format."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
        }
        for t in tools
    ]


def _messages_to_anthropic(request: ChatRequest) -> list[dict[str, Any]]:
    """Serialize ChatRequest messages to Anthropic message params."""
    result: list[dict[str, Any]] = []
    for msg in request.messages:
        content_blocks: list[dict[str, Any]] = []
        for part in msg.content:
            if isinstance(part, TextPart):
                content_blocks.append({"type": "text", "text": part.text})
            elif isinstance(part, ToolUsePart):
                content_blocks.append(
                    {
                        "type": "tool_use",
                        "id": part.id,
                        "name": part.name,
                        "input": part.arguments,
                    }
                )
            elif isinstance(part, ImagePart):
                content_blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.media_type,
                            "data": base64.b64encode(part.data).decode("ascii"),
                        },
                    }
                )
            elif isinstance(part, ToolResultPart):
                content_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": part.tool_use_id,
                        "content": part.content,
                        "is_error": part.is_error,
                    }
                )
            else:
                raise TypeError(f"Unsupported content part type: {type(part).__name__}")
        # Flatten to string if single text block and role != tool
        if len(content_blocks) == 1 and content_blocks[0]["type"] == "text":
            result.append({"role": msg.role, "content": content_blocks[0]["text"]})
        else:
            result.append({"role": msg.role, "content": content_blocks})
    return result


def _parse_anthropic_content(blocks: list[Any]) -> list[ContentPart]:
    """Parse Anthropic response content blocks into neutral ContentPart list."""
    parts: list[ContentPart] = []
    for block in blocks:
        if block.type == "text":
            parts.append(TextPart(text=block.text))
        elif block.type == "tool_use":
            parts.append(
                ToolUsePart(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input),
                )
            )
    return parts


def _map_stop_reason(stop_reason: str | None) -> str:
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "tool_use",
    }
    return mapping.get(stop_reason or "", "stop")


class AnthropicProvider:
    """LLM provider backed by the Anthropic Claude API."""

    name = "anthropic"
    supports_vision: bool = True  # Claude 3+ supports vision

    def __init__(self, **kwargs: Any) -> None:
        settings = AnthropicSettings(**kwargs)
        self._settings = settings
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.timeout_s,
            default_headers={"anthropic-version": settings.api_version},
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat request to the Anthropic API."""
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": _messages_to_anthropic(request),
            "max_tokens": request.max_tokens or 1024,
        }
        if request.system:
            kwargs["system"] = request.system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.stop:
            kwargs["stop_sequences"] = list(request.stop)
        if request.tools:
            kwargs["tools"] = _tool_specs_to_anthropic(list(request.tools))

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            raise _map_http_error(exc, self.name) from exc

        raw: dict[str, Any] = {
            "id": response.id,
            "model": response.model,
            "type": response.type,
            "stop_reason": response.stop_reason,
            "stop_sequence": response.stop_sequence,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

        finish_reason = _map_stop_reason(response.stop_reason)
        content = _parse_anthropic_content(response.content)

        return ChatResponse(
            model=response.model,
            content=content,
            finish_reason=finish_reason,  # type: ignore[arg-type]
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            raw=raw,
        )

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Internal async generator that streams events from Anthropic."""
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": _messages_to_anthropic(request),
            "max_tokens": request.max_tokens or 1024,
        }
        if request.system:
            kwargs["system"] = request.system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.stop:
            kwargs["stop_sequences"] = list(request.stop)

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text_chunk in stream.text_stream:
                    yield TextDelta(text=text_chunk)
                final = await stream.get_final_message()
                yield StreamEnd(
                    finish_reason=_map_stop_reason(final.stop_reason),
                    usage=Usage(
                        input_tokens=final.usage.input_tokens,
                        output_tokens=final.usage.output_tokens,
                    ),
                )
        except anthropic.APIStatusError as exc:
            raise _map_http_error(exc, self.name) from exc

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Return an async iterator of stream events for the given request."""
        return self._stream_impl(request)

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.close()


def _factory(**kwargs: Any) -> AnthropicProvider:
    return AnthropicProvider(**kwargs)


# Self-register on import
register("anthropic", _factory)

__all__ = ["AnthropicProvider", "AnthropicSettings"]
