# API Reference

## `Client`

```python
from norreroute import Client
```

The main entry point. Accepts either a provider name (resolved via the registry) or a
`Provider` instance directly.

---

### `Client.__init__`

```python
Client(provider: str | Provider, **provider_kwargs: object) -> None
```

Constructs a client backed by the named or supplied provider.

| Parameter | Type | Description |
|---|---|---|
| `provider` | `str \| Provider` | Provider name (e.g. `"anthropic"`) or a `Provider` instance |
| `**provider_kwargs` | `object` | Keyword arguments forwarded to the provider factory when `provider` is a string |

```python
client = Client("anthropic", api_key="sk-ant-...")   # by name
client = Client("ollama", base_url="http://host:11434")
client = Client(my_provider_instance)                 # by instance
```

Raises `KeyError` if the named provider is not registered.

---

### `Client.chat`

```python
async def chat(self, request: ChatRequest) -> ChatResponse
```

Sends a chat completion request and returns the full response.

| Parameter | Type | Description |
|---|---|---|
| `request` | `ChatRequest` | The request to send |

Returns `ChatResponse`. Raises any `ProviderError` subclass on provider-level errors.

```python
response = await client.chat(request)
print(response.content[0].text)
```

---

### `Client.stream`

```python
def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]
```

Returns an async iterator that yields `StreamEvent` objects as they arrive.

| Parameter | Type | Description |
|---|---|---|
| `request` | `ChatRequest` | The request to stream |

```python
async for event in client.stream(request):
    if isinstance(event, TextDelta):
        print(event.text, end="")
    elif isinstance(event, StreamEnd):
        break
```

---

### `Client.chat_sync`

```python
def chat_sync(self, request: ChatRequest) -> ChatResponse
```

Synchronous wrapper around `chat`. Calls `asyncio.run` internally.

Do not call from inside a running event loop (e.g. an async web handler). Use `chat` there instead.

---

### `Client.stream_sync`

```python
def stream_sync(self, request: ChatRequest) -> Iterator[StreamEvent]
```

Synchronous wrapper around `stream`. Creates a new event loop internally.

Do not call from inside a running event loop.

```python
for event in client.stream_sync(request):
    if isinstance(event, TextDelta):
        print(event.text, end="")
```

---

### `Client.aclose`

```python
async def aclose(self) -> None
```

Releases the provider's underlying resources (e.g. closes the httpx connection pool). Call this when you're done with the client, or use the client as an async context manager if the provider supports it.

---

## `Provider` Protocol

```python
from norreroute.provider import Provider
```

The contract every provider must satisfy. Defined as `typing.Protocol` with `@runtime_checkable`, so `isinstance(obj, Provider)` works without inheritance.

```python
@runtime_checkable
class Provider(Protocol):
    name: str

    async def chat(self, request: ChatRequest) -> ChatResponse: ...
    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]: ...
    async def aclose(self) -> None: ...
```

| Member | Type | Description |
|---|---|---|
| `name` | `str` | Provider identifier, e.g. `"anthropic"`, `"ollama"` |
| `chat` | `async method` | Non-streaming completion |
| `stream` | `method returning AsyncIterator` | Streaming completion |
| `aclose` | `async method` | Release resources |

`stream` is a regular method returning an `AsyncIterator`, not an `async def`. Providers implement it as a regular method returning an async generator. This allows `stream` to be called synchronously and iterated lazily.

---

## Types

```python
from norreroute.types import (
    ChatRequest, ChatResponse,
    Message, ContentPart,
    TextPart, ToolUsePart, ToolResultPart,
    ToolSpec, Usage, Role,
)
```

All types are frozen dataclasses. They have no Pydantic dependency.

---

### `ChatRequest`

```python
@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: Sequence[Message]
    system: str | None = None
    tools: Sequence[ToolSpec] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    stop: Sequence[str] = ()
    extra: dict[str, Any] = field(default_factory=dict)
```

| Field | Type | Description |
|---|---|---|
| `model` | `str` | Model identifier (provider-specific, e.g. `"claude-3-haiku-20240307"`, `"llama3"`) |
| `messages` | `Sequence[Message]` | Conversation history |
| `system` | `str \| None` | System prompt. Anthropic sends it as a top-level parameter; Ollama prepends it as a `system`-role message |
| `tools` | `Sequence[ToolSpec]` | Tools the model may call |
| `temperature` | `float \| None` | Sampling temperature. Provider default when `None` |
| `max_tokens` | `int \| None` | Maximum output tokens. Anthropic defaults to `1024` when `None`; Ollama uses its own default |
| `stop` | `Sequence[str]` | Stop sequences |
| `extra` | `dict[str, Any]` | Provider-specific parameters passed through without validation (e.g. `{"keep_alive": "5m"}` for Ollama, `{"cache_control": {...}}` for Anthropic) |

---

### `ChatResponse`

```python
@dataclass(frozen=True)
class ChatResponse:
    model: str
    content: Sequence[ContentPart]
    finish_reason: Literal["stop", "length", "tool_use", "error"]
    usage: Usage
    raw: dict[str, Any]
```

| Field | Type | Description |
|---|---|---|
| `model` | `str` | Model identifier as returned by the provider |
| `content` | `Sequence[ContentPart]` | Response content. May contain `TextPart` and/or `ToolUsePart` |
| `finish_reason` | `"stop" \| "length" \| "tool_use" \| "error"` | Why generation stopped |
| `usage` | `Usage` | Token counts |
| `raw` | `dict[str, Any]` | Untouched provider payload for debugging and audit |

---

### `Message`

```python
@dataclass(frozen=True)
class Message:
    role: Role
    content: Sequence[ContentPart]
```

