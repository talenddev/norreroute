# Feature Request: Vision / Multimodal Support in norreroute

**Requested by:** Leo (leo@talenddev.com)  
**Date:** 2026-05-05  
**norreroute version tested against:** 0.2.1  
**Context project:** [imagerec](https://github.com/talenddev/imagerec) — real-time webcam image recognition overlay  

---

## Background

We are trying to migrate `imagerec` from the raw `ollama` SDK to `norreroute` for provider-agnostic routing, built-in retry, and observability. The migration is fully viable for text workloads, but blocked on one structural gap: **norreroute has no multimodal content type**. imagerec's entire purpose is sending JPEG frames to a vision model (`/api/chat` with an `images` field), and that payload has nowhere to go in the current type system.

This document lists every change needed, ranked by priority, with exact proposed API surfaces and the specific files in norreroute that need to change.

---

## FR-1 — `ImagePart` content type *(blocker)*

### Problem

`ContentPart` in `types.py` is:

```python
ContentPart = TextPart | ToolUsePart | ToolResultPart
```

There is no way to attach binary image data to a `Message`. The type system rejects vision workloads at the boundary that matters most.

### Proposed change — `norreroute/types.py`

Add a new frozen dataclass and extend the union:

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


ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart
```

Export from `__init__.py`:

```python
from .types import ..., ImagePart
__all__ = [..., "ImagePart"]
```

### Why `bytes` not `str`

The caller (imagerec) holds raw JPEG bytes from `cv2.imencode`. Forcing callers to base64-encode before construction leaks a provider implementation detail into application code. Each provider serialiser should encode as required.

---

## FR-2 — Vision serialisation in the Ollama provider *(blocker)*

### Problem

`providers/ollama.py:_messages_to_ollama()` only handles `TextPart`, `ToolResultPart`, and `ToolUsePart`. Any `ImagePart` in a message content list is **silently dropped** — it never reaches the wire. The Ollama `/api/chat` endpoint accepts `{"images": ["<base64>"]}` on any message.

### Proposed change — `norreroute/providers/ollama.py`

Update `_messages_to_ollama` to collect and forward images:

```python
import base64
from norreroute.types import ImagePart  # add to existing import

def _messages_to_ollama(request: ChatRequest) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    if request.system:
        result.append({"role": "system", "content": request.system})

    for msg in request.messages:
        text_parts = [p for p in msg.content if isinstance(p, TextPart)]
        image_parts = [p for p in msg.content if isinstance(p, ImagePart)]
        tool_result_parts = [p for p in msg.content if isinstance(p, ToolResultPart)]
        tool_use_parts = [p for p in msg.content if isinstance(p, ToolUsePart)]

        if tool_result_parts:
            for part in tool_result_parts:
                result.append({"role": "tool", "content": part.content})
        elif tool_use_parts:
            calls = [
                {"function": {"name": p.name, "arguments": json.dumps(p.arguments)}}
                for p in tool_use_parts
            ]
            content = " ".join(p.text for p in text_parts) if text_parts else ""
            result.append({"role": msg.role, "content": content, "tool_calls": calls})
        else:
            content = " ".join(p.text for p in text_parts)
            ollama_msg: dict[str, Any] = {"role": msg.role, "content": content}
            if image_parts:
                ollama_msg["images"] = [
                    base64.b64encode(p.data).decode("ascii") for p in image_parts
                ]
            result.append(ollama_msg)

    return result
```

No changes needed to `OllamaProvider.chat()` or `OllamaProvider.stream()` — the serialiser is the only touch point.

---

## FR-3 — Vision serialisation in the Anthropic provider *(important)*

### Problem

`providers/anthropic.py` will encounter `ImagePart` once FR-1 lands and must not silently drop it either. The Anthropic Messages API accepts images as:

```json
{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "<base64>"}}
```

### Proposed change — `norreroute/providers/anthropic.py`

In the function that serialises message content parts to Anthropic format, add an `ImagePart` branch:

```python
elif isinstance(part, ImagePart):
    out.append({
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": part.media_type,
            "data": base64.b64encode(part.data).decode("ascii"),
        },
    })
```

---

## FR-4 — Unsupported-capability guard *(nice-to-have)*

### Problem

If a caller uses `ImagePart` with a provider or model that does not support vision (e.g. pointing imagerec at `llama3.2` instead of `llava`), the failure today is an opaque HTTP 400/422 from the provider. There is no pre-flight check and no typed error that the caller can distinguish from a network failure.

### Proposed change

**`norreroute/errors.py`** — add one new error class:

```python
class UnsupportedCapabilityError(AIProxyError):
    """Raised when a ChatRequest uses a feature the provider does not support.

    Args:
        capability: The unsupported capability name (e.g. ``"vision"``).
        provider: The provider name.
    """

    def __init__(self, capability: str, *, provider: str) -> None:
        super().__init__(
            f"Provider '{provider}' does not support capability '{capability}'"
        )
        self.capability = capability
        self.provider = provider
```

**`norreroute/client.py`** — validate before dispatch in `chat()` / `stream()`:

```python
def _validate_request(self, request: ChatRequest) -> None:
    """Raise UnsupportedCapabilityError if the request uses unsupported features."""
    from .types import ImagePart
    has_images = any(
        isinstance(part, ImagePart)
        for msg in request.messages
        for part in msg.content
    )
    if has_images and not getattr(self._provider, "supports_vision", True):
        from .errors import UnsupportedCapabilityError
        raise UnsupportedCapabilityError("vision", provider=self._provider.name)
