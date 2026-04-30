TASK-2: Core data model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/aiproxy/ package scaffold from TASK-1 (stub files only).
  What this task enables: TASK-3 (provider protocol), TASK-4 (Anthropic), TASK-5
                          (Ollama) — all depend on these shared types.

DEPENDS ON
  TASK-1

OBJECTIVE
  Implement all frozen dataclasses for the domain model in src/aiproxy/types.py and
  src/aiproxy/streaming.py, plus the error hierarchy in src/aiproxy/errors.py,
  exactly as specified in the architecture brief.

ACCEPTANCE CRITERIA
  - [ ] src/aiproxy/types.py defines: Role, TextPart, ToolUsePart, ToolResultPart,
        ContentPart (union), Message, ToolSpec, ChatRequest, Usage, ChatResponse
        — all with frozen=True dataclasses
  - [ ] src/aiproxy/streaming.py defines: TextDelta, ToolCallDelta, StreamEnd,
        StreamEvent (union) — all with frozen=True dataclasses
  - [ ] src/aiproxy/errors.py defines: AIProxyError, ConfigurationError,
        ProviderError (with provider/status/raw kwargs), RateLimitError,
        AuthenticationError, TimeoutError_, ToolArgumentError
  - [ ] ChatRequest.tools defaults to empty tuple (), stop defaults to ()
  - [ ] ChatRequest.extra uses field(default_factory=dict)
  - [ ] All fields typed correctly per architecture brief (Sequence, Literal, etc.)
  - [ ] Unit tests in tests/unit/test_types.py:
        - Construct each dataclass; verify fields accessible
        - Verify frozen (attempt mutation raises FrozenInstanceError)
        - Verify ContentPart union isinstance checks work
        - Verify StreamEvent union isinstance checks work
  - [ ] Unit tests in tests/unit/test_errors.py:
        - ProviderError carries provider, status, raw attributes
        - RateLimitError is a ProviderError
        - AuthenticationError is a ProviderError
  - [ ] uv run pytest tests/unit/test_types.py tests/unit/test_errors.py -- all pass
  - [ ] uv run ruff check src/aiproxy/types.py src/aiproxy/streaming.py src/aiproxy/errors.py
  - [ ] uv run mypy src/aiproxy/types.py src/aiproxy/streaming.py src/aiproxy/errors.py

FILES TO CREATE OR MODIFY
  - src/aiproxy/types.py              <- implement
  - src/aiproxy/streaming.py          <- implement
  - src/aiproxy/errors.py             <- implement
  - tests/unit/test_types.py          <- new
  - tests/unit/test_errors.py         <- new

CONSTRAINTS
  - No Pydantic in types.py or streaming.py — plain dataclasses only
  - from __future__ import annotations at top of each file
  - Use typing.Sequence (not list) for collection fields on ChatRequest/Message
  - Use field(default_factory=dict) for ChatRequest.extra (not default={})
  - Follow architecture brief section 2 exactly for field names and types

OUT OF SCOPE FOR THIS TASK
  - Provider implementations
  - Registry or client code
  - Pydantic settings classes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-2-core-data-model  (branch from develop)
  Commit when done:
    feat(types): implement core domain model dataclasses and error hierarchy
  Open PR into: develop
