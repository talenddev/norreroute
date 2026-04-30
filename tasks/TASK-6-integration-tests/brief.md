TASK-6: Integration tests — same ChatRequest through both providers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: AnthropicProvider (TASK-4) and OllamaProvider (TASK-5) fully
               implemented. Client facade from TASK-3.
  What this task enables: TASK-7 (tool-call support) — establishes the test
                          pattern that TASK-7 extends.

DEPENDS ON
  TASK-4, TASK-5

OBJECTIVE
  Write integration-style tests (still mocked HTTP via respx) that send the same
  ChatRequest through both providers via the Client facade and assert both return
  equivalent ChatResponse structures.

ACCEPTANCE CRITERIA
  - [ ] tests/unit/test_integration.py (respx-mocked, no live network):
        - A single ChatRequest with model+messages+system is constructed once
        - Both AnthropicProvider and OllamaProvider are instantiated (settings
          can be constructed directly with test values)
        - Both providers' chat() returns a ChatResponse with at least one TextPart
        - Both ChatResponse.finish_reason == "stop"
        - Both ChatResponse.usage.input_tokens > 0
        - Both ChatResponse.usage.output_tokens > 0
        - Test parametrized over [anthropic_client, ollama_client] so failures
          show which provider failed
  - [ ] Streaming round-trip test (both providers):
        - stream() yields at least one TextDelta event
        - stream() last event is StreamEnd with finish_reason set
        - Parametrized over both providers
  - [ ] Client facade used (not providers directly): Client(provider=provider_instance)
  - [ ] uv run pytest tests/unit/test_integration.py -- all pass
  - [ ] uv run ruff check tests/unit/test_integration.py
  - [ ] Coverage for src/aiproxy/client.py >= 80% after this task

FILES TO CREATE OR MODIFY
  - tests/unit/test_integration.py    <- new

CONSTRAINTS
  - All HTTP mocked with respx — no live network calls
  - Use pytest.mark.parametrize for provider parametrization
  - Fixtures for mock providers should be in the test file (not conftest.py)
    unless they are reused across files
  - Tests must be async (pytest-asyncio, asyncio_mode="auto")
  - stream_sync() tested in at least one case to verify sync wrapper

OUT OF SCOPE FOR THIS TASK
  - Tool-call integration (TASK-7)
  - Live network tests (tests/integration/test_ollama_live.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-6-integration-tests  (branch from develop)
  Commit when done:
    test(integration): add cross-provider round-trip tests with mocked HTTP
  Open PR into: develop
