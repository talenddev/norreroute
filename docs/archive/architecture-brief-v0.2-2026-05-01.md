# norreroute v0.2 — Architecture Brief

Status: design, pre-implementation
Scope: five additive features on top of v0.1
Constraint: **non-breaking** for any v0.1 consumer of `Client`, `Provider`, domain types, or errors

---

## 1. Guiding principles

- **Composition over inheritance.** New behaviour wraps `Provider`, never subclasses it.
- **YAGNI.** No plugin systems, no abstract middleware framework. Each feature is the smallest concrete thing that solves the stated problem.
- **Optional deps stay optional.** OTel and validators must not be imported at module load time when disabled.
- **Domain types are frozen.** Anything stateful (Conversation, retry counters) lives in new modules; `Message` / `ChatRequest` / `ChatResponse` are not touched.
- **One escape hatch already exists** (`ChatRequest.extra`, `ChatResponse.raw`) — reuse it; do not invent new ones.

---

## 2. Updated package structure

```
norreroute/
├── __init__.py              # re-exports v0.1 surface + new public symbols
├── types.py                 # unchanged
├── streaming.py             # unchanged
├── provider.py              # unchanged
├── registry.py              # unchanged
├── errors.py                # unchanged (AIProxyError kept; alias note in §8)
├── client.py                # extended: optional retry/trace/pricing wiring
├── providers/
│   ├── anthropic.py         # unchanged public behaviour; json_chat reads extra
│   └── ollama.py            # unchanged public behaviour
│
├── retry.py                 # NEW — RetryPolicy + RetryingProvider wrapper
├── pricing.py               # NEW — pricing table + estimate_cost / count_tokens
├── pricing_data.py          # NEW — structured constant: MODEL_PRICING
├── json_mode.py             # NEW — json_chat helper + JSON coercion
├── tracing.py               # NEW — OTel hook (lazy import, no-op when off)
├── conversation.py          # NEW — Conversation, TrimStrategy
└── _internal/
    └── __init__.py          # private helpers (jitter, clock, lazy_import)
```

Tests mirror layout under `tests/unit/` and `tests/integration/`.

---

## 3. Feature 1 — Retry / Exponential Backoff

### Public API

```python
# norreroute/retry.py
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3                  # total tries, not extra retries
    initial_delay: float = 0.5             # seconds
    max_delay: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.25                   # 0..1, fraction of delay
    retry_on: tuple[type[BaseException], ...] = (RateLimitError, ProviderError)

    def should_retry(self, exc: BaseException, attempt: int) -> bool: ...
    def delay_for(self, attempt: int) -> float: ...   # full-jitter formula

class RetryingProvider:
    """Wraps a Provider; same interface; retries chat() and stream()."""
    def __init__(self, inner: Provider, policy: RetryPolicy,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...
    async def chat(self, req: ChatRequest) -> ChatResponse: ...
    def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]: ...
    async def aclose(self) -> None: ...
```

### Client integration

```python
Client(provider="anthropic", retry=RetryPolicy(max_attempts=5))
Client(provider="anthropic", retry=False)   # default — no retry
```

`Client.__init__` resolves the provider, then optionally wraps it:

```python
self._provider = resolve(provider, **kwargs)
if retry:
    policy = retry if isinstance(retry, RetryPolicy) else RetryPolicy()
    self._provider = RetryingProvider(self._provider, policy)
```

### Streaming behaviour

- `stream()` retry only **before the first event is yielded**. Once any `TextDelta` / `ToolCallDelta` has been emitted to the caller, errors propagate — we never silently re-emit partial text.
- Implementation: open the inner `stream()`, await the first event inside a try/except; on retryable error before first yield, close the iterator and try again. After first yield, exceptions are raised as-is.
- `RetryingProvider.stream` returns an `async def` generator that owns this state machine.

### Key tradeoffs

