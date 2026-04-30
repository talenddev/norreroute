# norreroute

A provider-agnostic Python library for calling LLMs. Wraps Anthropic Claude and Ollama behind a single `Client` interface so switching providers is a one-line change, not a refactor.

## Installation

```bash
uv add norreroute
# or
pip install norreroute
```

Requires Python 3.12+.

## Quick Start

### Non-streaming (Anthropic)

```python
import asyncio
from norreroute import Client
from norreroute.types import ChatRequest, Message, TextPart

async def main() -> None:
    client = Client("anthropic")  # reads ANTHROPIC_API_KEY from env

    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[Message(role="user", content=[TextPart(text="What is 2 + 2?")])],
        system="You are a helpful math assistant.",
        max_tokens=256,
    )

    response = await client.chat(request)
    print(response.content[0].text)       # "4"
    print(response.usage.output_tokens)
    await client.aclose()

asyncio.run(main())
```

### Non-streaming (Ollama)

```python
from norreroute import Client
from norreroute.types import ChatRequest, Message, TextPart

client = Client("ollama")  # defaults to http://localhost:11434

request = ChatRequest(
    model="llama3",
    messages=[Message(role="user", content=[TextPart(text="Hello")])],
)

response = client.chat_sync(request)
print(response.content[0].text)
```

`chat_sync` calls `asyncio.run` internally — do not use it inside a running event loop.

### Streaming

```python
import asyncio
from norreroute import Client
from norreroute.streaming import StreamEnd, TextDelta
from norreroute.types import ChatRequest, Message, TextPart

async def main() -> None:
    client = Client("anthropic")

    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[Message(role="user", content=[TextPart(text="Count to five.")])],
        max_tokens=128,
    )

    async for event in client.stream(request):
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, StreamEnd):
            print()
            break

    await client.aclose()

asyncio.run(main())
```

### Tool calling

```python
import asyncio
from norreroute import Client
from norreroute.types import ChatRequest, Message, TextPart, ToolSpec, ToolUsePart

async def main() -> None:
    client = Client("anthropic")

    weather_tool = ToolSpec(
        name="get_weather",
        description="Get the current weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )

    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(role="user", content=[TextPart(text="What's the weather in Paris?")])
        ],
        tools=[weather_tool],
        max_tokens=256,
    )

    response = await client.chat(request)
    for part in response.content:
        if isinstance(part, ToolUsePart):
            print(f"Tool: {part.name}, args: {part.arguments}")
            # Tool: get_weather, args: {'city': 'Paris'}

    await client.aclose()

asyncio.run(main())
```

## Configuration

### Anthropic

| Env var | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | API base URL |
| `ANTHROPIC_API_VERSION` | No | `2023-06-01` | API version header |
| `ANTHROPIC_TIMEOUT_S` | No | `60.0` | Request timeout in seconds |

### Ollama

| Env var | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server base URL |
| `OLLAMA_TIMEOUT_S` | No | `120.0` | Request timeout in seconds |

Settings can also be passed as keyword arguments to `Client`:

```python
client = Client("anthropic", api_key="sk-ant-...", timeout_s=30.0)
client = Client("ollama", base_url="http://gpu-host:11434")
```

A `.env` file in the working directory is read automatically by each provider.

## Adding a Custom Provider

Implement the `Provider` protocol and register a factory:

```python
from collections.abc import AsyncIterator
from norreroute.registry import register
from norreroute.streaming import StreamEnd, StreamEvent, TextDelta
from norreroute.types import ChatRequest, ChatResponse, TextPart, Usage


class MyProvider:
    name = "my-provider"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        # call your API here
        return ChatResponse(
            model=request.model,
            content=[TextPart(text="response text")],
            finish_reason="stop",
            usage=Usage(input_tokens=10, output_tokens=5),
            raw={},
        )

    async def _stream_impl(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        yield TextDelta(text="response text")
        yield StreamEnd(finish_reason="stop", usage=None)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._stream_impl(request)

    async def aclose(self) -> None:
        pass


register("my-provider", lambda **kwargs: MyProvider())

client = Client("my-provider")
```

Or declare an entry point so your package registers automatically on install:

```toml
[project.entry-points."aiproxy.providers"]
my-provider = "my_package.providers:factory"
```

## Error Handling

```python
from norreroute.errors import (
    AIProxyError,
    AuthenticationError,
    ConfigurationError,
    ProviderError,
    RateLimitError,
    TimeoutError_,
)

try:
    response = await client.chat(request)
except AuthenticationError as e:
    print(f"Bad API key — provider={e.provider}, status={e.status}")
except RateLimitError as e:
    print(f"Rate limited — retry after back-off")
except TimeoutError_ as e:
    print(f"Request timed out")
except ProviderError as e:
    print(f"Provider error from {e.provider}: HTTP {e.status}")
except ConfigurationError as e:
    print(f"Bad configuration: {e}")
```

`TimeoutError_` has a trailing underscore to avoid shadowing the built-in `TimeoutError`.

## Provider Comparison

| Feature | Anthropic | Ollama |
|---|---|---|
| Non-streaming chat | Yes | Yes |
| Streaming | Yes | Yes |
| Tool calling | Yes | Yes (models that support it) |
| `system` prompt | Native top-level param | Prepended as `system` role message |
| `temperature` | Yes | Yes |
| `max_tokens` | Yes | Yes (mapped to `num_predict`) |
| `stop` sequences | Yes | Yes |
| Auth | `ANTHROPIC_API_KEY` | None (local) |
| Transport | Anthropic SDK | httpx direct REST |
| `finish_reason` values | `stop`, `length`, `tool_use` | `stop`, `length`, `tool_use` |

## Documentation

- [API Reference](docs/api-reference.md) — all types, methods, and errors
- [Provider Guide](docs/providers.md) — provider-specific details, custom provider walkthrough
- [Local Setup](docs/local-setup.md) — contributor setup, running tests

## Out of Scope (v0.1)

Retry/backoff, caching, rate-limit tracking, token counting, prompt templating,
session persistence, embeddings, structured-output helpers, multi-provider fallback,
OpenTelemetry hooks.
