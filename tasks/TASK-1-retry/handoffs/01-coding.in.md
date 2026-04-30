# Coding Handoff — TASK-1: Retry / Exponential Backoff

## Your task
Read `/var/home/leo/Documents/aiproxy/tasks/TASK-1-retry/brief.md` for full acceptance criteria.

## Branch
Create branch `feature/TASK-1-retry` from `develop` and do all work there.

## Key files to read first
- `/var/home/leo/Documents/aiproxy/src/norreroute/client.py` — Client class to extend
- `/var/home/leo/Documents/aiproxy/src/norreroute/errors.py` — RateLimitError, ProviderError
- `/var/home/leo/Documents/aiproxy/src/norreroute/provider.py` — Provider Protocol
- `/var/home/leo/Documents/aiproxy/src/norreroute/types.py` — ChatRequest, ChatResponse
- `/var/home/leo/Documents/aiproxy/src/norreroute/streaming.py` — StreamEvent, TextDelta, ToolCallDelta, StreamEnd
- `/var/home/leo/Documents/aiproxy/src/norreroute/__init__.py` — re-export surface

## What to build
1. `src/norreroute/retry.py` — RetryPolicy (frozen dataclass) + RetryingProvider
2. `src/norreroute/_internal/__init__.py` — if needed for jitter/clock helpers
3. Extend `src/norreroute/client.py` — add `retry=False` kwarg to `__init__`
4. Extend `src/norreroute/__init__.py` — re-export RetryPolicy, RetryingProvider
5. `tests/unit/test_retry.py` — full unit tests with FakeProvider

## Critical constraints
- Full-jitter formula: `random.uniform(0, min(max_delay, initial_delay * multiplier**attempt))`
- `sleep` is injectable (default `asyncio.sleep`) for deterministic tests
- `RetryingProvider.name` must delegate to `inner.name`
- stream() retry: peek first event before yielding; if retryable error BEFORE first yield, aclose iterator and restart; after first yield, propagate as-is
- No new required runtime deps — stdlib only

## Done condition
When all acceptance criteria in the brief are green, commit on `feature/TASK-1-retry`:
  `feat(retry): add RetryPolicy and RetryingProvider with Client wiring`
Then open a PR into `develop`.

## Report back
End your response with this exact YAML block:

```yaml
---
handoff:
  result: ok
  branch: feature/TASK-1-retry
  pr_url: <url or null>
  files_created:
    - src/norreroute/retry.py
    - tests/unit/test_retry.py
  files_modified:
    - src/norreroute/client.py
    - src/norreroute/__init__.py
  db_models_touched: false
  notes: <any notes>
---
```
