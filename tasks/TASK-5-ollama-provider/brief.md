TASK-5: Ollama provider
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: Provider Protocol, Client, Registry from TASK-3; domain types from
               TASK-2. No Ollama SDK — use direct httpx calls to the REST API.
  What this task enables: TASK-6 (integration tests) and TASK-7 (tool-call support).

DEPENDS ON
  TASK-3

OBJECTIVE
  Implement src/aiproxy/providers/ollama.py: an OllamaProvider class that satisfies
  the Provider protocol, using httpx directly against the Ollama REST API
  (POST /api/chat), backed by OllamaSettings (pydantic-settings). All HTTP calls
  mocked via respx in tests.

ACCEPTANCE CRITERIA
  - [ ] OllamaSettings(BaseSettings) in src/aiproxy/providers/ollama.py with:
        base_url: str = "http://localhost:11434", timeout_s: float = 120.0,
        env_prefix="OLLAMA_", env_file=".env"
  - [ ] OllamaProvider satisfies isinstance(provider, Provider) check
  - [ ] OllamaProvider.name == "ollama"
  - [ ] OllamaProvider.chat() calls POST /api/chat with stream=false, maps
        response to ChatResponse with TextPart, correct finish_reason, Usage, raw
  - [ ] OllamaProvider handles ChatRequest.system by prepending a {"role":"system",
        "content": system} message to the messages list
  - [ ] OllamaProvider.stream() calls POST /api/chat with stream=true, reads
        NDJSON response line-by-line, yields TextDelta per chunk, StreamEnd at end
  - [ ] OllamaProvider.aclose() closes the httpx.AsyncClient
  - [ ] Module-level self-registration: on import, registers "ollama" in registry
  - [ ] HTTP errors: 404 -> ProviderError("model not found"), other 4xx/5xx -> ProviderError
  - [ ] ChatResponse.raw contains the untouched provider JSON payload
  - [ ] Unit tests in tests/unit/providers/test_ollama.py (respx mocks):
        - chat() returns ChatResponse with TextPart
        - chat() with system prepends system message
        - stream() yields TextDelta events then StreamEnd
        - 404 raises ProviderError
        - 500 raises ProviderError
        - OllamaProvider.name == "ollama"
  - [ ] uv run pytest tests/unit/providers/test_ollama.py -- all pass
  - [ ] uv run ruff check src/aiproxy/providers/ollama.py
  - [ ] uv run mypy src/aiproxy/providers/ollama.py

FILES TO CREATE OR MODIFY
  - src/aiproxy/providers/ollama.py       <- implement
  - tests/unit/providers/test_ollama.py   <- new

CONSTRAINTS
  - Use httpx.AsyncClient directly (no Ollama SDK)
  - Use respx to mock HTTP in tests
  - Ollama /api/chat endpoint: POST with JSON body {model, messages, stream, options}
  - Streaming response is NDJSON (one JSON object per line)
  - Non-streaming response: response.json() -> {model, message, done_reason, prompt_eval_count,
    eval_count, ...}
  - Map done_reason: "stop" -> "stop", "length" -> "length", else "stop" as fallback
  - No retry logic — raise immediately on error

OUT OF SCOPE FOR THIS TASK
  - Tool-call handling (TASK-7)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-5-ollama-provider  (branch from develop)
  Commit when done:
    feat(ollama): implement OllamaProvider with chat and stream
  Open PR into: develop