- **Full jitter** (AWS-style: `delay = random(0, min(max_delay, initial * mult**attempt))`) over decorrelated jitter — simpler, well-understood.
- **No circuit breaker** in v0.2. YAGNI; add only if a concrete service-degradation incident demands it.
- **No per-call override.** Policy is set at `Client` construction. A per-request override is speculative.
- `retry_on` is a tuple of exception types; predicates rejected as over-engineered for v0.2.

### Test strategy

- Unit: a `FakeProvider` raising scripted exception sequences; assert call count, total slept time (inject fake `sleep`), and that non-retryable errors propagate immediately.
- Unit: stream fake yielding `[error]`, `[error, TextDelta, StreamEnd]`, `[TextDelta, error]` — assert retry, success, and propagation respectively.
- No real network in unit tests.

---

## 4. Feature 2 — Token Counting / Cost Estimation

### Public API

```python
# norreroute/pricing.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok_usd: float
    output_per_mtok_usd: float

@dataclass(frozen=True)
class CostEstimate:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    is_estimate: bool          # True when usage missing and we approximated

def estimate_cost(response: ChatResponse,
                  pricing: Mapping[str, ModelPrice] | None = None) -> CostEstimate: ...

def count_tokens_approx(request: ChatRequest) -> int:
    """Heuristic char/4 estimator for pre-flight budgeting. Not a tokenizer."""
```

### Pricing data

```python
# norreroute/pricing_data.py
MODEL_PRICING: dict[str, ModelPrice] = {
    "claude-3-5-sonnet-20241022": ModelPrice(3.00, 15.00),
    "claude-3-5-haiku-20241022":  ModelPrice(0.80,  4.00),
    "claude-3-opus-20240229":     ModelPrice(15.00, 75.00),
    # Ollama models — free, local
    "llama3.1":                    ModelPrice(0.0, 0.0),
    "qwen2.5":                     ModelPrice(0.0, 0.0),
}
```

- Resolution order: explicit `pricing` arg → `MODEL_PRICING` → `KeyError` wrapped as `AIProxyError` subclass `UnknownModelError`.
- A wildcard fallback `"ollama:*": ModelPrice(0,0)` rule lives in `pricing_data.py` as a small prefix-match helper — explicit, no regex engine.

### Client integration

`Client` is **not** modified for cost. `estimate_cost` is a free function consumers call with the `ChatResponse`. Keeping it out of the hot path preserves the rule that domain objects stay pure.

A convenience `Client.last_cost: CostEstimate | None` is **not** added — implicit state on a client is a bug magnet.

### Key tradeoffs

- **No real tokenizer** in v0.2. Anthropic returns usage in the response; Ollama returns `eval_count` / `prompt_eval_count` which the provider already maps into `Usage`. We trust `ChatResponse.usage` and skip a `tiktoken`-style dep.
- `count_tokens_approx` is documented as a coarse char/4 fallback for pre-flight checks only.
- Pricing in code (not YAML/JSON) for v0.2: type-checked, single import, easy diffs. A loader can be added later if a non-Python consumer needs it.

### Test strategy

- Unit: table-driven over `MODEL_PRICING`; assert math for known token counts.
- Unit: missing model raises `UnknownModelError`.
- Unit: missing `usage` on `ChatResponse` falls back to `count_tokens_approx` and sets `is_estimate=True`.

---

## 5. Feature 3 — Structured Output / JSON-Mode

### Public API

```python
# norreroute/json_mode.py
from typing import Type, TypeVar, overload
T = TypeVar("T")

async def json_chat(
    client: Client,
    request: ChatRequest,
    *,
    schema: Type[T] | None = None,
    strict: bool = True,
) -> tuple[ChatResponse, T | dict]: ...
```

- When `schema` is `None`, returns `(response, parsed_dict)`.
- When `schema` is a `dataclass` or `TypedDict`, returns `(response, schema_instance)` after coercion.
- `strict=True` raises `JSONValidationError` (new, subclass of `AIProxyError`) on parse or coercion failure; `strict=False` returns the raw text in a `JSONValidationError` `.partial` attribute via exception chaining — actually, simpler: `strict=False` returns `(response, None)` and logs a warning. We pick the simpler form.

