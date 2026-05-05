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
Client(
    provider: str | Provider,
    *,
    retry: RetryPolicy | bool = False,
    trace: bool = False,
    tracer: Any = None,
    **provider_kwargs: object,
) -> None
```

Constructs a client backed by the named or supplied provider.

| Parameter | Type | Description |
|---|---|---|
| `provider` | `str \| Provider` | Provider name (e.g. `"anthropic"`) or a `Provider` instance |
| `retry` | `RetryPolicy \| bool` | `False` (default) disables retries. `True` enables the default `RetryPolicy`. A `RetryPolicy` instance enables retries with the given configuration. |
| `trace` | `bool` | `True` enables OpenTelemetry tracing via the default tracer. Requires `pip install norreroute[otel]`. Default `False`. |
| `tracer` | `Any` | A custom OTel tracer object. Takes precedence over `trace=True`. Default `None`. |
| `**provider_kwargs` | `object` | Keyword arguments forwarded to the provider factory when `provider` is a string |

```python
client = Client("anthropic", api_key="sk-ant-...")           # by name
client = Client("ollama", base_url="http://host:11434")
client = Client(my_provider_instance)                         # by instance
client = Client("anthropic", retry=True)                     # default retry policy
client = Client("anthropic", retry=RetryPolicy(max_attempts=5))
client = Client("anthropic", trace=True)                     # OTel tracing
```

Raises `KeyError` if the named provider is not registered.

---

### `Client.provider_name`

```python
@property
def provider_name(self) -> str
```

Returns the name of the underlying provider (e.g. `"anthropic"`, `"ollama"`). When a
`RetryingProvider` wrapper is active, the name is still that of the inner provider.

```python
client = Client("anthropic")
print(client.provider_name)   # "anthropic"
```

---

### `Client.chat`

```python
async def chat(self, request: ChatRequest) -> ChatResponse
```

Sends a chat completion request and returns the full response.

| Parameter | Type | Description |
|---|---|---|
| `request` | `ChatRequest` | The request to send |

Returns `ChatResponse`. Raises `UnsupportedCapabilityError` pre-flight if the request
contains `ImagePart` and the provider does not support vision. Raises any `ProviderError`
subclass on provider-level errors.

```python
response = await client.chat(request)
print(response.text)
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

Raises `UnsupportedCapabilityError` pre-flight if the request contains `ImagePart` and the
provider does not support vision.

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

Providers may also declare a `supports_vision: bool` attribute. When present and `False`,
`Client` raises `UnsupportedCapabilityError` before sending any request that contains
`ImagePart`. Both built-in providers (`anthropic`, `ollama`) set `supports_vision = True`.

---

## Types

```python
from norreroute.types import (
    ChatRequest, ChatResponse,
    Message, ContentPart,
    TextPart, ImagePart, ToolUsePart, ToolResultPart,
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

#### `ChatResponse.text`

```python
@property
def text(self) -> str
```

Returns the concatenated text of all `TextPart` blocks in `content`. Returns `""` when
there are no `TextPart` blocks (e.g. a pure tool-use response).

```python
print(response.text)   # equivalent to "".join(p.text for p in response.content if isinstance(p, TextPart))
```

---

### `Message`

```python
@dataclass(frozen=True)
class Message:
    role: Role
    content: Sequence[ContentPart]
```

`Role = Literal["system", "user", "assistant", "tool"]`

#### `Message.user`

```python
@classmethod
def user(cls, text: str = "", *, images: Sequence[bytes] = ()) -> Message
```

Convenience constructor for a user-role message. Each item in `images` is wrapped in an
`ImagePart` with `media_type="image/jpeg"`. `text` and `images` may both be provided;
`text` is added first.

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | Text prompt. Optional if `images` is provided. |
| `images` | `Sequence[bytes]` | Raw image bytes. Each item becomes an `ImagePart(data=..., media_type="image/jpeg")`. |

```python
msg = Message.user("Describe this image.", images=[jpeg_bytes])
msg = Message.user(images=[jpeg_bytes])          # text-free
msg = Message.user("Hello")                      # text-only, same as before
```

To use a media type other than `image/jpeg`, construct `ImagePart` directly.

#### `Message.system`

```python
@classmethod
def system(cls, text: str) -> Message
```

Convenience constructor for a system-role message containing a single `TextPart`.

```python
msg = Message.system("You are a helpful assistant.")
```

---

### `ContentPart`

```python
ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart
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

