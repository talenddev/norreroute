# Coding Output — TASK-1: Retry / Exponential Backoff

## Deliverables
- `src/norreroute/retry.py` — RetryPolicy (frozen dataclass) + RetryingProvider
- `src/norreroute/_internal/__init__.py` — full_jitter helper
- `src/norreroute/client.py` — extended with retry= kwarg and provider_name property
- `src/norreroute/__init__.py` — re-exports RetryPolicy, RetryingProvider
- `tests/unit/test_retry.py` — 25 unit tests

## Test results
- 107 tests passing (25 new + 82 existing)
- ruff: clean
- mypy: clean

## Notes
- AuthenticationError IS a ProviderError subclass, so it IS retried by the default policy. Tests document this explicitly and use retry_on=(RateLimitError,) to test the non-retryable path.
- stream() retry uses AsyncGenerator cast to call aclose() correctly.
- provider_name property added to Client (used by TASK-3 json_mode).
- PR: https://github.com/talenddev/norreroute/pull/14

```yaml
---
handoff:
  result: ok
  branch: feature/TASK-1-retry
  pr_url: https://github.com/talenddev/norreroute/pull/14
  files_created:
    - src/norreroute/retry.py
    - src/norreroute/_internal/__init__.py
    - tests/unit/test_retry.py
  files_modified:
    - src/norreroute/client.py
    - src/norreroute/__init__.py
  db_models_touched: false
  notes: "25 new tests, 107 total, clean ruff+mypy"
---
```
