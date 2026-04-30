"""Tests for aiproxy.errors hierarchy."""

from __future__ import annotations

import pytest

from aiproxy.errors import (
    AIProxyError,
    AuthenticationError,
    ConfigurationError,
    ProviderError,
    RateLimitError,
    TimeoutError_,
    ToolArgumentError,
)


def test_provider_error_attributes() -> None:
    err = ProviderError(
        "something went wrong", provider="anthropic", status=500, raw={"error": "oops"}
    )
    assert str(err) == "something went wrong"
    assert err.provider == "anthropic"
    assert err.status == 500
    assert err.raw == {"error": "oops"}


def test_provider_error_defaults() -> None:
    err = ProviderError("msg", provider="ollama")
    assert err.status is None
    assert err.raw is None


def test_provider_error_is_aiproxy_error() -> None:
    err = ProviderError("msg", provider="x")
    assert isinstance(err, AIProxyError)
    assert isinstance(err, Exception)


def test_rate_limit_error_is_provider_error() -> None:
    err = RateLimitError("rate limited", provider="anthropic", status=429)
    assert isinstance(err, ProviderError)
    assert isinstance(err, AIProxyError)
    assert err.status == 429


def test_authentication_error_is_provider_error() -> None:
    err = AuthenticationError("unauthorized", provider="anthropic", status=401)
    assert isinstance(err, ProviderError)
    assert err.status == 401


def test_timeout_error_is_provider_error() -> None:
    err = TimeoutError_("timed out", provider="ollama")
    assert isinstance(err, ProviderError)
    assert isinstance(err, AIProxyError)


def test_configuration_error_is_aiproxy_error() -> None:
    err = ConfigurationError("missing api_key")
    assert isinstance(err, AIProxyError)


def test_tool_argument_error_is_aiproxy_error() -> None:
    err = ToolArgumentError("bad arg")
    assert isinstance(err, AIProxyError)


def test_raise_provider_error() -> None:
    with pytest.raises(ProviderError) as exc_info:
        raise ProviderError("boom", provider="test", status=503)
    assert exc_info.value.provider == "test"


def test_raise_rate_limit_as_provider_error() -> None:
    with pytest.raises(ProviderError):
        raise RateLimitError("too many", provider="anthropic", status=429)
