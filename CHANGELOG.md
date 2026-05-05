# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-05-05

### Added

- `ImagePart` content type for multimodal (vision) requests.
- `ChatResponse.text` convenience property — concatenates all `TextPart` blocks into a
  single string; returns `""` for pure tool-use responses.
- `Message.user(text, *, images=...)` classmethod — builds a user-role message from a text
  prompt and a sequence of raw image bytes; each bytes item becomes an `ImagePart` with
  `media_type="image/jpeg"`.
- `Message.system(text)` classmethod — builds a system-role message from a text string.
- `UnsupportedCapabilityError` raised pre-flight (in `Client.chat` and `Client.stream`)
  when a request contains `ImagePart` but the target provider has `supports_vision = False`.
  Fields: `capability: str`, `provider: str`. Exported from top-level `norreroute`.
- Vision payload serialisation for Ollama: `ImagePart` bytes are base64-encoded into the
  `"images"` field of the `/api/chat` request body.
- Vision payload serialisation for Anthropic: `ImagePart` is serialised as a
  `{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}` block
  in the Messages API request body.

### Changed

- `RetryingProvider` now forwards `supports_vision` from the wrapped provider (falls back to
  `True` for providers that do not declare the attribute).

No breaking changes.

## [0.2.1] - 2026-05-03

### Fixed

- Ignore extra environment variables


## [0.2.0] - 2026-05-03

### Added

- **Retry / Exponential Backoff** — `RetryPolicy` frozen dataclass and `RetryingProvider`
  wrapper; retries `chat()` and `stream()` on `RateLimitError` and transient `ProviderError`
  with full-jitter exponential backoff. Enable via `Client("anthropic", retry=True)` or
  `retry=RetryPolicy(max_attempts=5)`.
- **Token Counting / Cost Estimation** — `ModelPrice` and `CostEstimate` frozen dataclasses;
  `estimate_cost(response)` free function that uses `ChatResponse.usage` to compute USD cost;
  `count_tokens_approx(request)` char/4 heuristic for pre-flight budgeting. Ollama models
  always return `$0.00`.
- **Structured Output / JSON Mode** — `json_chat(client, request, schema=None, strict=True)`
  async function; automatically merges the provider-specific JSON hint into
  `ChatRequest.extra` and optionally coerces the parsed dict to a dataclass or TypedDict.
- **OpenTelemetry Tracing** — lazy OTel integration; enable via `Client("anthropic", trace=True)`
  or `Client("anthropic", tracer=my_tracer)`. OTel is never imported at module scope and
  is zero-cost when disabled. Emits `gen_ai.*` semantic convention attributes.
- **Conversation / Session Persistence** — `Conversation` stateful wrapper with `.send()`,
  `.send_message()`, `.stream()`, `.to_json()`, and `Conversation.from_json()`. Supports
  sliding-window history trimming via `TrimStrategy`.
- `Client.provider_name` read-only property returning the underlying provider name string.
- `Client(retry=...)`, `Client(trace=...)`, `Client(tracer=...)` keyword arguments.
- New error types: `UnknownModelError`, `JSONValidationError`, `ConversationOverflowError`.
- Optional dependency group `otel`: `pip install norreroute[otel]` adds `opentelemetry-api>=1.25`.

## [0.1.1] - 2026-04-30

### Fixed

- Provider self-registration bug: `providers/__init__.py` now imports `anthropic` and `ollama` submodules, and `norreroute/__init__.py` imports the providers package so registrations fire on import

## [0.1.0] - 2026-04-30

### Added

- Core `Client` interface with async and sync support
- Anthropic provider integration
- Ollama provider integration
- Streaming support with `TextDelta` and `StreamEnd` events
- Tool calling support for Anthropic and Ollama
- Provider registry for custom provider registration
- Comprehensive error types (AuthenticationError, ConfigurationError, ProviderError, RateLimitError, TimeoutError_)
- Domain model dataclasses and error hierarchy
- GitHub Actions CI/CD workflows for lint, test, and build

### Fixed

- CI/CD configuration fixes
