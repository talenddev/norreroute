"""Static pricing table for known LLM models.

Prices are per million tokens (USD).
Import this module anywhere you need to resolve model costs without
side effects — it contains only pure data.
"""

from __future__ import annotations

from .pricing import ModelPrice

MODEL_PRICING: dict[str, ModelPrice] = {
    # Anthropic
    "claude-3-5-sonnet-20241022": ModelPrice(
        input_per_mtok_usd=3.00,
        output_per_mtok_usd=15.00,
    ),
    "claude-3-5-haiku-20241022": ModelPrice(
        input_per_mtok_usd=0.80,
        output_per_mtok_usd=4.00,
    ),
    "claude-3-opus-20240229": ModelPrice(
        input_per_mtok_usd=15.00,
        output_per_mtok_usd=75.00,
    ),
    # Ollama (local — free)
    "llama3.1": ModelPrice(input_per_mtok_usd=0.0, output_per_mtok_usd=0.0),
    "qwen2.5": ModelPrice(input_per_mtok_usd=0.0, output_per_mtok_usd=0.0),
}

__all__ = ["MODEL_PRICING"]