```

**Provider implementations** — add a class-level attribute (default `True` for backward compatibility):

```python
class OllamaProvider:
    name = "ollama"
    supports_vision = True   # Ollama vision models accept images

class AnthropicProvider:
    name = "anthropic"
    supports_vision = True   # Claude 3+ supports vision
```

Export from `__init__.py`:

```python
from .errors import ..., UnsupportedCapabilityError
__all__ = [..., "UnsupportedCapabilityError"]
```

---

## FR-5 — `ChatResponse.text` convenience property *(nice-to-have)*

### Problem

After `client.chat_sync(request)`, extracting the model's text reply requires:

```python
text = next(p.text for p in response.content if isinstance(p, TextPart))
```

For callers like imagerec that only care about the text reply (no tool use), this is boilerplate at every call site.

### Proposed change — `norreroute/types.py`

Add a computed property to `ChatResponse`:

```python
@dataclass(frozen=True)
class ChatResponse:
    ...

    @property
    def text(self) -> str:
        """Return the concatenated text of all TextPart content blocks.

        Returns an empty string if the response contains no TextPart
        (e.g. a pure tool-use response).
        """
        return "".join(p.text for p in self.content if isinstance(p, TextPart))
```

> Note: `frozen=True` dataclasses support `@property` without issue.

---

## FR-6 — `Message.user()` convenience constructor *(nice-to-have)*

### Problem

Assembling a user message with both text and images requires:

```python
Message(role="user", content=[TextPart(text=prompt), ImagePart(data=jpeg_bytes)])
```

At 2–10 Hz (imagerec's inference cadence), this is noisy and allocates two extra intermediate lists per frame.

### Proposed change — `norreroute/types.py`

Add a classmethod to `Message`:

```python
@dataclass(frozen=True)
class Message:
    role: Role
    content: Sequence[ContentPart]

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

---

## Summary table

| # | Title | Priority | Files changed |
|---|---|---|---|
| FR-1 | `ImagePart` content type | **Blocker** | `types.py`, `__init__.py` |
| FR-2 | Ollama vision serialisation | **Blocker** | `providers/ollama.py` |
| FR-3 | Anthropic vision serialisation | Important | `providers/anthropic.py` |
| FR-4 | Unsupported-capability guard | Nice-to-have | `errors.py`, `client.py`, provider files |
| FR-5 | `ChatResponse.text` property | Nice-to-have | `types.py` |
| FR-6 | `Message.user()` constructor | Nice-to-have | `types.py` |

---

## What the migrated imagerec call site looks like

Once FR-1, FR-2, and FR-5 land, `src/ollama_client.py` shrinks to:

```python
import cv2
import numpy as np
from norreroute import Client
from norreroute.types import ChatRequest, Message, ImagePart
from norreroute.errors import ProviderError

OllamaError = ProviderError   # preserves the single `except` in inference_worker.py


class OllamaVisionClient:
    def __init__(
        self,
        url: str,
        model: str,
        timeout_s: float,
        prompt: str,
        jpeg_quality: int,
    ) -> None:
        self._client = Client(provider="ollama", base_url=url, timeout_s=timeout_s)
        self._model = model
        self._prompt = prompt
        self._jpeg_quality = jpeg_quality

    def describe(self, frame: np.ndarray) -> str:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality])
        if not ok:
            raise OllamaError("cv2.imencode failed — could not encode frame as JPEG")

        request = ChatRequest(
            model=self._model,
            messages=[
                Message.user(self._prompt, images=[buf.tobytes()])  # requires FR-2 + FR-6
            ],
        )
        response = self._client.chat_sync(request)  # raises ProviderError on failure
        return response.text.strip()                # requires FR-5
```

`camera.py`, `inference_worker.py`, `overlay.py`, `app.py`, and `config.py` are **unchanged**. The migration is contained entirely within `ollama_client.py`.

---

## Suggested test cases for norreroute

```python
# tests/test_vision.py

def test_image_part_roundtrip():
    """ImagePart preserves bytes and media_type."""
    data = b"\xff\xd8\xff"  # JPEG magic bytes
    part = ImagePart(data=data, media_type="image/jpeg")
    assert part.data == data
    assert part.type == "image"


def test_ollama_serialiser_includes_images():
    """_messages_to_ollama encodes ImagePart as base64 in the images field."""
    import base64
    from norreroute.providers.ollama import _messages_to_ollama
    from norreroute.types import ChatRequest, Message, TextPart, ImagePart

    jpeg = b"\xff\xd8\xff\xe0"
    request = ChatRequest(
        model="llava",
        messages=[
            Message(role="user", content=[
                TextPart(text="What is this?"),
                ImagePart(data=jpeg),
            ])
        ],
    )
    serialised = _messages_to_ollama(request)
    assert len(serialised) == 1
    assert serialised[0]["images"] == [base64.b64encode(jpeg).decode("ascii")]
    assert serialised[0]["content"] == "What is this?"


def test_chat_response_text_property():
    """ChatResponse.text concatenates all TextPart content."""
    from norreroute.types import ChatResponse, TextPart, Usage

    response = ChatResponse(
        model="llava",
        content=[TextPart(text="A cat.")],
        finish_reason="stop",
        usage=Usage(input_tokens=10, output_tokens=3),
        raw={},
    )
    assert response.text == "A cat."


def test_message_user_convenience():
    """Message.user() builds role='user' with TextPart + ImagePart."""
    msg = Message.user("describe this", images=[b"\xff\xd8"])
    assert msg.role == "user"
    assert isinstance(msg.content[0], TextPart)
    assert isinstance(msg.content[1], ImagePart)
```