### `ImagePart`

```python
@dataclass(frozen=True)
class ImagePart:
    data: bytes
    media_type: str = "image/jpeg"
    type: Literal["image"] = "image"
```

A binary image content block. Import from `norreroute.types`.

| Field | Type | Description |
|---|---|---|
| `data` | `bytes` | Raw image bytes |
| `media_type` | `str` | MIME type of the image. Default `"image/jpeg"`. Common values: `"image/jpeg"`, `"image/png"`, `"image/gif"`, `"image/webp"`. |
| `type` | `Literal["image"]` | Always `"image"`. Identifies the part type. |

Providers base64-encode `data` themselves during serialisation. You supply raw bytes.

```python
from norreroute.types import ImagePart

part = ImagePart(data=png_bytes, media_type="image/png")
```

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

## Retry

```python
from norreroute import RetryPolicy, RetryingProvider
```

---

### `RetryPolicy`

```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.25
    retry_on: tuple[type[BaseException], ...] = (RateLimitError, ProviderError)
```

Configuration for retry behaviour on transient errors. All fields have defaults — `RetryPolicy()` gives a sensible starting point.

| Field | Type | Description |
|---|---|---|
| `max_attempts` | `int` | Total number of attempts including the first call. Default `3`. |
| `initial_delay` | `float` | Starting delay in seconds before the first retry. Default `0.5`. |
| `max_delay` | `float` | Maximum cap on the pre-jitter delay window in seconds. Default `30.0`. |
| `multiplier` | `float` | Exponential backoff multiplier applied per attempt. Default `2.0`. |
| `jitter` | `float` | Kept for interface compatibility. Actual randomisation uses full-jitter (uniform over `[0, min(max_delay, initial * multiplier**attempt)]`). Default `0.25`. |
| `retry_on` | `tuple[type[BaseException], ...]` | Exception types that trigger a retry. Default `(RateLimitError, ProviderError)`. |

#### `RetryPolicy.should_retry`

```python
def should_retry(self, exc: BaseException, attempt: int) -> bool
```

Returns `True` if `exc` is an instance of one of `retry_on` and `attempt < max_attempts`. `attempt` is 1-based (the number of the call that just failed).

#### `RetryPolicy.delay_for`

```python
def delay_for(self, attempt: int) -> float
```

Returns the number of seconds to sleep before the next attempt. Uses AWS full-jitter: `uniform(0, min(max_delay, initial_delay * multiplier**attempt))`. `attempt` is 1-based.

---

### `RetryingProvider`

```python
class RetryingProvider:
    def __init__(
        self,
        inner: Provider,
        policy: RetryPolicy,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None
```

Wraps any `Provider` and retries `chat()` and `stream()` according to `policy`. Satisfies the `Provider` protocol — pass it anywhere a `Provider` is accepted.

You do not normally construct this directly. Use `Client("anthropic", retry=...)` instead.

| Parameter | Type | Description |
|---|---|---|
| `inner` | `Provider` | The underlying provider to delegate to |
| `policy` | `RetryPolicy` | Retry configuration |
| `sleep` | `Callable[[float], Awaitable[None]]` | Injectable sleep callable. Default `asyncio.sleep`. Override in tests to avoid actual sleeps. |

`RetryingProvider` forwards `supports_vision` from the wrapped provider. If the inner
provider does not declare `supports_vision`, it defaults to `True`.