### Provider-specific wiring

`json_chat` mutates a **copy** of the request (dataclasses are frozen — use `dataclasses.replace`) and merges `extra` based on the **provider name** the client was constructed with:

```python
hints = {
    "anthropic": {"response_format": {"type": "json_object"}},
    "ollama":    {"format": "json"},
}
```

The mapping lives in `json_mode.py` as a private dict. A new provider adding JSON mode adds itself to this dict (or, longer term, declares it via a capability — out of scope for v0.2).

`Client` exposes `client.provider_name: str` (read-only property) so `json_chat` can pick the right hint without reaching into internals.

### Coercion

- `dataclass`: `cls(**parsed_dict)` with a try/except wrapping `TypeError` into `JSONValidationError`.
- `TypedDict`: shallow type check on top-level keys; no recursive validation. Documented as "best-effort" — Pydantic is **not** added as a dep.
- Users wanting deep validation pass a dataclass with `__post_init__` checks, or do their own validation on the returned dict.

### Key tradeoffs

- No Pydantic. Adding it doubles the dep surface for one feature. If users need it they can call `MyModel.model_validate(parsed_dict)` themselves on the returned dict.
- No streaming JSON mode. Partial-JSON parsing is a research project; explicitly out of scope.

### Test strategy

- Unit: fake provider that echoes the merged `extra` back through `ChatResponse.raw`; assert correct hint per provider name.
- Unit: dataclass coercion happy path, missing field, extra field, wrong type.
- Unit: invalid JSON in response → `JSONValidationError` when strict, `(resp, None)` when not.

---

## 6. Feature 4 — Observability (OpenTelemetry)

### Public API

```python
Client(provider="anthropic", trace=True)
# or
Client(provider="anthropic", tracer=my_tracer)   # bring-your-own
```

Internally:

```python
# norreroute/tracing.py
def get_tracer(enabled: bool, custom: "Tracer | None") -> "Tracer | None":
    if not enabled and custom is None:
        return None
    return custom or _lazy_import_otel_tracer()

@contextmanager
def chat_span(tracer, request: ChatRequest): ...
@contextmanager
def stream_span(tracer, request: ChatRequest): ...
```

### Lazy-import guard

```python
# tracing.py top of file — NO `import opentelemetry` at module scope
def _lazy_import_otel_tracer():
    try:
        from opentelemetry import trace
    except ImportError as e:
        raise AIProxyError(
            "trace=True requires `pip install norreroute[otel]`"
        ) from e
    return trace.get_tracer("norreroute", _VERSION)
```

`pyproject.toml` adds:
```toml
[project.optional-dependencies]
otel = ["opentelemetry-api>=1.25"]
```

When `trace=False` (default) **no OTel symbol is referenced**, satisfying the "must not import OTel when unused" requirement.

### Span attributes (gen_ai semantic conventions)

Set on span start:
- `gen_ai.system` = provider name (`"anthropic"`, `"ollama"`)
- `gen_ai.request.model` = `request.model`
- `gen_ai.request.max_tokens`, `gen_ai.request.temperature` if set

Set on span end:
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` from `ChatResponse.usage`
- `gen_ai.response.finish_reason`
- `gen_ai.response.model`

On exception: span status = `ERROR`, exception recorded, then re-raised.

### Client integration

`Client.chat` becomes:

```python
async def chat(self, req):
    with chat_span(self._tracer, req) as span:
        resp = await self._provider.chat(req)
        if span: _set_response_attrs(span, resp)
        return resp
