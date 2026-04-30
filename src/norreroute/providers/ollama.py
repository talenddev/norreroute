"""Ollama provider — uses httpx directly against the Ollama REST API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from norreroute.errors import ProviderError
from norreroute.registry import register
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import (
    ChatRequest,
    ChatResponse,
    ContentPart,
    TextPart,
    ToolResultPart,
    ToolSpec,
    ToolUsePart,
    Usage,
)


class OllamaSettings(BaseSettings):
    """Configuration for the Ollama provider.

    Reads from environment variables with the prefix ``OLLAMA_``.
    """

    base_url: str = "http://localhost:11434"
    timeout_s: float = 120.0

    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        env_file=".env",
    )


def _map_finish_reason(done_reason: str | None, has_tool_calls: bool = False) -> str:
    """Map Ollama done_reason to neutral finish_reason."""
    if has_tool_calls or done_reason == "tool_calls":
        return "tool_use"
    if done_reason == "length":
        return "length"
    return "stop"


def _messages_to_ollama(request: ChatRequest) -> list[dict[str, Any]]:
    """Serialize ChatRequest messages to Ollama message params.

    If ChatRequest.system is set, it is prepended as a system-role message.
    """
    result: list[dict[str, Any]] = []

    # Prepend system message if present
    if request.system:
        result.append({"role": "system", "content": request.system})

    for msg in request.messages:
        # Collect text and tool content
        text_parts = [p for p in msg.content if isinstance(p, TextPart)]
        tool_result_parts = [p for p in msg.content if isinstance(p, ToolResultPart)]
        tool_use_parts = [p for p in msg.content if isinstance(p, ToolUsePart)]

        if tool_result_parts:
            # Tool result messages
            for part in tool_result_parts:
                result.append({"role": "tool", "content": part.content})
        elif tool_use_parts:
            # Assistant message with tool calls
            calls = [
                {
                    "function": {
                        "name": p.name,
                        "arguments": json.dumps(p.arguments),
                    }
                }
                for p in tool_use_parts
            ]
            content = " ".join(p.text for p in text_parts) if text_parts else ""
            result.append({"role": msg.role, "content": content, "tool_calls": calls})
        else:
            content = " ".join(p.text for p in text_parts)
            result.append({"role": msg.role, "content": content})

    return result


def _tool_specs_to_ollama(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Convert ToolSpec list to Ollama/OpenAI-compatible tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _parse_ollama_content(
    message: dict[str, Any],
) -> tuple[list[ContentPart], bool]:
    """Parse Ollama response message into content parts.

    Returns:
        A tuple of (content_parts, has_tool_calls).
    """
    parts: list[ContentPart] = []
    has_tool_calls = False

    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        has_tool_calls = True
        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except json.JSONDecodeError:
                    arguments = {}
            else:
                arguments = raw_args
            parts.append(
                ToolUsePart(
                    id=call.get("id", f"call_{name}"),
                    name=name,
                    arguments=arguments,
                )
            )
    else:
        text = message.get("content", "")
        if text:
            parts.append(TextPart(text=text))

    return parts, has_tool_calls


def _raise_for_status(response: httpx.Response) -> None:
    """Map httpx HTTP errors to aiproxy ProviderError."""
    if response.status_code == 404:
        raise ProviderError(
            "model not found",
            provider="ollama",
            status=404,
            raw=_safe_json(response),
        )
    if response.status_code >= 400:
        raise ProviderError(
            f"HTTP {response.status_code}: {response.text[:200]}",
            provider="ollama",
            status=response.status_code,
            raw=_safe_json(response),
        )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """Safely parse a response body as JSON."""
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class OllamaProvider:
    """LLM provider backed by the Ollama local HTTP API."""

    name = "ollama"

    def __init__(self, **kwargs: Any) -> None:
        settings = OllamaSettings(**kwargs)
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=settings.timeout_s,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat request to the Ollama API."""
        body: dict[str, Any] = {
            "model": request.model,
            "messages": _messages_to_ollama(request),
            "stream": False,
        }
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if request.stop:
            options["stop"] = list(request.stop)
        if options:
            body["options"] = options
        if request.tools:
            body["tools"] = _tool_specs_to_ollama(list(request.tools))

        response = await self._client.post("/api/chat", json=body)
        _raise_for_status(response)
        data: dict[str, Any] = response.json()

        message = data.get("message", {})
        content, has_tool_calls = _parse_ollama_content(message)
        finish_reason = _map_finish_reason(
            data.get("done_reason"), has_tool_calls=has_tool_calls
        )

        return ChatResponse(
            model=data.get("model", request.model),
            content=content,
            finish_reason=finish_reason,  # type: ignore[arg-type]
            usage=Usage(
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            ),
            raw=data,
        )

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Internal async generator that streams events from Ollama."""
        body: dict[str, Any] = {
            "model": request.model,
            "messages": _messages_to_ollama(request),
            "stream": True,
        }
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if options:
            body["options"] = options

        async with self._client.stream("POST", "/api/chat", json=body) as response:
            _raise_for_status(response)
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = chunk.get("message", {})
                text = msg.get("content", "")
                if text:
                    yield TextDelta(text=text)

                if chunk.get("done", False):
                    yield StreamEnd(
                        finish_reason=_map_finish_reason(chunk.get("done_reason")),
                        usage=Usage(
                            input_tokens=chunk.get("prompt_eval_count", 0),
                            output_tokens=chunk.get("eval_count", 0),
                        ),
                    )
                    return

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Return an async iterator of stream events for the given request."""
        return self._stream_impl(request)

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()


def _factory(**kwargs: Any) -> OllamaProvider:
    return OllamaProvider(**kwargs)


# Self-register on import
register("ollama", _factory)

__all__ = ["OllamaProvider", "OllamaSettings"]
