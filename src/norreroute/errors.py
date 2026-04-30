"""Error hierarchy for aiproxy."""

from __future__ import annotations

from typing import Any


class AIProxyError(Exception):
    """Base exception for all aiproxy errors."""


class ConfigurationError(AIProxyError):
    """Raised when provider configuration is invalid or missing."""


class ProviderError(AIProxyError):
    """Raised when a provider returns an error response."""

    def __init__(
        self,
        msg: str,
        *,
        provider: str,
        status: int | None = None,
        raw: Any = None,
    ) -> None:
        super().__init__(msg)
        self.provider = provider
        self.status = status
        self.raw = raw


class RateLimitError(ProviderError):
    """Raised when the provider returns a rate-limit (429) response."""


class AuthenticationError(ProviderError):
    """Raised when the provider returns an authentication failure (401/403)."""


class TimeoutError_(ProviderError):
    """Raised when a provider request times out.

    Named with a trailing underscore to avoid shadowing the built-in TimeoutError.
    """


class ToolArgumentError(AIProxyError):
    """Raised when a tool receives invalid arguments."""


class UnknownModelError(AIProxyError):
    """Raised when a model name cannot be resolved to a pricing entry."""


class JSONValidationError(AIProxyError):
    """Raised when a JSON response cannot be parsed or coerced to the target type."""


class ConversationOverflowError(AIProxyError):
    """Raised when a Conversation cannot trim its history to fit the token budget."""


__all__ = [
    "AIProxyError",
    "ConfigurationError",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "TimeoutError_",
    "ToolArgumentError",
    "UnknownModelError",
    "JSONValidationError",
    "ConversationOverflowError",
]
