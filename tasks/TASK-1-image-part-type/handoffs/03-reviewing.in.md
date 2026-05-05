# Review Request: TASK-1

## Files to review
- `src/norreroute/types.py`
- `src/norreroute/providers/anthropic.py` (temporary mypy fix in else branch)
- `tests/test_vision_types.py`

## Acceptance criteria
- ImagePart frozen dataclass with data: bytes, media_type: str = "image/jpeg", type: Literal["image"]
- ContentPart union extended with ImagePart
- ChatResponse.text property returns concatenated text parts
- Message.user/system classmethods
- "ImagePart" in __all__, __init__.py NOT modified
- mypy --strict and ruff clean
