# Coding Brief: TASK-1 — Add ImagePart, ChatResponse.text, Message.user/system

## Branch
`feature/TASK-1-image-part-type` (already created, you are on it)

## File to modify
`/var/home/leo/Documents/aiproxy/src/norreroute/types.py`

## File to create
`/var/home/leo/Documents/aiproxy/tests/test_vision_types.py`

## What to implement

### 1. Add ImagePart frozen dataclass after TextPart (line ~18 in types.py)
```python
@dataclass(frozen=True)
class ImagePart:
    """A binary image content block.

    Args:
        data: Raw image bytes (e.g. JPEG or PNG).
        media_type: MIME type of the image data. Providers that require
            base64 will encode ``data`` themselves during serialisation.
    """
    data: bytes
    media_type: str = "image/jpeg"
    type: Literal["image"] = "image"
```

### 2. Extend ContentPart union (currently line ~40)
Change:
```python
ContentPart = TextPart | ToolUsePart | ToolResultPart
```
To:
```python
ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart
```

### 3. Add text property to ChatResponse (add after `raw` field)
```python
@property
def text(self) -> str:
    """Return the concatenated text of all TextPart content blocks.

    Returns an empty string if the response contains no TextPart
    (e.g. a pure tool-use response).
    """
    return "".join(p.text for p in self.content if isinstance(p, TextPart))
```

### 4. Add Message.user and Message.system classmethods to Message dataclass
```python
@classmethod
def user(cls, text: str = "", *, images: Sequence[bytes] = ()) -> "Message":
    """Convenience constructor for a user-role message.

    Args:
        text: The text prompt (optional if images are provided).
        images: Raw image bytes. Each item becomes an ``ImagePart``
            with ``media_type="image/jpeg"``.

    Returns:
        A ``Message`` with role ``"user"``.
    """
    parts: list[ContentPart] = []
    if text:
        parts.append(TextPart(text=text))
    for img in images:
        parts.append(ImagePart(data=img))
    return cls(role="user", content=parts)

@classmethod
def system(cls, text: str) -> "Message":
    """Convenience constructor for a system-role message."""
    return cls(role="system", content=[TextPart(text=text)])
```

### 5. Append "ImagePart" to __all__ in types.py
Add `"ImagePart"` to the `__all__` list.

### IMPORTANT constraints
- Do NOT modify src/norreroute/__init__.py
- `images` param in Message.user accepts `Sequence[bytes]` only (no pre-built ImagePart)
- Keep `from __future__ import annotations` at top

## Tests to write in tests/test_vision_types.py

Write these 8 test functions:
- `test_image_part_is_frozen_and_typed` — verifies type literal "image", mutation raises FrozenInstanceError
- `test_image_part_preserves_bytes` — verifies data and media_type are preserved
- `test_chat_response_text_concatenates_text_parts` — multiple TextParts, text joins them
- `test_chat_response_text_empty_when_only_tool_use` — only ToolUsePart, text returns ""
- `test_message_user_text_only` — content is [TextPart("hi")], role is "user"
- `test_message_user_images_only` — text="", images=[b"x"], content has only ImagePart (no TextPart)
- `test_message_user_text_and_images` — content is [TextPart("hi"), ImagePart(b"\xff\xd8")]
- `test_message_system_single_text_part` — role "system", content [TextPart("be brief")]

Import pattern: `from norreroute.types import ...`
For FrozenInstanceError: `from dataclasses import FrozenInstanceError`

## Quality gates to verify before reporting done
- `cd /var/home/leo/Documents/aiproxy && uv run pytest tests/test_vision_types.py -v`
- `cd /var/home/leo/Documents/aiproxy && uv run mypy --strict src/norreroute`
- `cd /var/home/leo/Documents/aiproxy && uv run ruff check src/ tests/`

## Commit when done
```
feat(types): add ImagePart, ChatResponse.text, Message.user/system
```
