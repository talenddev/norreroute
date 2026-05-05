TASK-2: Ollama vision serialisation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/norreroute/providers/ollama.py with _messages_to_ollama() that
               handles TextPart, ToolResultPart, ToolUsePart but silently drops ImagePart.
               TASK-1 will have added ImagePart to types.py.
  What this task enables: TASK-4 (capability guard uses OllamaProvider.supports_vision)

DEPENDS ON
  TASK-1

OBJECTIVE
  Update _messages_to_ollama in providers/ollama.py to collect ImagePart instances
  and forward them as base64-encoded strings in the Ollama "images" field.

ACCEPTANCE CRITERIA
  - [ ] Message with TextPart + ImagePart serialises to Ollama dict with "images" as
        1-element base64 list and "content" equal to the text
  - [ ] Image-only message (no TextPart) -> content: "", images populated
  - [ ] No "images" key in output when no ImagePart present (regression check)
  - [ ] Images in tool-use/tool-result messages are dropped with a brief comment
  - [ ] `import base64` added at module top
  - [ ] ImagePart added to the existing `from norreroute.types import (...)` group
  - [ ] mypy --strict passes on src/norreroute
  - [ ] ruff check passes on src/ and tests/

FILES TO CREATE OR MODIFY
  - src/norreroute/providers/ollama.py   ← modify
  - tests/test_ollama_vision.py          ← new

CONSTRAINTS
  - Use uv for any new dependencies
  - Use respx to mock /api/chat in e2e tests
  - Follow existing patterns in src/ if any exist
  - base64 is stdlib — no new pyproject.toml dependencies needed

OUT OF SCOPE FOR THIS TASK
  - Adding supports_vision class attribute (that is TASK-4)
  - Any changes to types.py, __init__.py, errors.py, client.py, retry.py
  - Anthropic provider changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-2-ollama-vision  (branch from develop after TASK-1 merged)
  Commit when done:
    feat(ollama): add ImagePart base64 serialisation to _messages_to_ollama
  Open PR into: develop