`Role = Literal["system", "user", "assistant", "tool"]`

---

### `ContentPart`

```python
ContentPart = TextPart | ToolUsePart | ToolResultPart
```

---

### `TextPart`

```python
@dataclass(frozen=True)
class TextPart:
    text: str
    type: Literal["text"] = "text"
```

Plain text content block.

---

### `ToolUsePart`

```python
@dataclass(frozen=True)
class ToolUsePart:
    id: str
    name: str
    arguments: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"
```

A tool invocation emitted by the model. Appears in `ChatResponse.content` when `finish_reason == "tool_use"`.

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Tool call identifier. Required to construct the subsequent `ToolResultPart` |
| `name` | `str` | Tool name matching a `ToolSpec.name` |
| `arguments` | `dict[str, Any]` | Parsed JSON arguments |

---

### `ToolResultPart`

```python
@dataclass(frozen=True)
class ToolResultPart:
    tool_use_id: str
    content: str
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"
```

The result of a tool invocation, sent back to the model in a follow-up message.

| Field | Type | Description |
|---|---|---|
| `tool_use_id` | `str` | Must match the `ToolUsePart.id` from the model's previous response |
| `content` | `str` | JSON-encoded result or plain text |
| `is_error` | `bool` | Set to `True` to signal the tool call failed |

---

### `ToolSpec`

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
```

Declares a tool the model may call. `parameters` must be a valid JSON Schema object.

---

### `Usage`

```python
@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
```

Token counts for a completion. For Ollama, `input_tokens` maps to `prompt_eval_count` and `output_tokens` maps to `eval_count`.

---

## Streaming Events

```python
from norreroute.streaming import TextDelta, ToolCallDelta, StreamEnd, StreamEvent
```

`StreamEvent = TextDelta | ToolCallDelta | StreamEnd`

---

### `TextDelta`

```python
@dataclass(frozen=True)
class TextDelta:
    text: str
    type: Literal["text_delta"] = "text_delta"
```

A chunk of streamed text. Concatenate successive `text` values to reconstruct the full response.

---

### `ToolCallDelta`

```python
@dataclass(frozen=True)
class ToolCallDelta:
    id: str
    name: str | None
    arguments_json: str
    type: Literal["tool_call_delta"] = "tool_call_delta"
```

A chunk of a streamed tool call. `name` and `arguments_json` may arrive in fragments across multiple events. Accumulate `arguments_json` until `StreamEnd` before parsing.

Note: the current Anthropic provider uses `text_stream` and does not emit `ToolCallDelta` during streaming. Tool calls appear only in non-streaming `chat` responses.

---

### `StreamEnd`

```python
@dataclass(frozen=True)
class StreamEnd:
    finish_reason: str
    usage: Usage | None
    type: Literal["end"] = "end"
```

Signals the end of a streaming response. Always the last event in a stream.

| Field | Type | Description |
|---|---|---|
| `finish_reason` | `str` | Same values as `ChatResponse.finish_reason` |
| `usage` | `Usage \| None` | Token counts. Present for Anthropic; present for Ollama (from the final `done` chunk) |

---

## Errors

```python
from norreroute.errors import (
    AIProxyError,
    ConfigurationError,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError_,
    ToolArgumentError,
)
```

### Hierarchy

```
AIProxyError
├── ConfigurationError
├── ProviderError
│   ├── RateLimitError
│   ├── AuthenticationError
│   └── TimeoutError_
└── ToolArgumentError
```

### `AIProxyError`

Base exception for all aiproxy errors. Catch this to handle any library error.

### `ConfigurationError`

Raised when provider configuration is invalid or missing (e.g. `ANTHROPIC_API_KEY` not set and not passed as a keyword argument).

### `ProviderError`

```python
class ProviderError(AIProxyError):
    provider: str
    status: int | None
    raw: Any
```

Raised when a provider returns an error response. Attributes:

| Attribute | Type | Description |
|---|---|---|
| `provider` | `str` | Provider name, e.g. `"anthropic"` |
| `status` | `int \| None` | HTTP status code |
| `raw` | `Any` | Raw error payload from the provider |

### `RateLimitError`

Subclass of `ProviderError`. Raised on HTTP 429. `status == 429`.

### `AuthenticationError`

Subclass of `ProviderError`. Raised on HTTP 401. `status == 401`.

### `TimeoutError_`

Subclass of `ProviderError`. Raised when a request times out. Named with a trailing underscore to avoid shadowing the built-in `TimeoutError`.

### `ToolArgumentError`

Subclass of `AIProxyError`. Raised when a tool receives invalid arguments. Not currently raised by built-in providers — intended for use in tool handler implementations.

---

## Registry

```python
from norreroute.registry import register, resolve
```

---

### `register`

```python
def register(name: str, factory: Callable[..., Provider]) -> None
```

Registers a provider factory under the given name. Overwrites any existing registration for the same name.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Provider name to register under |
| `factory` | `Callable[..., Provider]` | A callable that accepts keyword arguments and returns a `Provider` |

```python
from norreroute.registry import register

register("my-provider", lambda **kwargs: MyProvider(**kwargs))
```

---

### `resolve`

```python
def resolve(name: str, **kwargs: object) -> Provider
```

Looks up a provider by name and instantiates it. If the name is not found in the in-memory registry, attempts to load it via package entry points (`group="aiproxy.providers"`) before raising.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Provider name to look up |
| `**kwargs` | `object` | Forwarded to the factory |

Raises `KeyError` if the provider is not found after entry-point discovery.

```python
from norreroute.registry import resolve

provider = resolve("anthropic", api_key="sk-ant-...")
```
