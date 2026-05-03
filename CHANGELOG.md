# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-05-01

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
