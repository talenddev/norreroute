TASK-3: Anthropic vision serialisation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/norreroute/providers/anthropic.py with _messages_to_anthropic()
               that handles TextPart, ToolUsePart, ToolResultPart but would encounter
               ImagePart in the bare else branch (ToolResultPart) once TASK-1 lands.
               TASK-1 will have added ImagePart to types.py.
  What this task enables: TASK-4 (capability guard uses AnthropicProvider.supports_vision)

DEPENDS ON
  TASK-1

OBJECTIVE
  Update _messages_to_anthropic in providers/anthropic.py to serialise ImagePart
  as an Anthropic-format image block, and add explicit TypeError for unknown parts.

ACCEPTANCE CRITERIA
  - [ ] ImagePart(data=b"\xff\xd8", media_type="image/png") serialises to
        {"type":"image","source":{"type":"base64","media_type":"image/png","data":"<b64>"}}
  - [ ] Single TextPart message still flattens to plain string (regression)
  - [ ] Mixed text + image -> list of two blocks (no flatten)
  - [ ] Unknown part type raises TypeError with message containing part type name
  - [ ] `import base64` added at module top
  - [ ] ImagePart added to the existing `from norreroute.types import (...)` group
  - [ ] bare `else: # ToolResultPart` replaced with explicit isinstance check +
        final else raises TypeError
  - [ ] mypy --strict passes on src/norreroute
  - [ ] ruff check passes on src/ and tests/

FILES TO CREATE OR MODIFY
  - src/norreroute/providers/anthropic.py   ← modify
  - tests/test_anthropic_vision.py          ← new

CONSTRAINTS
  - Use uv for any new dependencies
  - Use pytest-mock to mock the anthropic SDK in e2e tests
  - Follow existing patterns in src/ if any exist
  - base64 is stdlib — no new pyproject.toml dependencies needed

OUT OF SCOPE FOR THIS TASK
  - Adding supports_vision class attribute (that is TASK-4)
  - Any changes to types.py, __init__.py, errors.py, client.py, retry.py
  - Ollama provider changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-3-anthropic-vision  (branch from develop after TASK-1 merged)
  Commit when done:
    feat(anthropic): add ImagePart base64 serialisation and unknown-part TypeError
  Open PR into: develop
