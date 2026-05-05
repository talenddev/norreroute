# Vision / Multimodal Support — Tech Lead Brief

**Source request:** `docs/norreroute-vision-feature-request.md`
**Target version:** next minor (0.3.0 — additive feature, no breaking changes)
**Branch:** cut feature branches from `develop`

---

## 1. Architecture assessment

The proposed design is sound and consistent with the existing codebase conventions (frozen dataclasses, provider-side serialisation, no Pydantic on the wire types). Adopt as-is with the following observations and corrections.

### Strengths
- `ImagePart` carries raw `bytes`. Correct — keeps base64 as a provider serialisation detail. Matches the project's "providers own their wire format" pattern already used for `ToolUsePart` / `ToolResultPart`.
- No changes to `Provider` Protocol or `Client` public surface required (FR-1 to FR-3, FR-5, FR-6 are purely additive).
- Symmetry between Ollama (`images: [b64...]` flat field) and Anthropic (`{"type":"image","source":{...}}` blocks) is correctly captured in two distinct serialiser branches — no leaky abstraction.

### Risks and gaps to address
1. **Retry wrapper hides `supports_vision` (FR-4 bug).** `RetryingProvider` (`src/norreroute/retry.py`) only forwards `name`. When `Client.__init__` wraps a provider with `RetryingProvider`, `self._provider.supports_vision` will not exist on the wrapper — `getattr(..., True)` falls through to `True` and the guard becomes a no-op when retry is enabled. **Fix:** `RetryingProvider` must forward `supports_vision` from `inner` (mirroring how `name` is forwarded).
2. **Anthropic flatten-to-string short-circuit (`_messages_to_anthropic`).** The current implementation collapses a single text block into a plain string. After adding `ImagePart`, the flatten branch is still safe (only triggered when `len(content_blocks) == 1` and type is `text`), but the developer must verify the new branch produces a `dict` block, not a string. Add a regression test for "single image, no text" and "text + image" message shapes.
3. **`ChatRequest.system` already exists.** `Message.system()` (FR-6) is fine to add for parity, but document that callers using Anthropic should prefer `ChatRequest(system=...)` to avoid double-system-message ambiguity. No code change needed — just a docstring note.
4. **Token / payload size.** A JPEG frame at 720p is ~80–200 KB. With retries enabled, the entire request body (including base64 image) is held in memory per attempt. This is acceptable for the imagerec use case (single client, single frame at a time), but flag it: do **not** add request-body retention for tracing/logging without a size guard. Audit `tracing.py` to confirm it does not log message bodies (it currently does not — keep it that way).
5. **Streaming with images.** The Ollama and Anthropic streaming code paths reuse `_messages_to_*`, so streaming "just works" once the serialisers are updated. Add one streaming test per provider with an `ImagePart` to lock this in.
6. **mypy strict mode.** `ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart` widens the union. The Ollama serialiser currently has an implicit `else` that handles "no special parts" — verify mypy still passes after the union grows. The Anthropic serialiser's bare `else: # ToolResultPart` comment becomes a lie once `ImagePart` exists; replace with explicit `isinstance(part, ToolResultPart)` and an `else: raise TypeError(...)` to keep exhaustiveness checked.
7. **`__init__.py` exports.** The current `__init__.py` does **not** re-export the wire types (`TextPart`, `Message`, `ChatRequest`, etc.) — callers import them from `norreroute.types`. Stay consistent: export `ImagePart` from `norreroute.types` only. Do **not** add it to top-level `norreroute.__all__` unless we also add the others (out of scope here). The feature request's "Export `ImagePart` from `__init__.py`" instruction is a deviation from current style — flag and skip. Same applies to `UnsupportedCapabilityError`: it should be exported from `norreroute.errors` (already done by `__all__` there) and added to top-level `__init__.py` only if we want it in the public surface — yes, do that, since the other error classes (`ConversationOverflowError`, `JSONValidationError`, `UnknownModelError`) are exported from top-level.

### Deviations recommended

| # | Deviation | Rationale |
|---|---|---|
| D-1 | Do not export `ImagePart` from top-level `norreroute/__init__.py`. | Existing wire types are not exported there either; keep imports as `from norreroute.types import ImagePart`. Consistency over convenience. |
| D-2 | **Do** export `UnsupportedCapabilityError` from top-level `__init__.py`. | All other custom error classes are exported there; keep the error surface consistent. |
| D-3 | `RetryingProvider` must forward `supports_vision` from inner provider. | Without this, FR-4 silently breaks when `retry=True`. |
| D-4 | Replace Anthropic serialiser's `else` (currently labelled `# ToolResultPart`) with explicit `isinstance` + final `else: raise TypeError`. | Defensive programming for the widened union; keeps mypy strict-friendly. |
| D-5 | `Message.user(text="", *, images=())` accepts `Sequence[bytes]` only — do **not** also accept pre-built `ImagePart` instances in this constructor. | YAGNI; if a caller has already built `ImagePart`, they can pass `Message(role="user", content=[...])` directly. Keeps `Message.user` signature small. |
| D-6 | Bump version to **0.3.0**, not 0.2.2. | Adds new public type (`ImagePart`), new error class, new convenience methods. SemVer minor bump. |

