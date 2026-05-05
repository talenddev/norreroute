TASK-1: Add ImagePart, ChatResponse.text, Message.user/system
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT
  What exists: src/norreroute/types.py with TextPart, ToolUsePart, ToolResultPart,
               Message, ChatRequest, ChatResponse, Usage frozen dataclasses.
               ContentPart = TextPart | ToolUsePart | ToolResultPart
  What this task enables: TASK-2 (Ollama vision), TASK-3 (Anthropic vision),
                          TASK-4 (capability guard) — all depend on ImagePart existing

DEPENDS ON
  none

OBJECTIVE
  Add ImagePart frozen dataclass, extend ContentPart union, add ChatResponse.text
  property, and add Message.user/system classmethods to types.py.

ACCEPTANCE CRITERIA
  - [ ] `from norreroute.types import ImagePart` works
  - [ ] `ImagePart(data=b"\xff\xd8")` is hashable and frozen (mutation raises FrozenInstanceError)
  - [ ] `ImagePart` default media_type is "image/jpeg", type literal is "image"
  - [ ] ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart
  - [ ] `ChatResponse(...).text` returns concatenated text from all TextPart blocks
  - [ ] `ChatResponse(...).text` returns "" when content has only tool-use parts
  - [ ] `Message.user("hi", images=[b"\xff\xd8"]).content` is [TextPart("hi"), ImagePart(b"\xff\xd8")]
  - [ ] `Message.user(images=[b"x"]).content` has no TextPart (skipped when text is "")
  - [ ] `Message.user("hi").content` is [TextPart("hi")] with no ImagePart
  - [ ] `Message.system("be brief").content == [TextPart(text="be brief")]`
  - [ ] `Message.system("be brief").role == "system"`
  - [ ] "ImagePart" appended to __all__ in types.py
  - [ ] top-level norreroute/__init__.py NOT modified for ImagePart
  - [ ] mypy --strict passes on src/norreroute
  - [ ] ruff check passes on src/ and tests/

FILES TO CREATE OR MODIFY
  - src/norreroute/types.py   ← modify
  - tests/test_vision_types.py  ← new

CONSTRAINTS
  - Use uv for any new dependencies
  - No external HTTP calls without mocking in tests
  - Follow existing patterns in src/ if any exist
  - ImagePart.data is bytes only — do NOT accept pre-built ImagePart in Message.user images param
  - images param in Message.user accepts Sequence[bytes] only

OUT OF SCOPE FOR THIS TASK
  - Any changes to providers/ollama.py or providers/anthropic.py
  - Any changes to __init__.py
  - Any changes to errors.py, client.py, retry.py
  - Any HTTP calls or provider integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GIT
  Branch: feature/TASK-1-image-part-type  (branch from develop)
  Commit when done:
    feat(types): add ImagePart, ChatResponse.text, Message.user/system
  Open PR into: develop
