"""Token counting and cost estimation utilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .errors import UnknownModelError
from .types import ChatRequest, ChatResponse, TextPart


@dataclass(frozen=True)
class ModelPrice:
    """Per-model pricing expressed in USD per million tokens.

    Attributes:
        input_per_mtok_usd: Cost of input (prompt) tokens per million.
        output_per_mtok_usd: Cost of output (completion) tokens per million.
    """

    input_per_mtok_usd: float
    output_per_mtok_usd: float


@dataclass(frozen=True)
class CostEstimate:
    """Result of a cost estimation for a single chat completion.

    Attributes:
        model: The model name from the response.
        input_tokens: Number of input tokens used (or estimated).
        output_tokens: Number of output tokens used (or estimated).
        input_cost_usd: Dollar cost for input tokens.
        output_cost_usd: Dollar cost for output tokens.
        total_cost_usd: Sum of input and output costs.
        is_estimate: True when token counts were approximated (no usage data).
    """

    model: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    is_estimate: bool


def _resolve_price(
    model: str,
    pricing: Mapping[str, ModelPrice] | None,
) -> ModelPrice:
    """Resolve pricing for a model name.

    Lookup order:
    1. Explicit ``pricing`` argument (if provided).
    2. Built-in ``MODEL_PRICING`` table.
    3. Prefix-match fallback (e.g. "llama3.1:latest" → "llama3.1").
    4. ``UnknownModelError`` if nothing matches.

    Args:
        model: The model name to look up.
        pricing: Optional caller-supplied pricing table.

    Returns:
        The resolved ModelPrice.

    Raises:
        UnknownModelError: When no pricing entry can be found for ``model``.
    """
    # Explicit caller table takes precedence
    if pricing is not None:
        if model in pricing:
            return pricing[model]
        # Prefix match in caller table
        for key, price in pricing.items():
            if model.startswith(key):
                return price

    # Fall back to built-in table (late import to avoid circular deps)
    from .pricing_data import MODEL_PRICING  # noqa: PLC0415

    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Prefix match in built-in table
    for key, price in MODEL_PRICING.items():
        if model.startswith(key):
            return price

    raise UnknownModelError(
        f"No pricing found for model {model!r}. "
        "Pass an explicit `pricing` dict or add it to MODEL_PRICING."
    )


def count_tokens_approx(request: ChatRequest) -> int:
    """Estimate token count for a request using a char/4 heuristic.

    This is a rough approximation suitable for pre-flight budgeting only.
    It is NOT a real tokeniser.

    Args:
        request: The chat request to estimate tokens for.

    Returns:
        Approximate number of tokens (floor of total characters / 4).
    """
    total_chars = 0
    if request.system:
        total_chars += len(request.system)
    for msg in request.messages:
        for part in msg.content:
            if isinstance(part, TextPart):
                total_chars += len(part.text)
    return total_chars // 4


def estimate_cost(
    response: ChatResponse,
    pricing: Mapping[str, ModelPrice] | None = None,
    *,
    request: ChatRequest | None = None,
) -> CostEstimate:
    """Compute the cost of a completed chat response.

    Token counts are taken from ``response.usage`` when available.
    If usage is absent (tokens == 0 and no usage data), the function falls
    back to ``count_tokens_approx`` on the original request (if supplied)
    and sets ``is_estimate=True``.

    Args:
        response: The completed chat response.
        pricing: Optional caller-supplied pricing table (overrides MODEL_PRICING).
        request: Optional original request used for token approximation when
                 usage data is unavailable.

    Returns:
        A CostEstimate with full cost breakdown.

    Raises:
        UnknownModelError: When no pricing entry exists for the response model.
    """
    price = _resolve_price(response.model, pricing)

    usage = response.usage
    is_estimate = False

    if usage is not None and (usage.input_tokens > 0 or usage.output_tokens > 0):
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
    else:
        # Fall back to approximation
        is_estimate = True
        input_tokens = count_tokens_approx(request) if request is not None else 0
        output_tokens = 0

    input_cost = input_tokens / 1_000_000 * price.input_per_mtok_usd
    output_cost = output_tokens / 1_000_000 * price.output_per_mtok_usd

    return CostEstimate(
        model=response.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
        is_estimate=is_estimate,
    )


__all__ = [
    "ModelPrice",
    "CostEstimate",
    "estimate_cost",
    "count_tokens_approx",
]
