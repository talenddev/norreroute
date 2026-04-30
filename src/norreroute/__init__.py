"""aiproxy — a pragmatic, provider-agnostic Python library for calling LLMs."""

from __future__ import annotations

from . import providers as _providers  # noqa: F401 — triggers self-registration
from .client import Client

__version__ = "0.1.0"

__all__ = ["Client", "__version__"]
