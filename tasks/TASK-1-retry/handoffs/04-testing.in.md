# Audit Request — TASK-1: Retry / Exponential Backoff
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files delivered by developer:
  - src/norreroute/retry.py
  - src/norreroute/_internal/__init__.py
  - src/norreroute/client.py (extended)
  - src/norreroute/__init__.py (extended)
  - tests/unit/test_retry.py

Acceptance criteria to verify:
  - [ ] RetryPolicy is frozen dataclass with correct defaults
  - [ ] should_retry returns correct bool based on type and attempt count
  - [ ] delay_for implements full-jitter and respects max_delay
  - [ ] RetryingProvider.chat retries on retryable errors up to max_attempts
  - [ ] RetryingProvider.stream retries only before first content event
  - [ ] Client(retry=...) wiring works correctly for all three forms
  - [ ] RetryPolicy and RetryingProvider exported from top-level __init__

Expected coverage target: >= 90% for new files

Run:
  uv run pytest --cov=src --cov-report=term-missing tests/unit/test_retry.py

Report back:
  - PASS or FAIL
  - Coverage % for new files
  - Bug reports (if any) in structured format
  - List of any missing test cases added by you
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