Stream retries occur only before the first `TextDelta` or `ToolCallDelta` event is yielded. After the first content event, errors propagate without retry and partial responses are never re-emitted.

---

## Token Counting / Cost Estimation

```python
from norreroute import ModelPrice, CostEstimate, estimate_cost, count_tokens_approx
```

---

### `ModelPrice`

```python
@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok_usd: float
    output_per_mtok_usd: float
```

Per-model pricing in USD per million tokens.

| Field | Type | Description |
|---|---|---|
| `input_per_mtok_usd` | `float` | Cost of input (prompt) tokens per million |
| `output_per_mtok_usd` | `float` | Cost of output (completion) tokens per million |

---

### `CostEstimate`

```python
@dataclass(frozen=True)
class CostEstimate:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    is_estimate: bool
```

Result of a cost calculation for a single completion.

| Field | Type | Description |
|---|---|---|
| `model` | `str` | Model name from the response |
| `input_tokens` | `int` | Input tokens used (or approximated) |
| `output_tokens` | `int` | Output tokens used (or approximated) |
| `input_cost_usd` | `float` | Dollar cost for input tokens |
| `output_cost_usd` | `float` | Dollar cost for output tokens |
| `total_cost_usd` | `float` | Sum of input and output costs |
| `is_estimate` | `bool` | `True` when usage was missing and the char/4 heuristic was used |

---

### `estimate_cost`

```python
def estimate_cost(
    response: ChatResponse,
    pricing: Mapping[str, ModelPrice] | None = None,
    *,
    request: ChatRequest | None = None,
) -> CostEstimate
```

Computes the cost of a completed chat response.

Token counts are taken from `response.usage` when the values are non-zero. When usage is absent or zero, the function falls back to `count_tokens_approx` on `request` (if provided) and sets `is_estimate=True`.

Pricing lookup order:
1. `pricing` argument (exact key match, then prefix match).
2. Built-in `MODEL_PRICING` table (exact key match, then prefix match).
3. Raises `UnknownModelError` if nothing matches.

| Parameter | Type | Description |
|---|---|---|
| `response` | `ChatResponse` | The completed response to cost |
| `pricing` | `Mapping[str, ModelPrice] \| None` | Optional caller-supplied table, overrides built-in |
| `request` | `ChatRequest \| None` | Optional original request for token approximation when usage is absent |

Raises `UnknownModelError` when the model is not in the built-in table and not in `pricing`.

```python
cost = estimate_cost(response)
print(f"${cost.total_cost_usd:.6f}")
```

---

### `count_tokens_approx`

```python
def count_tokens_approx(request: ChatRequest) -> int
```

Estimates the token count for a request using a char/4 heuristic. Counts characters in the system prompt and all `TextPart` content, then divides by 4.

This is a rough approximation suitable for pre-flight budget checks only. It is not a real tokeniser and does not account for tool schemas, non-text parts, or model-specific vocabulary.

| Parameter | Type | Description |
|---|---|---|
| `request` | `ChatRequest` | The request to estimate |

Returns an `int` (floor of total characters / 4).

---

## Structured Output / JSON Mode

```python
from norreroute import json_chat
```

---

### `json_chat`

```python
async def json_chat(
    client: Client,
    request: ChatRequest,
    *,
    schema: type[T] | None = None,
    strict: bool = True,
) -> tuple[ChatResponse, T | dict[str, Any] | None]
```

Sends a chat request in JSON mode and returns the parsed (and optionally coerced) response.

Before calling the provider, `json_chat` merges a provider-specific JSON hint into `ChatRequest.extra`. The original `request` is never mutated; a new `ChatRequest` is constructed internally.

Provider hints applied automatically:

| Provider | Hint merged into `extra` |
|---|---|
| `"anthropic"` | `{"response_format": {"type": "json_object"}}` |
| `"ollama"` | `{"format": "json"}` |

Unknown providers receive no hint.

