# Provider Guide

## Anthropic Claude

### Setup

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or pass it at construction time:

```python
from norreroute import Client

client = Client("anthropic", api_key="sk-ant-...")
```

### Settings

| Env var | kwarg | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | `api_key` | — | **Required.** Anthropic API key |
| `ANTHROPIC_BASE_URL` | `base_url` | `https://api.anthropic.com` | Override for proxies or private deployments |
| `ANTHROPIC_API_VERSION` | `api_version` | `2023-06-01` | Sent as the `anthropic-version` request header |
| `ANTHROPIC_TIMEOUT_S` | `timeout_s` | `60.0` | Request timeout in seconds |

A `.env` file in the working directory is read automatically.

### Supported Models

Any model string accepted by the Anthropic Messages API. Common values at time of writing:

| Model | Context | Notes |
|---|---|---|
| `claude-3-5-sonnet-20241022` | 200k | Latest Sonnet |
| `claude-3-5-haiku-20241022` | 200k | Latest Haiku |
| `claude-3-haiku-20240307` | 200k | Fast, low cost |
| `claude-3-opus-20240229` | 200k | Highest capability |

Check [docs.anthropic.com/models](https://docs.anthropic.com/en/docs/about-claude/models) for the current list.

### Tool Calling

Anthropic tool calling is fully supported. `ToolSpec.parameters` maps to `input_schema` in the Anthropic wire format. Responses with `stop_reason == "tool_use"` produce `finish_reason == "tool_use"` and `ToolUsePart` blocks in `content`.

Multi-turn tool use (sending results back):

```python
import asyncio
from norreroute import Client
from norreroute.types import (
    ChatRequest, Message, TextPart,
    ToolSpec, ToolUsePart, ToolResultPart,
)

async def main() -> None:
    client = Client("anthropic")

    tool = ToolSpec(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )

    # Turn 1: model requests a tool call
    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(role="user", content=[TextPart(text="What's the weather in Paris?")])
        ],
        tools=[tool],
        max_tokens=256,
    )
    response = await client.chat(request)

    tool_part = next(p for p in response.content if isinstance(p, ToolUsePart))
    city = tool_part.arguments["city"]   # "Paris"

    # Turn 2: send tool result back
    follow_up = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(role="user", content=[TextPart(text="What's the weather in Paris?")]),
            Message(role="assistant", content=list(response.content)),
            Message(
                role="user",
                content=[
                    ToolResultPart(
                        tool_use_id=tool_part.id,
                        content='{"temperature": 18, "condition": "sunny"}',
                    )
                ],
            ),
        ],
        tools=[tool],
        max_tokens=256,
    )
    final = await client.chat(follow_up)
    print(final.content[0].text)
    await client.aclose()

asyncio.run(main())
```

### Streaming

The Anthropic provider uses `anthropic.AsyncAnthropic.messages.stream` and exposes the text stream via `TextDelta` events. Tool call streaming emits `StreamEnd` only — `ToolCallDelta` is not emitted by this provider. Retrieve tool calls from a non-streaming `chat` call instead.

### JSON Mode

When using `json_chat` with an Anthropic client, the following hint is merged into `ChatRequest.extra` automatically:

```python
{"response_format": {"type": "json_object"}}
```

You do not need to set this manually. The original `ChatRequest` is never mutated.

```python
from norreroute import json_chat

response, data = await json_chat(client, request)
```

### OpenTelemetry

When tracing is enabled, the `gen_ai.system` attribute on every span is set to `"norreroute"` (not the provider name). All other `gen_ai.*` attributes follow the OpenTelemetry Semantic Conventions for Generative AI.

### Provider-Specific Parameters via `extra`

Pass Anthropic-specific parameters through `ChatRequest.extra`. These are not validated:

```python
request = ChatRequest(
    model="claude-3-haiku-20240307",
    messages=[...],
    extra={"cache_control": {"type": "ephemeral"}},
)
```

Note: `extra` is stored on the request object but the current provider implementation does not forward it to the API call. Use this field once the provider is extended to pass it through.

### Error Mapping

| HTTP status | Exception |
|---|---|
| 401 | `AuthenticationError` |
| 429 | `RateLimitError` |
| Any other 4xx/5xx | `ProviderError` |

---

## Ollama

### Setup

Run Ollama locally with Docker:

```bash
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama
```

Then pull a model:

```bash
docker exec ollama ollama pull llama3
```

Or install Ollama natively from [ollama.com](https://ollama.com) and run `ollama serve`.

### Settings

| Env var | kwarg | Default | Description |
|---|---|---|---|
| `OLLAMA_BASE_URL` | `base_url` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT_S` | `timeout_s` | `120.0` | Request timeout in seconds (models can be slow on first run) |

### Supported Models

Any model available in your Ollama instance. Pull models with `ollama pull <name>`.

Common models:

| Model | Notes |
|---|---|
| `llama3` | Meta Llama 3 8B |
| `llama3:70b` | Meta Llama 3 70B |
| `mistral` | Mistral 7B |
| `gemma2` | Google Gemma 2 |
| `qwen2.5` | Alibaba Qwen 2.5 |

For tool calling, use models that explicitly support it (e.g. `llama3.1`, `mistral-nemo`). Check the Ollama model library for the `tools` tag.

### System Prompt Handling

`ChatRequest.system` is prepended as a `{"role": "system", "content": "..."}` message in the Ollama request. This is different from Anthropic where it is a top-level parameter.

### Tool Calling

Ollama tool calling uses the OpenAI-compatible `tools` format. `ToolSpec` is translated to:

```json
{
  "type": "function",
  "function": {
    "name": "...",
    "description": "...",
    "parameters": { ... }
  }
}
```

Tool call responses are parsed from `message.tool_calls` in the Ollama response. If the response contains tool calls, `finish_reason` is set to `"tool_use"` regardless of `done_reason`.

When sending tool results back, use `role="tool"` and a `ToolResultPart`. Each `ToolResultPart` becomes a separate `{"role": "tool", "content": "..."}` message in the Ollama request.

### Streaming Quirk

The Ollama provider streams token-by-token over NDJSON (`/api/chat` with `"stream": true`). Streaming does not support tool calls — use non-streaming `chat` for tool use with Ollama.

### JSON Mode

When using `json_chat` with an Ollama client, the following hint is merged into `ChatRequest.extra` automatically:

```python
{"format": "json"}
```

You do not need to set this manually. The original `ChatRequest` is never mutated.

```python
from norreroute import json_chat

response, data = await json_chat(client, request)
```

### Cost Estimation

Ollama models run locally. `estimate_cost` always returns `$0.00` for Ollama models in the built-in pricing table (`llama3.1`, `qwen2.5`). `CostEstimate.is_estimate` will be `False` when Ollama reports token usage.

### OpenTelemetry

When tracing is enabled, the `gen_ai.system` attribute on every span is set to `"norreroute"` (not the provider name). All other `gen_ai.*` attributes follow the OpenTelemetry Semantic Conventions for Generative AI.

### Error Mapping

| HTTP status | Exception |
|---|---|
| 404 | `ProviderError` with message `"model not found"` |
| Any other 4xx/5xx | `ProviderError` |

Ollama does not distinguish auth errors (it has no auth by default).

---

## Implementing a Custom Provider

### Step 1: Satisfy the `Provider` Protocol

You do not subclass anything. Implement three methods and a `name` attribute:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import ChatRequest, ChatResponse, TextPart, Usage


class MyProvider:
    name = "my-provider"

    def __init__(self, **kwargs: Any) -> None:
        # read your settings here
        self._base_url: str = kwargs.get("base_url", "https://my-api.example.com")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        # call your API, parse the response
        # translate ChatRequest fields to your API's format
        # translate the response to ChatResponse
        return ChatResponse(
            model=request.model,
            content=[TextPart(text="Hello from my provider")],
            finish_reason="stop",
            usage=Usage(input_tokens=10, output_tokens=5),
            raw={},   # put the raw API response here
        )

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        # yield TextDelta events as chunks arrive
        yield TextDelta(text="Hello ")
        yield TextDelta(text="world")
        yield StreamEnd(finish_reason="stop", usage=None)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        # return the async generator, do not await it
        return self._stream_impl(request)

    async def aclose(self) -> None:
        # close your HTTP client or any other resources
        pass
```

### Step 2: Register the Provider

**Option A — Direct registration (scripts, apps):**

```python
from norreroute.registry import register

register("my-provider", lambda **kwargs: MyProvider(**kwargs))
```

**Option B — Self-register on import (library packages):**

```python
# At the bottom of your provider module:
from norreroute.registry import register

register("my-provider", lambda **kwargs: MyProvider(**kwargs))
```

Import your module before constructing a `Client`:

```python
import my_package.providers  # triggers self-registration
from norreroute import Client

client = Client("my-provider")
```

**Option C — Entry point (installable packages):**

In `pyproject.toml`:

```toml
[project.entry-points."aiproxy.providers"]
my-provider = "my_package.providers:factory"
```

Where `factory` is a callable that accepts keyword arguments and returns a `Provider`:

```python
# my_package/providers.py
def factory(**kwargs: Any) -> MyProvider:
    return MyProvider(**kwargs)
```

aiproxy discovers this entry point automatically when `resolve` is called with `"my-provider"` and the name is not already registered.

### Step 3: Handle Errors

Map your API's error responses to aiproxy's error hierarchy:

```python
from norreroute.errors import AuthenticationError, ProviderError, RateLimitError

def _map_error(status: int, message: str) -> ProviderError:
    if status == 401:
        return AuthenticationError(message, provider="my-provider", status=status)
    if status == 429:
        return RateLimitError(message, provider="my-provider", status=status)
    return ProviderError(message, provider="my-provider", status=status)
```

### Step 4: Verify Protocol Conformance

```python
from norreroute.provider import Provider

provider = MyProvider()
assert isinstance(provider, Provider), "Provider protocol not satisfied"
```

This uses `@runtime_checkable` and checks for the presence of `name`, `chat`, `stream`, and `aclose`.

### JSON Mode with Custom Providers

`json_chat` looks up the provider name via `client.provider_name` to select the hint to merge. If your provider name is not `"anthropic"` or `"ollama"`, no hint is merged and the request is sent as-is. Add the appropriate JSON instruction to your system prompt or `ChatRequest.extra` manually.

### Cost Estimation with Custom Providers

`estimate_cost` will raise `UnknownModelError` for models not in the built-in table. Pass a `pricing` dict to supply prices for your models:

```python
from norreroute import ModelPrice, estimate_cost

my_prices = {
    "my-model-v1": ModelPrice(input_per_mtok_usd=0.50, output_per_mtok_usd=1.50),
}
cost = estimate_cost(response, pricing=my_prices)
```