---

## 2. Sequencing

```
FR-1 (ImagePart type)
   ├── unblocks ─▶ FR-2 (Ollama serialiser)
   ├── unblocks ─▶ FR-3 (Anthropic serialiser)
   ├── unblocks ─▶ FR-4 (capability guard)
   └── unblocks ─▶ FR-6 (Message.user/system)

FR-5 (ChatResponse.text) — independent, can land any time.
```

Recommended PR layout (one PR per task, all into `develop`):

1. **PR-1** `feature/TASK-1-image-part-type` — FR-1 + FR-5 + FR-6 (pure type additions, no provider changes). Ships fast, low risk.
2. **PR-2** `feature/TASK-2-ollama-vision` — FR-2 (depends on PR-1).
3. **PR-3** `feature/TASK-3-anthropic-vision` — FR-3 (depends on PR-1).
4. **PR-4** `feature/TASK-4-capability-guard` — FR-4 + retry forwarding fix (depends on PR-1, PR-2, PR-3).

PR-2 and PR-3 can run in parallel.

---

## 3. Developer task list

### TASK-1 — Add `ImagePart`, `ChatResponse.text`, `Message.user/system`

**Branch:** `feature/TASK-1-image-part-type`
**Files:**
- `src/norreroute/types.py`

**Steps:**
1. Add `ImagePart` frozen dataclass after `TextPart`:
   ```python
   @dataclass(frozen=True)
   class ImagePart:
       data: bytes
       media_type: str = "image/jpeg"
       type: Literal["image"] = "image"
   ```
2. Extend the union: `ContentPart = TextPart | ImagePart | ToolUsePart | ToolResultPart`.
3. Add `text` property to `ChatResponse`:
   ```python
   @property
   def text(self) -> str:
       return "".join(p.text for p in self.content if isinstance(p, TextPart))
   ```
4. Add `Message.user` and `Message.system` classmethods per FR-6 (signature: `user(text: str = "", *, images: Sequence[bytes] = ()) -> Message`; `system(text: str) -> Message`). `images` accepts `bytes` only — do not also accept `ImagePart` (D-5).
5. Append `"ImagePart"` to `__all__` in `types.py`. **Do not** modify top-level `norreroute/__init__.py` (D-1).

**Acceptance criteria:**
- `from norreroute.types import ImagePart` works.
- `ImagePart(data=b"\xff\xd8")` is hashable and frozen.
- `ChatResponse(...).text` returns concatenated text, `""` when only tool-use parts.
- `Message.user("hi", images=[b"\xff\xd8"]).content` is `[TextPart("hi"), ImagePart(b"\xff\xd8")]`.
- `Message.user(images=[b"x"]).content` has no `TextPart` (skipped when empty).
- `Message.system("be brief").content == [TextPart("be brief")]`.
- `mypy --strict` passes.
- `ruff check` passes.

---

### TASK-2 — Ollama vision serialisation

**Branch:** `feature/TASK-2-ollama-vision`
**Depends on:** TASK-1
**Files:**
- `src/norreroute/providers/ollama.py`

**Steps:**
1. Add `import base64` at module top.
2. Add `ImagePart` to the `from norreroute.types import (...)` group.
3. In `_messages_to_ollama`, collect `image_parts = [p for p in msg.content if isinstance(p, ImagePart)]` alongside the existing `text_parts` / tool collections.
4. In the **non-tool** branch (the existing `else:` arm that builds `{"role": ..., "content": ...}`), if `image_parts` is non-empty, attach `ollama_msg["images"] = [base64.b64encode(p.data).decode("ascii") for p in image_parts]` before appending.
5. Decision: images are **only** forwarded in the non-tool branch. If a caller mixes `ImagePart` with `ToolUsePart` or `ToolResultPart` in the same `Message`, the image is dropped. Document this with a comment — it is the same semantics as text being dropped on a tool-result message today.

**Acceptance criteria:**
- A `ChatRequest` with `Message(role="user", content=[TextPart("?"), ImagePart(b"\xff\xd8")])` produces an Ollama dict whose `"images"` is a 1-element list of base64 strings, `"content"` is `"?"`.
- A `ChatRequest` with image-only message (no `TextPart`) produces `"content": ""` and the `"images"` field populated.
- Existing text-only and tool-call tests still pass.
- `mypy --strict` passes.

