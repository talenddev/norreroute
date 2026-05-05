"""norreroute — a pragmatic, provider-agnostic Python library for calling LLMs."""

from __future__ import annotations

from . import providers as _providers  # noqa: F401 — triggers self-registration
from .client import Client
from .conversation import Conversation, TrimStrategy
from .errors import (
    ConversationOverflowError,
    JSONValidationError,
    UnknownModelError,
    UnsupportedCapabilityError,
)
from .json_mode import json_chat
from .pricing import CostEstimate, ModelPrice, count_tokens_approx, estimate_cost
from .retry import RetryingProvider, RetryPolicy

__version__ = "0.3.0"

__all__ = [
    "Client",
    "Conversation",
    "TrimStrategy",
    "RetryPolicy",
    "RetryingProvider",
    "ModelPrice",
    "CostEstimate",
    "estimate_cost",
    "count_tokens_approx",
    "UnknownModelError",
    "JSONValidationError",
    "ConversationOverflowError",
    "UnsupportedCapabilityError",
    "json_chat",
    "__version__",
]
