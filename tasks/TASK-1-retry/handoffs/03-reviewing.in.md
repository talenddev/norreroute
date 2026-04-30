# Review Request — TASK-1: Retry / Exponential Backoff

## PR
https://github.com/talenddev/norreroute/pull/14
Branch: feature/TASK-1-retry

## Files delivered
- `src/norreroute/retry.py` — RetryPolicy frozen dataclass + RetryingProvider
- `src/norreroute/_internal/__init__.py` — full_jitter private helper
- `src/norreroute/client.py` — extended: retry= kwarg, provider_name property
- `src/norreroute/__init__.py` — re-exports RetryPolicy, RetryingProvider
- `tests/unit/test_retry.py` — 25 unit tests

## Acceptance criteria to verify
- [ ] RetryPolicy is frozen dataclass with correct default fields
- [ ] should_retry(exc, attempt) returns True iff isinstance(exc, retry_on) and attempt < max_attempts
- [ ] delay_for(attempt) uses AWS full-jitter formula
- [ ] RetryingProvider satisfies Provider Protocol (name, chat, stream, aclose)
- [ ] chat() retries on retryable errors; sleeps using injected sleep
- [ ] stream() retries only before first TextDelta/ToolCallDelta; propagates after
- [ ] Client(retry=RetryPolicy(...)) wraps in RetryingProvider
- [ ] Client(retry=True) wraps with default policy
- [ ] Client() / Client(retry=False) leaves provider unwrapped
- [ ] RetryPolicy, RetryingProvider exported from __init__.py
- [ ] No new required runtime deps

## Review focus areas
- Type safety (mypy passes, correct Protocol satisfaction)
- Stream retry boundary: is the "after first content event" rule correct?
- Jitter formula correctness
- Thread/async safety of the generator-based retry
- Test coverage adequacy
- YAGNI: any over-engineering?

## Report back
End your response with:

```yaml
---
handoff:
  result: ok   # or: blocked
  findings: []  # list of issues if blocked
  notes: ""
---
```
