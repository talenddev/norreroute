# aiproxy

A pragmatic, provider-agnostic Python library for calling LLMs. Starts with Anthropic Claude and Ollama; designed so adding OpenAI or Gemini later is mechanical, not architectural.

## Providers

| Provider | Status | Transport |
|---|---|---|
| Anthropic Claude | Supported | anthropic SDK |
| Ollama | Supported | httpx (direct REST) |
| OpenAI / Gemini | Not built | Planned |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv add aiproxy
```

## Quick Start

### Non-streaming (async)

```python
import asyncio
from aiproxy import Client
from aiproxy.types import ChatRequest, Message, TextPart

async def main():
    client = Client("anthropic", api_key="sk-ant-...")
    # or: client = Client("anthropic")  # reads ANTHROPIC_API_KEY from env

    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(role="user", content=[TextPart(text="What is 2 + 2?")])
        ],
        system="You are a helpful math assistant.",
        max_tokens=256,
    )

    response = await client.chat(request)
    print(response.content[0].text)   # "4"
    print(response.usage.output_tokens)
    await client.aclose()

asyncio.run(main())
```

### Sync wrapper (scripts / CLIs)

```python
from aiproxy import Client
from aiproxy.types import ChatRequest, Message, TextPart

client = Client("ollama", base_url="http://localhost:11434")

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
async def stream_example():
    client = Client("anthropic")
    from aiproxy.streaming import TextDelta, StreamEnd

    async for event in client.stream(request):
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, StreamEnd):
            print()
            break
```

### Tool calling

```python
from aiproxy.types import ChatRequest, Message, TextPart, ToolSpec, ToolUsePart

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
    messages=[Message(role="user", content=[TextPart(text="What's the weather in Paris?")])],
    tools=[weather_tool],
    max_tokens=256,
)

response = await client.chat(request)
for part in response.content:
    if isinstance(part, ToolUsePart):
        print(f"Tool call: {part.name}({part.arguments})")
        # {"city": "Paris"}
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

## Provider registration

Providers self-register on import. You can also register third-party providers:

```python
from aiproxy.registry import register

register("my-provider", MyProviderFactory)
client = Client("my-provider", some_kwarg="value")
```

Or declare an entry point in your package:

```toml
[project.entry-points."aiproxy.providers"]
my-provider = "my_package.providers:factory"
```

## Error handling

```python
from aiproxy.errors import AuthenticationError, RateLimitError, ProviderError

try:
    response = await client.chat(request)
except AuthenticationError as e:
    print(f"Bad API key: {e}")
except RateLimitError as e:
    print(f"Rate limited (status {e.status})")
except ProviderError as e:
    print(f"Provider error from {e.provider}: {e}")
```

## Development

```bash
# Install dependencies (including dev)
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Lint
uv run ruff check src/

# Type check
uv run mypy src/
```

## Not built (out of scope for v0.1)

- Retry / exponential backoff
- Response caching
- Rate limiting / quota tracking
- Token counting / cost estimation
- Prompt templating
- Conversation / session persistence
- Embeddings, image generation, audio APIs
- Structured-output helpers
- Multi-provider fallback / load balancing
- Observability hooks (OpenTelemetry)

## Architecture

See [docs/architecture-brief.md](docs/architecture-brief.md) for the design rationale and key tradeoffs.
