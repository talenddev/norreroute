AUDIT REQUEST: TASK-1 — Package scaffold
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files delivered by developer:
  - src/aiproxy/__init__.py
  - src/aiproxy/types.py (stub)
  - src/aiproxy/streaming.py (stub)
  - src/aiproxy/errors.py (stub)
  - src/aiproxy/provider.py (stub)
  - src/aiproxy/registry.py (stub)
  - src/aiproxy/client.py (stub)
  - src/aiproxy/providers/__init__.py
  - src/aiproxy/providers/anthropic.py (stub)
  - src/aiproxy/providers/ollama.py (stub)
  - pyproject.toml (modified)

Acceptance criteria to verify:
  - [ ] uv run python -c "import aiproxy" exits 0
  - [ ] uv run pytest --co exits without collection errors
  - [ ] uv run ruff check src/ exits 0

Context: Pure scaffold task — no logic, no unit tests expected.
Coverage target: N/A (stubs only)

Run:
  uv run pytest --cov=src --cov-report=term-missing tests/

Report back:
  - PASS or FAIL
  - Coverage % for new files
  - Any collection errors
