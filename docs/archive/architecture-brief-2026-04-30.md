# Architecture Brief — `aiproxy` LLM Client Library

A pragmatic, provider-agnostic Python library for calling LLMs. Starts with Ollama + Anthropic, designed so adding OpenAI/Gemini later is mechanical, not architectural.

---

## 1. Context Diagram

```
                         ┌─────────────────────────┐
   caller code  ────────▶│   aiproxy.Client        │
   (provider-agnostic)   │   (facade, sync+async)  │
                         └───────────┬─────────────┘
                                     │ resolves via
                                     ▼
                         ┌─────────────────────────┐
                         │   ProviderRegistry      │
                         │   (name → Provider)     │
                         └───────────┬─────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
      ┌───────────────┐      ┌───────────────┐     ┌───────────────┐
      │ AnthropicProv │      │ OllamaProv    │     │ <future>      │
      │ (httpx + SSE) │      │ (httpx + ND)  │     │ Gemini/OpenAI │
      └───────────────┘      └───────────────┘     └───────────────┘
              │                      │                      │
              ▼                      ▼                      ▼
        api.anthropic.com     localhost:11434         vendor API
```

The `Client` knows nothing about vendors. Providers translate between the neutral domain model (`ChatRequest`, `ChatResponse`, `ToolCall`) and vendor wire formats.

---

## 2. Core Domain Model

Plain dataclasses — no Pydantic in the core to keep the dependency surface tight. Pydantic only at the config layer.

```python
# aiproxy/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

Role = Literal["system", "user", "assistant", "tool"]

@dataclass(frozen=True)
class TextPart:
    text: str
    type: Literal["text"] = "text"

@dataclass(frozen=True)
class ToolUsePart:
    id: str
    name: str
    arguments: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"

@dataclass(frozen=True)
class ToolResultPart:
    tool_use_id: str
    content: str            # JSON-encoded result or plain text
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"

ContentPart = TextPart | ToolUsePart | ToolResultPart

@dataclass(frozen=True)
class Message:
    role: Role
    content: Sequence[ContentPart]

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]   # JSON Schema

@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: Sequence[Message]
    system: str | None = None             # Anthropic-style top-level system
    tools: Sequence[ToolSpec] = ()
    temperature: float | None = None
    max_tokens: int | None = None
    stop: Sequence[str] = ()
    extra: dict[str, Any] = field(default_factory=dict)  # provider-specific escape hatch

@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class ChatResponse:
    model: str
    content: Sequence[ContentPart]        # may include ToolUsePart
    finish_reason: Literal["stop", "length", "tool_use", "error"]
    usage: Usage
    raw: dict[str, Any]                   # untouched provider payload for debugging
```

### Streaming events — neutral

```python
# aiproxy/streaming.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class TextDelta:
    text: str
    type: Literal["text_delta"] = "text_delta"

@dataclass(frozen=True)
class ToolCallDelta:
    id: str
    name: str | None        # may arrive in chunks
    arguments_json: str     # accumulating JSON fragment
    type: Literal["tool_call_delta"] = "tool_call_delta"

@dataclass(frozen=True)
class StreamEnd:
    finish_reason: str
    usage: "Usage | None"
    type: Literal["end"] = "end"

StreamEvent = TextDelta | ToolCallDelta | StreamEnd
```

Rationale: every provider streams differently (Anthropic SSE with named events, Ollama NDJSON, OpenAI SSE deltas). A small neutral event vocabulary is the only thing callers need.

---

## 3. Provider Protocol

`typing.Protocol` over ABC — duck-typed, no inheritance forced on third-party packages.

```python
# aiproxy/provider.py
from __future__ import annotations
from typing import AsyncIterator, Protocol, runtime_checkable
from .types import ChatRequest, ChatResponse
from .streaming import StreamEvent

@runtime_checkable
class Provider(Protocol):
    name: str                              # "anthropic", "ollama", ...

    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]: ...

    async def aclose(self) -> None: ...    # release httpx client etc.
```

