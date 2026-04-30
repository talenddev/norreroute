"""norreroute — a pragmatic, provider-agnostic Python library for calling LLMs."""

from __future__ import annotations

from . import providers as _providers  # noqa: F401 — triggers self-registration
from .client import Client
from .retry import RetryingProvider, RetryPolicy

__version__ = "0.2.0"

__all__ = [
    "Client",
    "RetryPolicy",
    "RetryingProvider",
    "__version__",
]
