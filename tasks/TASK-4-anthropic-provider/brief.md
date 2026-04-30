TASK-4: Anthropic Claude provider
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: Provider Protocol, Client, Registry from TASK-3; domain types from
               TASK-2; scaffold from TASK-1 (anthropic SDK already in deps).
  What this task enables: TASK-6 (integration tests) and TASK-7 (tool-call support).

DEPENDS ON
  TASK-3

OBJECTIVE
  Implement src/aiproxy/providers/anthropic.py: an AnthropicProvider class that
  satisfies the Provider protocol, using the anthropic SDK (not raw httpx), backed
  by AnthropicSettings (pydantic-settings). All HTTP calls mocked via respx in tests.

ACCEPTANCE CRITERIA
  - [ ] AnthropicSettings(BaseSettings) in src/aiproxy/providers/anthropic.py with:
        api_key: SecretStr, base_url: str, api_version: str, timeout_s: float,
        env_prefix="ANTHROPIC_", env_file=".env"
  - [ ] AnthropicProvider satisfies isinstance(provider, Provider) check
  - [ ] AnthropicProvider.name == "anthropic"
  - [ ] AnthropicProvider.chat() maps ChatRequest -> Anthropic messages API ->
        ChatResponse with TextPart content, correct finish_reason, Usage, and raw
  - [ ] AnthropicProvider.chat() maps ChatRequest.system to top-level system param
  - [ ] AnthropicProvider.stream() yields TextDelta events then StreamEnd
  - [ ] AnthropicProvider.aclose() closes the underlying httpx client
  - [ ] Module-level self-registration: on import, registers "anthropic" in registry
  - [ ] HTTP errors map to correct exception types:
        401 -> AuthenticationError, 429 -> RateLimitError, other 4xx/5xx -> ProviderError
  - [ ] ChatResponse.raw contains the untouched provider payload
  - [ ] ANTHROPIC_API_KEY value is NOT present in ChatResponse.raw or any log output
  - [ ] Unit tests in tests/unit/providers/test_anthropic.py (respx mocks, no real API):
        - chat() returns ChatResponse with TextPart
        - chat() with system param sends system field to API
        - stream() yields TextDelta + StreamEnd
        - 401 raises AuthenticationError
        - 429 raises RateLimitError
        - 500 raises ProviderError
  - [ ] uv run pytest tests/unit/providers/test_anthropic.py -- all pass
  - [ ] uv run ruff check src/aiproxy/providers/anthropic.py
  - [ ] uv run mypy src/aiproxy/providers/anthropic.py

FILES TO CREATE OR MODIFY
  - src/aiproxy/providers/anthropic.py    <- implement
  - tests/unit/providers/test_anthropic.py <- new

CONSTRAINTS
  - Use the anthropic SDK (import anthropic), not raw httpx for this provider
  - Use respx to mock HTTP in tests (not unittest.mock patching SDK internals)
    -- if the SDK wraps httpx, respx can intercept; otherwise mock at SDK level
    -- if respx cannot intercept the SDK transport, use pytest-mock to patch
       the SDK client methods directly (anthropic.AsyncAnthropic)
  - AnthropicSettings reads from env vars with prefix ANTHROPIC_
  - api_key must be SecretStr; never call .get_secret_value() outside the provider
  - No retry logic — raise immediately on error

OUT OF SCOPE FOR THIS TASK
  - Tool-call handling (TASK-7)
  - Streaming with tool calls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-4-anthropic-provider  (branch from develop)
  Commit when done:
    feat(anthropic): implement AnthropicProvider with chat and stream
  Open PR into: develop
