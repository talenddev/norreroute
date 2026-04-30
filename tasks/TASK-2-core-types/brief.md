TASK-2: Core domain types — frozen dataclasses and streaming events
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/aiproxy/types.py and src/aiproxy/streaming.py as empty stubs (from TASK-1).
  What this task enables: TASK-3 (Provider protocol, Client facade), TASK-4, TASK-5 providers.

DEPENDS ON
  TASK-1

OBJECTIVE
  Implement all frozen dataclass types in aiproxy/types.py and aiproxy/streaming.py
  exactly as specified in the architecture brief, and write a thorough unit test suite.

ACCEPTANCE CRITERIA
  - [ ] types.py defines: TextPart, ToolUsePart, ToolResultPart, ContentPart, Message,
        ToolSpec, ChatRequest, Usage, ChatResponse — all frozen dataclasses
  - [ ] streaming.py defines: TextDelta, ToolCallDelta, StreamEnd, StreamEvent — all frozen dataclasses
  - [ ] Role = Literal["system", "user", "assistant", "tool"] defined in types.py
  - [ ] ChatRequest.tools defaults to () and ChatRequest.stop defaults to ()
  - [ ] ChatRequest.extra uses field(default_factory=dict)
  - [ ] All dataclass fields have correct type annotations matching the brief
  - [ ] No Pydantic in types.py or streaming.py (plain dataclasses only)
  - [ ] tests/unit/test_types.py: constructs every type, verifies frozen (AttributeError on mutation),
        verifies defaults, verifies type literals
  - [ ] tests/unit/test_streaming.py: constructs every StreamEvent variant
  - [ ] `uv run pytest tests/unit/test_types.py tests/unit/test_streaming.py -v` exits 0
  - [ ] `uv run mypy src/aiproxy/types.py src/aiproxy/streaming.py` exits 0
  - [ ] Coverage >= 90% on types.py and streaming.py

FILES TO CREATE OR MODIFY
  - src/aiproxy/types.py                    ← implement
  - src/aiproxy/streaming.py                ← implement
  - tests/__init__.py                       ← ensure exists
  - tests/unit/__init__.py                  ← new
  - tests/unit/test_types.py                ← new
  - tests/unit/test_streaming.py            ← new

CONSTRAINTS
  - Use `from __future__ import annotations` at top of each module
  - ChatResponse.finish_reason: Literal["stop", "length", "tool_use", "error"]
  - ContentPart = TextPart | ToolUsePart | ToolResultPart (type alias, not a class)
  - StreamEvent = TextDelta | ToolCallDelta | StreamEnd (type alias, not a class)
  - Follow exact field names and types from the architecture brief — no additions

OUT OF SCOPE FOR THIS TASK
  - errors.py, provider.py, registry.py, client.py (those are TASK-3)
  - Any network or provider logic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-2-core-types  (branch from develop)
  Commit when done:
    feat(types): implement frozen dataclass domain model and streaming events
  Open PR into: develop
