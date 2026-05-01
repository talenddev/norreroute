# norreroute

A provider-agnostic Python library for calling LLMs. Wraps Anthropic Claude and Ollama behind a single `Client` interface so switching providers is a one-line change, not a refactor.

## Installation

```bash
uv add norreroute
# or
pip install norreroute
```

For OpenTelemetry tracing support:

```bash
uv add "norreroute[otel]"
# or
pip install "norreroute[otel]"
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

## Retry / Exponential Backoff

Pass `retry=True` to enable retries with the default policy, or pass a `RetryPolicy` for fine-grained control:

```python
from norreroute import Client, RetryPolicy

# Default policy: 3 attempts, 0.5s initial delay, 2x multiplier, 30s cap
client = Client("anthropic", retry=True)

# Custom policy
client = Client(
    "anthropic",
    retry=RetryPolicy(
        max_attempts=5,
        initial_delay=1.0,
        max_delay=60.0,
        multiplier=2.0,
    ),
)
```

Retries apply to `RateLimitError` and `ProviderError` by default. `AuthenticationError` is not retried. Stream retries happen only before the first content event is yielded — partial responses are never re-emitted.

Default `RetryPolicy` values:

| Parameter | Default | Description |
|---|---|---|
| `max_attempts` | `3` | Total attempts including the first call |
| `initial_delay` | `0.5` | Seconds before the first retry |
| `max_delay` | `30.0` | Maximum pre-jitter delay window in seconds |
| `multiplier` | `2.0` | Exponential backoff multiplier per attempt |
| `jitter` | `0.25` | Kept for interface compatibility; actual randomisation uses full-jitter (uniform over the capped window) |
| `retry_on` | `(RateLimitError, ProviderError)` | Exception types that trigger a retry |

## Token Counting / Cost Estimation

```python
import asyncio
from norreroute import Client, estimate_cost, count_tokens_approx
from norreroute.types import ChatRequest, Message, TextPart

async def main() -> None:
    client = Client("anthropic")
    request = ChatRequest(
        model="claude-3-5-haiku-20241022",
        messages=[Message(role="user", content=[TextPart(text="Explain recursion.")])],
        max_tokens=256,
    )

    # Pre-flight estimate (rough heuristic — not a real tokeniser)
    approx = count_tokens_approx(request)
    print(f"~{approx} input tokens")

    response = await client.chat(request)

    # Precise cost from actual usage data
    cost = estimate_cost(response)
    print(f"${cost.total_cost_usd:.6f} — {cost.input_tokens} in / {cost.output_tokens} out")
    await client.aclose()

asyncio.run(main())
```

Supply a custom pricing table to override or extend the built-in one:

```python
from norreroute import ModelPrice, estimate_cost

my_pricing = {"my-model": ModelPrice(input_per_mtok_usd=1.00, output_per_mtok_usd=3.00)}
cost = estimate_cost(response, pricing=my_pricing)
```

`estimate_cost` raises `UnknownModelError` for models not in the built-in table and not in the supplied `pricing` dict. Ollama models (local) always cost `$0.00`. `CostEstimate.is_estimate` is `True` when usage data was absent and the char/4 heuristic was used instead.

## Structured Output / JSON Mode

`json_chat` sends the request in JSON mode and returns the parsed response. It automatically merges the provider-specific JSON hint (e.g. `response_format` for Anthropic, `format: "json"` for Ollama) into `ChatRequest.extra` without mutating the original request.

```python
import asyncio
from dataclasses import dataclass
from norreroute import Client, json_chat
from norreroute.types import ChatRequest, Message, TextPart

@dataclass
class Capital:
    country: str
    capital: str

async def main() -> None:
    client = Client("anthropic")
    request = ChatRequest(
        model="claude-3-haiku-20240307",
        messages=[
            Message(
                role="user",
                content=[TextPart(text='Return JSON: {"country": "France", "capital": "..."}')],
            )
        ],
        max_tokens=128,
    )

    # With a dataclass schema — returns (ChatResponse, Capital)
    response, result = await json_chat(client, request, schema=Capital)
    print(result.capital)   # "Paris"

    # Without a schema — returns (ChatResponse, dict)
    response, raw = await json_chat(client, request)
    print(raw)

    await client.aclose()

