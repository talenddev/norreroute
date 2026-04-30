TASK-6: Integration — same ChatRequest round-trips through both providers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: both AnthropicProvider and OllamaProvider fully implemented (TASK-4, TASK-5).
    Client facade from TASK-3.
  What this task enables: TASK-7 (tool-call tests build on this wiring).

DEPENDS ON
  TASK-4, TASK-5

OBJECTIVE
  Write an integration test file (respx-mocked) that sends the same ChatRequest through
  Client("anthropic") and Client("ollama") and verifies that both return a ChatResponse
  with at least one TextPart in content, the correct model field, and a non-null Usage.
  Also verify that Client("unknown-provider") raises KeyError.

ACCEPTANCE CRITERIA
  - [ ] tests/integration/__init__.py exists
  - [ ] tests/integration/test_roundtrip.py sends a shared ChatRequest (role=user, TextPart content)
        to both providers via Client facade (async path)
  - [ ] Both responses are ChatResponse instances with content containing at least one TextPart
  - [ ] Response.model matches the model field in the ChatRequest for each provider
  - [ ] Response.usage is a Usage instance with input_tokens >= 0 and output_tokens >= 0
  - [ ] Resolving Client("unknown-provider") raises KeyError
  - [ ] tests/integration/test_ollama_live.py exists with one test marked @pytest.mark.skipif
        (skip unless AIPROXY_LIVE_TESTS=1 env var set) that sends a real request to
        localhost:11434 — test body is a placeholder that skips gracefully; no live call in CI
  - [ ] `uv run pytest tests/integration/test_roundtrip.py -v` exits 0
  - [ ] `uv run mypy tests/integration/test_roundtrip.py` exits 0 (or passes with --ignore-missing-imports)
  - [ ] All previous unit tests still pass: `uv run pytest tests/unit/ -v` exits 0

FILES TO CREATE OR MODIFY
  - tests/integration/__init__.py                ← new
  - tests/integration/test_roundtrip.py          ← new
  - tests/integration/test_ollama_live.py        ← new (placeholder with skip guard)

CONSTRAINTS
  - No live network calls in test_roundtrip.py — use respx to mock both providers
  - Live test in test_ollama_live.py must skip when AIPROXY_LIVE_TESTS != "1"
  - Import both providers by name string via Client, not direct class instantiation,
    to exercise the registry resolve path
  - Use pytest-asyncio for async test functions

OUT OF SCOPE FOR THIS TASK
  - Tool-call round-trips (TASK-7)
  - Stream path integration tests (nice-to-have, not required here)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-6-integration-roundtrip  (branch from develop)
  Commit when done:
    test(integration): verify same ChatRequest round-trips through both providers
  Open PR into: develop