---

### TASK-3 — Anthropic vision serialisation

**Branch:** `feature/TASK-3-anthropic-vision`
**Depends on:** TASK-1
**Files:**
- `src/norreroute/providers/anthropic.py`

**Steps:**
1. Add `import base64` at module top.
2. Add `ImagePart` to the `from norreroute.types import (...)` group.
3. In `_messages_to_anthropic`, replace the bare `else: # ToolResultPart` with an explicit chain:
   ```python
   elif isinstance(part, ImagePart):
       content_blocks.append({
           "type": "image",
           "source": {
               "type": "base64",
               "media_type": part.media_type,
               "data": base64.b64encode(part.data).decode("ascii"),
           },
       })
   elif isinstance(part, ToolResultPart):
       content_blocks.append({...})  # existing body
   else:
       raise TypeError(f"Unsupported content part type: {type(part).__name__}")
   ```
4. Confirm the "flatten to string" short-circuit (`if len(content_blocks) == 1 and content_blocks[0]["type"] == "text":`) still behaves correctly — image-only messages must **not** be flattened (they will not be: their type is `"image"`, not `"text"`).

**Acceptance criteria:**
- `ImagePart(data=b"\xff\xd8", media_type="image/png")` serialises to `{"type":"image","source":{"type":"base64","media_type":"image/png","data":"<b64>"}}`.
- Existing text-only flatten path still produces a plain string content.
- Mixed text + image produces a list of two blocks (no flatten).
- `mypy --strict` passes.

---

### TASK-4 — Unsupported-capability guard + retry forwarding

**Branch:** `feature/TASK-4-capability-guard`
**Depends on:** TASK-1, TASK-2, TASK-3
**Files:**
- `src/norreroute/errors.py`
- `src/norreroute/client.py`
- `src/norreroute/retry.py`
- `src/norreroute/providers/ollama.py`
- `src/norreroute/providers/anthropic.py`
- `src/norreroute/__init__.py`

**Steps:**
1. **`errors.py`** — add `UnsupportedCapabilityError(AIProxyError)` per FR-4. Append to `__all__`.
2. **Provider classes** — add class attribute `supports_vision: bool = True` to `OllamaProvider` and `AnthropicProvider`.
3. **`retry.py`** — in `RetryingProvider.__init__`, forward the attribute:
   ```python
   self.supports_vision: bool = getattr(inner, "supports_vision", True)
   ```
   (Mirror the existing `self.name` line.)
4. **`client.py`** — add `_validate_request` method (private), call it as the first line of both `chat()` and `stream()` (and ensure `chat_sync` / `stream_sync` benefit transitively — they already delegate). The guard must inspect `self._provider.supports_vision`, which now works whether `_provider` is a raw provider or a `RetryingProvider`.
5. **`__init__.py`** — add `UnsupportedCapabilityError` to the `from .errors import (...)` block and to `__all__` (D-2).

**Acceptance criteria:**
- A `Client` with a stub provider declaring `supports_vision = False` raises `UnsupportedCapabilityError` on `chat()`/`stream()` when the request contains any `ImagePart`.
- The same Client raises **before** any HTTP call is made (assert no httpx mock invocations).
- The guard is a no-op when no `ImagePart` is present.
- The guard works correctly with `retry=True` (i.e. `RetryingProvider` propagates `supports_vision`).
- `from norreroute import UnsupportedCapabilityError` works.

---

## 4. Tester task list

Use `pytest`. Tests go in `tests/` (mirror existing layout). `respx` is available for HTTP mocking. Keep tests fast — no real network.

### Test group A — Types (covers TASK-1)
**File:** `tests/test_vision_types.py`

- `test_image_part_is_frozen_and_typed` — assert `frozen=True` (mutation raises), `type == "image"`, default `media_type == "image/jpeg"`.
- `test_image_part_preserves_bytes` — round-trip raw bytes through the dataclass.
- `test_chat_response_text_concatenates_text_parts` — multiple `TextPart`s concatenate in order.
- `test_chat_response_text_empty_when_only_tool_use` — pure tool-use response → `text == ""`.
- `test_message_user_text_only` — no images.
- `test_message_user_images_only` — empty text omits `TextPart`.
- `test_message_user_text_and_images` — order is `[TextPart, ImagePart, ImagePart, ...]`.
- `test_message_system_single_text_part` — role `system`, one `TextPart`.

### Test group B — Ollama serialiser (covers TASK-2)
**File:** `tests/test_ollama_vision.py`