asyncio.run(main())
```

Set `strict=False` to get `(response, None)` instead of an exception on parse/coercion failure:

```python
response, result = await json_chat(client, request, schema=Capital, strict=False)
if result is None:
    print("model did not return valid JSON")
```

`json_chat` raises `JSONValidationError` (when `strict=True`) if the response is not valid JSON or cannot be coerced to the requested schema.

## OpenTelemetry Tracing

Requires the `otel` extra: `pip install "norreroute[otel]"`.

```python
from norreroute import Client

# Use the default tracer (reads from the OTel SDK environment)
client = Client("anthropic", trace=True)

# Or supply your own tracer
from opentelemetry import trace
my_tracer = trace.get_tracer("my-app")
client = Client("anthropic", tracer=my_tracer)
```

When tracing is disabled (the default), OTel is never imported and adds zero overhead.

Span names and attributes emitted on every `chat` and `stream` call:

| Span name | `chat` calls | `stream` calls |
|---|---|---|
| `norreroute.chat` | Yes | — |
| `norreroute.stream` | — | Yes |

Attributes set on every span:

| Attribute | Source |
|---|---|
| `gen_ai.system` | Always `"norreroute"` |
| `gen_ai.request.model` | `ChatRequest.model` |
| `gen_ai.request.max_tokens` | `ChatRequest.max_tokens` (omitted if `None`) |
| `gen_ai.request.temperature` | `ChatRequest.temperature` (omitted if `None`) |
| `gen_ai.usage.input_tokens` | `ChatResponse.usage.input_tokens` |
| `gen_ai.usage.output_tokens` | `ChatResponse.usage.output_tokens` |
| `gen_ai.response.finish_reason` | `ChatResponse.finish_reason` |
| `gen_ai.response.model` | `ChatResponse.model` |

On error, the span status is set to `ERROR`, the exception is recorded, and then re-raised. For streaming, the span is opened when iteration begins and closed when the iterator is exhausted or broken.

## Conversation / Session Persistence

`Conversation` tracks the message history and handles the request/response cycle for you:

```python
import asyncio
from norreroute import Client, Conversation
from norreroute.streaming import TextDelta, StreamEnd

async def main() -> None:
    client = Client("anthropic")
    conv = Conversation(client, model="claude-3-haiku-20240307", system="You are a helpful assistant.")

    # Non-streaming turns
    response = await conv.send("What is the capital of France?")
    print(response.content[0].text)   # "Paris"

    response = await conv.send("And of Germany?")
    print(response.content[0].text)   # History is sent automatically

    # Streaming turn
    async for event in conv.stream("Give me a fun fact about Berlin."):
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, StreamEnd):
            print()
            break

    print(f"{len(conv.messages)} messages in history")
    await client.aclose()

asyncio.run(main())
```

### History Trimming

Use `TrimStrategy` to keep the history within a token budget. The system prompt and the last N messages are always kept; older messages are dropped from the front.

```python
from norreroute import Conversation, TrimStrategy

conv = Conversation(
    client,
    model="claude-3-haiku-20240307",
    system="You are a helpful assistant.",
    trim=TrimStrategy(max_input_tokens=4000, keep_system=True, keep_last_n=4),
)
```

Raises `ConversationOverflowError` if the pinned messages alone exceed the budget.

### JSON Persistence

```python
# Save
json_str = conv.to_json()
with open("session.json", "w") as f:
    f.write(json_str)

# Restore
with open("session.json") as f:
    json_str = f.read()

conv = Conversation.from_json(json_str, client)
```

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
    ConversationOverflowError,
    JSONValidationError,
    ProviderError,
    RateLimitError,
    TimeoutError_,
    UnknownModelError,
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
except UnknownModelError as e:
    print(f"Unknown model for pricing: {e}")
except JSONValidationError as e:
    print(f"JSON parse/coercion failed: {e}")
except ConversationOverflowError as e:
    print(f"Conversation too large to trim: {e}")
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
| JSON mode hint (`json_chat`) | `response_format: {type: json_object}` | `format: "json"` |
| Cost estimation | Yes (built-in prices) | Yes (always `$0.00`) |
| OTel `gen_ai.system` | `"norreroute"` | `"norreroute"` |

## Documentation

- [API Reference](docs/api-reference.md) — all types, methods, and errors
- [Provider Guide](docs/providers.md) — provider-specific details, custom provider walkthrough
- [Local Setup](docs/local-setup.md) — contributor setup, running tests