```

`chat_span` returns a no-op context manager when `tracer is None` so the hot path stays branch-light.

### Streaming

For `stream()` we open a span at the start, accumulate token counts from `StreamEnd.usage` (already in v0.1), and close the span when the iterator is exhausted or the caller breaks. Use `async with` semantics via an async context manager wrapper around the inner iterator.

### Key tradeoffs

- API only, not SDK. The user wires their own exporter — we never call `TracerProvider`.
- One vendor (OTel). No structlog/Datadog adapters; users can listen to OTel and forward.
- No metrics in v0.2. Spans cover the requirement; metrics is a separate feature.

### Test strategy

- Unit: in-memory span exporter (`opentelemetry-sdk` as test-only dep) asserts attributes set on success and on exception.
- Unit: `trace=False` path — monkeypatch `sys.modules["opentelemetry"]` to raise on import, run a chat, assert success (proves no import).
- Unit: stream span closes exactly once even when caller breaks early.

---

## 7. Feature 5 — Conversation / Session Persistence

### Public API

```python
# norreroute/conversation.py
from dataclasses import dataclass, field

@dataclass(frozen=True)
class TrimStrategy:
    max_input_tokens: int
    keep_system: bool = True
    keep_last_n: int = 2          # always preserve last N messages

class Conversation:
    def __init__(self, client: Client, *,
                 model: str,
                 system: str | None = None,
                 trim: TrimStrategy | None = None,
                 history: list[Message] | None = None) -> None: ...

    @property
    def messages(self) -> tuple[Message, ...]: ...   # immutable view

    async def send(self, text: str, **extra) -> ChatResponse: ...
    async def send_message(self, msg: Message, **extra) -> ChatResponse: ...
    def stream(self, text: str, **extra) -> AsyncIterator[StreamEvent]: ...

    def to_json(self) -> str: ...
    @classmethod
    def from_json(cls, data: str, client: Client) -> "Conversation": ...