Notes:
- `stream` returns an async iterator (not async-def) so providers can yield directly.
- No sync methods on the protocol. Sync support is bolted on at the `Client` facade. Providers stay async-only.

---

## 4. Client Facade

```python
# aiproxy/client.py
from __future__ import annotations
import asyncio
from typing import AsyncIterator, Iterator
from .provider import Provider
from .registry import resolve
from .types import ChatRequest, ChatResponse
from .streaming import StreamEvent

class Client:
    def __init__(self, provider: str | Provider, **provider_kwargs):
        self._provider: Provider = (
            provider if isinstance(provider, Provider)
            else resolve(provider, **provider_kwargs)
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return await self._provider.chat(request)

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        return self._provider.stream(request)

    def chat_sync(self, request: ChatRequest) -> ChatResponse:
        return asyncio.run(self._provider.chat(request))

    def stream_sync(self, request: ChatRequest) -> Iterator[StreamEvent]:
        loop = asyncio.new_event_loop()
        agen = self._provider.stream(request).__aiter__()
        try:
            while True:
                try:
                    yield loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    return
        finally:
            loop.close()

    async def aclose(self) -> None:
        await self._provider.aclose()
```

Tradeoff: `asyncio.run` per call in `chat_sync` is fine for scripts/CLIs but unsuitable inside a running event loop. Documented constraint.

---

## 5. Provider Registration

**Decision: direct imports + entry-point discovery as opt-in.** No mandatory plugin system.

```python
# aiproxy/registry.py
from __future__ import annotations
from importlib.metadata import entry_points
from typing import Callable
from .provider import Provider

_FACTORIES: dict[str, Callable[..., Provider]] = {}

def register(name: str, factory: Callable[..., Provider]) -> None:
    _FACTORIES[name] = factory

def resolve(name: str, **kwargs) -> Provider:
    if name not in _FACTORIES:
        _load_entry_points()
    if name not in _FACTORIES:
        raise KeyError(f"Unknown provider: {name!r}. Known: {list(_FACTORIES)}")
    return _FACTORIES[name](**kwargs)

def _load_entry_points() -> None:
    for ep in entry_points(group="aiproxy.providers"):
        register(ep.name, ep.load())
```

Built-in providers self-register on import. Third-party providers can either import-and-register, or declare `[project.entry-points."aiproxy.providers"]`.

---

## 6. Configuration

Pydantic-settings, per provider. Each provider owns its own settings class.

```python
class AnthropicSettings(BaseSettings):
    api_key: SecretStr
    base_url: str = "https://api.anthropic.com"
    api_version: str = "2023-06-01"
    timeout_s: float = 60.0
    model_config = SettingsConfigDict(env_prefix="ANTHROPIC_", env_file=".env")

class OllamaSettings(BaseSettings):
    base_url: str = "http://localhost:11434"
    timeout_s: float = 120.0
    model_config = SettingsConfigDict(env_prefix="OLLAMA_", env_file=".env")
```

Caller usage:

```python
client = Client("anthropic", api_key="sk-ant-...")
client = Client("ollama", base_url="http://gpu-host:11434")
client = Client("anthropic")   # picks up ANTHROPIC_API_KEY from env
```

---

## 7. Provider-Specific Feature Handling

| Feature | How it's modeled |
|---|---|
| Anthropic top-level `system` | First-class `ChatRequest.system`. Ollama folds it into a `system` role message. |
| Anthropic tool_use / tool_result blocks | Native — neutral `ToolUsePart` / `ToolResultPart` map 1:1. |
| Ollama tools (OpenAI-shaped) | Provider translates `ToolSpec` → Ollama JSON, parses `tool_calls` → `ToolUsePart`. |
| Anthropic `cache_control` | Pass through `ChatRequest.extra={"cache_control": ...}`. |
| Ollama `keep_alive`, `num_ctx` | Same — `extra={"keep_alive": "5m", "num_ctx": 8192}`. |
| Streaming | Each provider implements `stream()` and emits neutral `StreamEvent`. |
| Vendor-only response fields | Preserved verbatim in `ChatResponse.raw`. |