| Parameter | Type | Description |
|---|---|---|
| `client` | `Client` | The client to send the request through |
| `request` | `ChatRequest` | The request to send. Existing `extra` values are preserved; hint wins on key conflicts. |
| `schema` | `type[T] \| None` | Optional dataclass or TypedDict to coerce the parsed dict into. `None` returns a raw `dict`. |
| `strict` | `bool` | `True` (default) raises `JSONValidationError` on invalid JSON or coercion failure. `False` returns `(response, None)` on failure. |

Return value:

| Condition | Type of second element |
|---|---|
| `schema=None` | `dict[str, Any]` |
| `schema` is a dataclass and coercion succeeds | Instance of `schema` |
| `schema` is a TypedDict or other annotated type | `dict[str, Any]` (shallow key check only) |
| Parse or coercion fails with `strict=False` | `None` |

Raises `JSONValidationError` on parse or coercion failure when `strict=True`.

```python
from dataclasses import dataclass
from norreroute import json_chat

@dataclass
class Point:
    x: float
    y: float

response, point = await json_chat(client, request, schema=Point)
```

---

## OpenTelemetry Tracing

```python
# No direct import needed — configure via Client constructor
client = Client("anthropic", trace=True)
client = Client("anthropic", tracer=my_tracer)
```

Tracing is enabled by passing `trace=True` or `tracer=my_tracer` to `Client.__init__`. See the [`Client.__init__`](#client__init) entry for parameter details.

OTel is never imported at module scope. When tracing is disabled, there is zero overhead.

### Span names

| Operation | Span name |
|---|---|
| `Client.chat` | `norreroute.chat` |
| `Client.stream` | `norreroute.stream` |

### Attributes

| Attribute | Set on | Source |
|---|---|---|
| `gen_ai.system` | Request | Always `"norreroute"` |
| `gen_ai.request.model` | Request | `ChatRequest.model` |
| `gen_ai.request.max_tokens` | Request | `ChatRequest.max_tokens` (omitted if `None`) |
| `gen_ai.request.temperature` | Request | `ChatRequest.temperature` (omitted if `None`) |
| `gen_ai.usage.input_tokens` | Response | `ChatResponse.usage.input_tokens` |
| `gen_ai.usage.output_tokens` | Response | `ChatResponse.usage.output_tokens` |
| `gen_ai.response.finish_reason` | Response | `ChatResponse.finish_reason` |
| `gen_ai.response.model` | Response | `ChatResponse.model` |

Response attributes (`gen_ai.usage.*`, `gen_ai.response.*`) are set after the call completes. They are not present on stream spans when the caller breaks out early.

On error: span status is set to `ERROR`, the exception is recorded, then re-raised.

---

## Conversation

```python
from norreroute import Conversation, TrimStrategy
```

---

### `TrimStrategy`

```python
@dataclass(frozen=True)
class TrimStrategy:
    max_input_tokens: int
    keep_system: bool = True
    keep_last_n: int = 2
```

Configuration for sliding-window history trimming. Applied before each `send` or `stream` call.

| Field | Type | Description |
|---|---|---|
| `max_input_tokens` | `int` | Approximate token budget for the request (uses `count_tokens_approx` internally) |
| `keep_system` | `bool` | If `True`, the system prompt is always included and counted within the budget. Default `True`. |
| `keep_last_n` | `int` | Always keep the last N messages regardless of budget. Default `2`. |

---

### `Conversation`

```python
class Conversation:
    def __init__(
        self,
        client: Client,
        *,
        model: str,
        system: str | None = None,
        trim: TrimStrategy | None = None,
        history: list[Message] | None = None,
    ) -> None
```

A stateful conversation that accumulates message history and calls the LLM on each turn.

| Parameter | Type | Description |
|---|---|---|
| `client` | `Client` | The client to use for all requests |
| `model` | `str` | Model identifier sent on every request |
| `system` | `str \| None` | System prompt. Not stored in `messages`; passed as `ChatRequest.system`. |
| `trim` | `TrimStrategy \| None` | Trimming configuration. `None` sends full history on every turn. |
| `history` | `list[Message] \| None` | Seed history. Used by `from_json` to restore a saved session. |

#### `Conversation.messages`

```python
@property
def messages(self) -> tuple[Message, ...]
```

Immutable view of the full conversation history. Returns all messages appended so far, including user and assistant turns. Does not include the system prompt.

#### `Conversation.send`

```python
async def send(self, text: str, **extra: Any) -> ChatResponse
```

Appends a user message with the given text, sends the request, appends the assistant reply, and returns the response.

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | The user's message text |
| `**extra` | `Any` | Forwarded to `ChatRequest.extra` |

#### `Conversation.send_message`

```python
async def send_message(self, msg: Message, **extra: Any) -> ChatResponse
```

Same as `send` but accepts a pre-built `Message`. Use this to send non-text content parts (e.g. `ImagePart`) or tool results.

| Parameter | Type | Description |
|---|---|---|
| `msg` | `Message` | The message to append and send |
| `**extra` | `Any` | Forwarded to `ChatRequest.extra` |

#### `Conversation.stream`

```python
def stream(self, text: str, **extra: Any) -> AsyncIterator[StreamEvent]
```

Appends a user message and returns a streaming async iterator. The assistant reply is appended to history only after a `StreamEnd` event is received. If the caller breaks out of the loop early, history is not modified.

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | The user's message text |
| `**extra` | `Any` | Forwarded to `ChatRequest.extra` |

#### `Conversation.to_json`

```python
def to_json(self) -> str
```

Serialises the conversation (model, system, trim config, and full message history) to a JSON string. The envelope is versioned (`{"version": 1, ...}`).

#### `Conversation.from_json`

```python
@classmethod
def from_json(cls, data: str, client: Client) -> Conversation
```

Reconstructs a `Conversation` from a string produced by `to_json`.

| Parameter | Type | Description |
|---|---|---|
| `data` | `str` | The JSON string |
| `client` | `Client` | The client to use for subsequent requests |

---

## Errors

```python
from norreroute import UnsupportedCapabilityError
from norreroute.errors import (
    AIProxyError,
    ConfigurationError,
    ConversationOverflowError,
    JSONValidationError,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError_,
    ToolArgumentError,
    UnknownModelError,
    UnsupportedCapabilityError,
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
├── ToolArgumentError
├── UnknownModelError
├── JSONValidationError
├── ConversationOverflowError
└── UnsupportedCapabilityError
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

### `UnknownModelError`

Subclass of `AIProxyError`. Raised by `estimate_cost` when the model name cannot be resolved to a pricing entry in the built-in table or a caller-supplied `pricing` dict.

### `JSONValidationError`

Subclass of `AIProxyError`. Raised by `json_chat` (when `strict=True`) if the model response is not valid JSON or cannot be coerced to the requested schema type.

### `ConversationOverflowError`

Subclass of `AIProxyError`. Raised by `Conversation` when the pinned messages (system prompt + last N) exceed the `TrimStrategy.max_input_tokens` budget and the history cannot be trimmed any further.

### `UnsupportedCapabilityError`

```python
class UnsupportedCapabilityError(AIProxyError):
    capability: str
    provider: str
```

Raised pre-flight by `Client.chat` and `Client.stream` when a `ChatRequest` uses a
capability the target provider does not support. Currently only fires for vision: if any
message in `request.messages` contains an `ImagePart` and the provider has
`supports_vision = False`.

| Attribute | Type | Description |
|---|---|---|
| `capability` | `str` | The unsupported capability name, e.g. `"vision"` |
| `provider` | `str` | The provider name, e.g. `"my-provider"` |

`UnsupportedCapabilityError` is also exported directly from `norreroute`:

```python
from norreroute import UnsupportedCapabilityError
```

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