```

### Trimming

Sliding window only:
1. If `keep_system` and a system message exists, pin it.
2. Always keep the last `keep_last_n` messages.
3. Drop oldest messages until estimated input tokens (via `count_tokens_approx`) ≤ `max_input_tokens`.
4. If trimming cannot satisfy the budget without dropping pinned messages, raise `ConversationOverflowError`.

Trimming is applied at `send()` time, not on append, so history stays a faithful log; only the request to the provider is trimmed.

### Serialisation format

```json
{
  "version": 1,
  "model": "claude-3-5-sonnet-20241022",
  "system": "You are...",
  "trim": {"max_input_tokens": 8000, "keep_system": true, "keep_last_n": 2},
  "messages": [
    {"role": "user", "parts": [{"type": "text", "text": "..."}]}
  ]
}
```

- `version` field gates future format changes.
- Messages serialise via a pure function in `conversation.py` that pattern-matches on the part dataclasses (`TextPart`, `ToolUsePart`, `ToolResultPart`). No JSON support is added to `types.py` itself — keeps domain types pure.

### Client integration

`Conversation` holds a `Client` reference but does not subclass it. The `Client` API is unchanged.

Streaming: `Conversation.stream` yields events and, on `StreamEnd`, appends the assistant's accumulated message to history. If the consumer breaks early, **partial responses are not appended** (mirrors the retry rule: history reflects only completed turns).

### Key tradeoffs

- **No summarisation.** Sliding window only, as specified. Summarisation would require an extra LLM call and a strategy abstraction — explicit non-goal for v0.2.
- **No persistence backend** (no SQLite, no Redis). `to_json` / `from_json` is the contract; users persist where they like. YAGNI.
- **Immutable history view.** `messages` is a tuple; mutation goes through `send_message` only. Prevents accidental edits desynchronising token estimates.

### Test strategy

- Unit: append → trim → assert pinned messages survive, oldest dropped.
- Unit: round-trip `to_json` / `from_json` over a conversation containing each part type.
- Unit: stream interruption does not append.
- Unit: overflow with un-droppable history raises `ConversationOverflowError`.

---

## 8. Errors module additions

```python
# norreroute/errors.py — additive only
class UnknownModelError(AIProxyError): ...
class JSONValidationError(AIProxyError): ...
class ConversationOverflowError(AIProxyError): ...
```

`AIProxyError` name is preserved for backwards compatibility. A short note in `__init__.py` documents that the project was renamed but the base class kept its name to avoid a v0.1 break. Renaming to `NorrerouteError` is deferred to a future major.

---

## 9. Dependencies

| Dep | Status | Reason |
|---|---|---|
| `opentelemetry-api` | optional (`[otel]`) | Tracing only; lazy-imported |
| `opentelemetry-sdk` | dev/test only | In-memory exporter for assertions |
| `pytest`, `pytest-asyncio` | dev | existing |
| `tiktoken` / `anthropic-tokenizer` | **rejected** | Heavy; usage already returned by providers |
| `pydantic` | **rejected** | Adds a runtime layer for one helper; users can opt in themselves |
| `tenacity` | **rejected** | Our retry needs are 60 lines; tenacity's API surface is larger than the feature |

No new required runtime deps. v0.2 stays a thin library.

---

## 10. Public surface (`norreroute/__init__.py`)

Re-exports added (everything v0.1 exports unchanged):

```python
from .retry import RetryPolicy, RetryingProvider
from .pricing import ModelPrice, CostEstimate, estimate_cost, count_tokens_approx
from .json_mode import json_chat
from .conversation import Conversation, TrimStrategy
from .errors import UnknownModelError, JSONValidationError, ConversationOverflowError
# tracing intentionally NOT re-exported at top level — accessed via Client(trace=...)
```

---

## 11. Backwards compatibility (v0.1 → v0.2)

Non-breaking guarantees:

1. `Client(provider=...)` with no new kwargs behaves identically to v0.1.
2. All v0.1 imports (`from norreroute import Client, ChatRequest, ...`) continue to resolve.
3. `Provider` Protocol is unchanged; existing custom providers keep working.
4. `RetryingProvider` satisfies `Provider` so it composes with anything expecting a `Provider`.
5. New kwargs on `Client` (`retry`, `trace`, `tracer`) all default to off/None.
6. Domain dataclasses (`Message`, `ChatRequest`, etc.) have **no field changes**.
7. The package rename (`aiproxy` → `norreroute`) is the one breaking change at the import-path level; documented in the v0.2 changelog with a migration note. The `AIProxyError` class name is intentionally preserved to soften the transition.

A deprecation shim package `aiproxy` re-exporting from `norreroute` is **out of scope** for v0.2 unless a concrete user needs it — flag for product decision before release.

---

## 12. First milestone (smallest working slice)

Ship in this order; each merges to `develop` behind its own `feature/TASK-*` branch:

1. `feature/TASK-1-retry` — `retry.py` + `Client` wiring + tests. No other feature depends on this.
2. `feature/TASK-2-pricing` — `pricing.py` + `pricing_data.py` + tests. Pure functions, no client change.
3. `feature/TASK-3-json-mode` — `json_mode.py` + provider-name property on `Client` + tests.
4. `feature/TASK-4-tracing` — `tracing.py` + optional dep + `Client(trace=...)` + tests.
5. `feature/TASK-5-conversation` — `conversation.py` + tests.

Each PR squash-merges per CLAUDE.md git flow. Cut `release/0.2.0` from `develop` when all five land green.

---

## 13. Out of scope for v0.2 (YAGNI)

- Circuit breaker / bulkhead patterns
- Real tokenizer integration (tiktoken, anthropic-tokenizer)
- Pydantic models for JSON schemas
- Streaming JSON parsing
- OTel metrics / logs (spans only)
- Conversation summarisation
- Conversation persistence backends (SQLite, Redis, S3)
- Per-request retry overrides
- `aiproxy` deprecation shim package
- Pricing loaded from external YAML/JSON
- Multi-provider failover ("if Anthropic 429s, try Ollama")