The `extra` escape hatch avoids leaking every vendor knob into the neutral type.

---

## 8. Package Structure

```
aiproxy/
├── pyproject.toml
├── README.md
├── docs/architecture-brief.md
├── src/aiproxy/
│   ├── __init__.py
│   ├── client.py
│   ├── provider.py
│   ├── registry.py
│   ├── types.py
│   ├── streaming.py
│   ├── errors.py
│   └── providers/
│       ├── __init__.py
│       ├── anthropic.py
│       └── ollama.py
└── tests/
    ├── unit/
    │   ├── test_registry.py
    │   ├── test_client.py
    │   └── providers/
    │       ├── test_anthropic.py       # respx-mocked
    │       └── test_ollama.py
    └── integration/
        └── test_ollama_live.py         # opt-in
```

Single-package layout. No core/provider split — premature.

---

## 9. Error Taxonomy

```python
class AIProxyError(Exception): ...
class ConfigurationError(AIProxyError): ...
class ProviderError(AIProxyError):
    def __init__(self, msg, *, provider, status=None, raw=None): ...
class RateLimitError(ProviderError): ...
class AuthenticationError(ProviderError): ...
class TimeoutError_(ProviderError): ...
class ToolArgumentError(AIProxyError): ...
```

Providers map HTTP status codes / error envelopes to this taxonomy.

---

## 10. Key Design Decisions & Tradeoffs

| Decision | Why | Tradeoff |
|---|---|---|
| Async-first, sync via wrapper | Natural for httpx+streaming | `chat_sync` not callable inside running loop |
| `Protocol` over ABC | Zero inheritance coupling | `isinstance` needs `@runtime_checkable` |
| Plain dataclasses for domain types | Minimal deps, immutable | Providers parse JSON explicitly |
| Pydantic-settings only at config | Per-provider env prefix, validated at startup | Two type systems (segregated) |
| `ChatRequest.extra` escape hatch | Vendor knobs without API bloat | Code using `extra` is non-portable |
| `ChatResponse.raw` always populated | Debugging, audit | Slightly larger response objects |
| Direct imports + opt-in entry points | Simple now, plugin-ready later | None meaningful |
| One package, not split | YAGNI — current deps light (`httpx`) | Split later if heavyweight SDK arrives |
| No retry/backoff in v1 | No concrete requirement | Add when proxy service needs reliability |
| No caching/rate-limit/token-count | YAGNI — proxy service can wrap `Client` | Library stays thin |

---

## 11. First Milestone

1. `aiproxy.types`, `aiproxy.streaming`, `aiproxy.provider`, `aiproxy.registry`, `aiproxy.errors`, `aiproxy.client`.
2. `OllamaProvider` — `chat` + `stream` against local docker `ollama`.
3. `AnthropicProvider` — `chat` + `stream` (real API; `respx` mocks in unit tests).
4. End-to-end test: same `ChatRequest` to both, both return `TextPart` content.
5. One tool-calling test per provider: `get_weather` tool returns `ToolUsePart`.

---

## 12. Out of Scope (YAGNI — do not build yet)

- Retry / exponential backoff middleware
- Response caching
- Rate limiting / quota tracking
- Token counting / cost estimation
- Prompt templating engine
- Conversation/session persistence
- Embeddings, image generation, audio APIs (chat completions only for v1)
- Structured-output / JSON-mode helpers
- Multi-provider fallback / load balancing
- Observability hooks (OpenTelemetry)
- Sync-from-async worker pool
- CLI tool

---

## 13. AWS Promotion Checklist

This is a library, not a service — no infrastructure to promote. When the `aiproxy` gateway service is later designed on top of this library, that brief will own the AWS checklist (Secrets Manager for `ANTHROPIC_API_KEY`, VPC routing to self-hosted Ollama, etc.).
