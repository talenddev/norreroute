TASK-1: Retry / Exponential Backoff
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists:
    - src/norreroute/client.py — Client class with _provider: Provider
    - src/norreroute/provider.py — Provider Protocol (chat, stream, aclose)
    - src/norreroute/errors.py — RateLimitError, ProviderError, AIProxyError
    - src/norreroute/types.py — ChatRequest, ChatResponse
    - src/norreroute/streaming.py — StreamEvent, TextDelta, ToolCallDelta, StreamEnd
  What this task enables: any future feature that needs a Client wrapping retry behaviour

DEPENDS ON
  none

OBJECTIVE
  Implement RetryPolicy + RetryingProvider in retry.py and wire them into Client via an optional retry= kwarg.

ACCEPTANCE CRITERIA
  - [ ] RetryPolicy is a frozen dataclass with fields: max_attempts (3), initial_delay (0.5), max_delay (30.0), multiplier (2.0), jitter (0.25), retry_on tuple defaulting to (RateLimitError, ProviderError)
  - [ ] RetryPolicy.should_retry(exc, attempt) returns True iff isinstance(exc, retry_on) and attempt < max_attempts
  - [ ] RetryPolicy.delay_for(attempt) implements AWS full-jitter: random(0, min(max_delay, initial * multiplier**attempt))
  - [ ] RetryingProvider wraps a Provider; satisfies the Provider Protocol (has name, chat, stream, aclose)
  - [ ] RetryingProvider.chat() retries on retryable errors up to max_attempts; sleeps between attempts using injected sleep callable
  - [ ] RetryingProvider.stream() retries only BEFORE the first TextDelta or ToolCallDelta is yielded; once any such event is emitted, errors propagate without retry
  - [ ] Client(provider="anthropic", retry=RetryPolicy(max_attempts=5)) wraps _provider in RetryingProvider
  - [ ] Client(provider="anthropic", retry=True) wraps _provider in RetryingProvider with default RetryPolicy()
  - [ ] Client(provider="anthropic") (no retry kwarg) leaves _provider unwrapped — identical to v0.1 behaviour
  - [ ] Client(provider="anthropic", retry=False) leaves _provider unwrapped
  - [ ] RetryPolicy and RetryingProvider are exported from norreroute/__init__.py
  - [ ] No new required runtime dependencies (only stdlib: asyncio, random, dataclasses)
  - [ ] FakeProvider test: scripted exception sequence [RateLimitError, RateLimitError, ok] → 3 calls, correct total sleep
  - [ ] FakeProvider test: non-retryable error (AuthenticationError) → propagates immediately after 1 attempt
  - [ ] Stream test: [error, error, TextDelta, StreamEnd] → retry twice then succeed
  - [ ] Stream test: [TextDelta, error] → error propagates (no retry after first yield)

FILES TO CREATE OR MODIFY
  - src/norreroute/retry.py         <- new
  - src/norreroute/client.py        <- extend __init__ with retry kwarg
  - src/norreroute/__init__.py      <- re-export RetryPolicy, RetryingProvider
  - src/norreroute/_internal/__init__.py  <- new (jitter helper if needed)
  - tests/unit/test_retry.py        <- new

CONSTRAINTS
  - Use uv for any new dependencies (there are none for this task)
  - sleep callable must be injectable (default asyncio.sleep) for deterministic tests
  - No external HTTP calls in tests — use a FakeProvider
  - Follow frozen dataclass pattern from types.py
  - RetryingProvider.name must delegate to inner.name
  - Full-jitter formula: random.uniform(0, min(max_delay, initial_delay * multiplier**attempt))
  - stream() retry: open inner stream, peek first event in try/except; on retryable error before any yield, aclose the iterator and restart

OUT OF SCOPE FOR THIS TASK
  - Circuit breaker
  - Per-call retry override
  - Predicate-based retry_on (only exception types)
  - Any changes to Provider Protocol itself
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-1-retry  (branch from develop)
  Commit when done:
    feat(retry): add RetryPolicy and RetryingProvider with Client wiring
  Open PR into: develop