- `test_ollama_serialiser_includes_base64_images` — verifies `images` field equals the base64 of the input bytes; `content` carries text.
- `test_ollama_serialiser_image_only_message` — `content == ""`, `images` populated.
- `test_ollama_serialiser_no_images_unchanged` — regression: a request without `ImagePart` produces no `images` key.
- `test_ollama_serialiser_multiple_messages_with_images` — two user turns, each with one image; both serialised independently.
- `test_ollama_chat_with_image_e2e` — uses `respx` to mock `/api/chat`, sends a request with an image, asserts the request body posted to Ollama contains `images` with the expected base64 payload.
- `test_ollama_stream_with_image` — `respx` mock of streaming `/api/chat`; verify request body includes `images` (just the request shape, no need to test response parsing here).

### Test group C — Anthropic serialiser (covers TASK-3)
**File:** `tests/test_anthropic_vision.py`

- `test_anthropic_serialiser_image_block_shape` — single `ImagePart` produces the exact `{"type":"image","source":{...}}` dict.
- `test_anthropic_serialiser_text_and_image_no_flatten` — multi-block message is **not** flattened to string.
- `test_anthropic_serialiser_text_only_still_flattens` — regression: single `TextPart` still produces plain string content.
- `test_anthropic_serialiser_unknown_part_raises_type_error` — defensive: passing an unrecognised dataclass (constructed via a stub) raises `TypeError`.
- `test_anthropic_chat_with_image_e2e` — mock the `anthropic` SDK (via `pytest-mock`); assert the message dict passed to `messages.create` contains the image block.

### Test group D — Capability guard (covers TASK-4)
**File:** `tests/test_capability_guard.py`

- `test_unsupported_capability_error_fields` — `capability == "vision"`, `provider == "stubprov"`, message contains both.
- `test_client_raises_when_provider_lacks_vision` — stub provider with `supports_vision = False`; sending a request with `ImagePart` raises `UnsupportedCapabilityError`. Assert no provider HTTP method was called (use a spy / `pytest-mock`).
- `test_client_passes_through_when_no_image_part` — same stub with `supports_vision = False`; request without `ImagePart` is forwarded normally.
- `test_client_passes_through_when_provider_supports_vision` — stub with `supports_vision = True`; request with `ImagePart` is forwarded normally.
- `test_capability_guard_works_through_retry_wrapper` — `Client(provider=stub, retry=True)` where stub has `supports_vision = False`; assert `RetryingProvider.supports_vision` is `False` and the guard still fires.
- `test_default_supports_vision_true_for_unknown_attribute` — provider without the attribute defaults to `True` (backward compat).
- `test_unsupported_capability_error_exported_from_top_level` — `from norreroute import UnsupportedCapabilityError` works.

### Linting / typing
- `ruff check src tests` must pass.
- `mypy --strict` must pass on `src/norreroute`.
- `pytest --cov` — coverage must not regress on touched files.

---

## 5. Out of scope (YAGNI — do not build)

- URL-based images (`ImagePart` accepts only `bytes`). If a caller has a URL, they fetch it. Re-evaluate when a real use case appears.
- Image input on additional providers (OpenAI, Gemini, etc.) — only Ollama and Anthropic are in the codebase today.
- Image **output** from models (image generation). Different problem entirely.
- Per-model capability checks (e.g. "is `llama3.2` a vision model?"). Provider-level `supports_vision` is enough until a caller hits a real mismatch.
- Streaming-specific image handling beyond verifying request serialisation. Output is still text deltas.
- Auto-resizing / re-encoding images. Caller's responsibility.
- A `capabilities` registry or capability-negotiation API. One boolean per provider until we have three or more capability axes.

---

## 6. Release note draft (for CHANGELOG)

```
## 0.3.0

### Added
- `ImagePart` content type for multimodal (vision) requests.
- `ChatResponse.text` convenience property — concatenates all TextPart blocks.
- `Message.user(text, *, images=...)` and `Message.system(text)` classmethods.
- `UnsupportedCapabilityError` raised pre-flight when a request targets a
  provider that lacks the required capability (e.g. vision).
- Vision payload serialisation for Ollama (`images` field) and Anthropic
  (`{"type":"image","source":{"type":"base64",...}}` blocks).

### Changed
- `RetryingProvider` now forwards `supports_vision` from the wrapped provider.

No breaking changes.
```

---

## Handoff

```
ARCHITECTURE BRIEF
─────────────────────────────────────
Brief saved to: docs/vision-feature-brief.md
Tasks: TASK-1, TASK-2, TASK-3, TASK-4 (one PR each into develop)
Sequence: TASK-1 first; TASK-2 and TASK-3 parallel; TASK-4 last
Deviations from FR: D-1..D-6 (see §1)
First milestone: TASK-1 merged — unblocks downstream and ships the new types
─────────────────────────────────────
DO NOT build: URL images, OpenAI/Gemini providers, image generation,
per-model capability checks, capability registry, image resizing.
```
