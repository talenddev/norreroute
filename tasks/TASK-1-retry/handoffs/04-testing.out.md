# Testing Output — TASK-1: Retry / Exponential Backoff

## Verdict: PASS

## Coverage
- `src/norreroute/retry.py`: 100% (after adding empty-stream test)
- `src/norreroute/_internal/__init__.py`: 100%

## Tests
26 passed (25 original + 1 added: `test_stream_empty_yields_nothing`)

## Bug reports
None.

## Missing test cases added
- `test_stream_empty_yields_nothing`: covers the `StopAsyncIteration` early-return path in `_stream_with_retry` (line 143 in original, now covered). An empty inner stream should yield nothing to the caller.

## All acceptance criteria verified
- RetryPolicy frozen dataclass with correct defaults: PASS
- should_retry logic: PASS
- delay_for full-jitter + max_delay cap: PASS
- RetryingProvider.chat retry loop: PASS
- RetryingProvider.stream retry boundary: PASS
- Client wiring for all three forms: PASS
- Exports from __init__.py: PASS

```yaml
---
handoff:
  result: ok
  coverage:
    retry.py: 100%
    _internal/__init__.py: 100%
  tests_added:
    - test_stream_empty_yields_nothing
  bugs: []
---
```
