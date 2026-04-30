"""Tests for aiproxy.registry."""

from __future__ import annotations

import pytest

import norreroute.registry as registry_module
from norreroute.registry import register, resolve
from norreroute.types import ChatRequest, ChatResponse, TextPart, Usage

# ---------------------------------------------------------------------------
# Minimal stub provider for registry tests
# ---------------------------------------------------------------------------


class _StubProvider:
    """Minimal provider stub satisfying the Provider protocol for registry tests."""

    name = "stub"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            model=request.model,
            content=[TextPart(text="stub")],
            finish_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
            raw={},
        )

    async def aclose(self) -> None:
        pass

    async def _stream_impl(self, request: ChatRequest):  # type: ignore[override]
        yield  # pragma: no cover

    def stream(self, request: ChatRequest):  # type: ignore[override]
        return self._stream_impl(request)


def _stub_factory(**kwargs: object) -> _StubProvider:
    return _StubProvider()


# ---------------------------------------------------------------------------
# Fixture: reset _FACTORIES before each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_factories() -> None:
    """Isolate registry state between tests."""
    original = dict(registry_module._FACTORIES)
    registry_module._FACTORIES.clear()
    yield
    registry_module._FACTORIES.clear()
    registry_module._FACTORIES.update(original)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_then_resolve() -> None:
    register("stub", _stub_factory)
    provider = resolve("stub")
    assert provider.name == "stub"


def test_resolve_unknown_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown provider"):
        resolve("does_not_exist")


def test_register_overwrites_existing() -> None:
    register("stub", _stub_factory)

    class _AltProvider(_StubProvider):
        name = "stub_alt"

    register("stub", lambda **kw: _AltProvider())
    provider = resolve("stub")
    assert provider.name == "stub_alt"


def test_resolve_passes_kwargs_to_factory() -> None:
    received_kwargs: dict[str, object] = {}

    def _capturing_factory(**kwargs: object) -> _StubProvider:
        received_kwargs.update(kwargs)
        return _StubProvider()

    register("stub", _capturing_factory)
    resolve("stub", api_key="key123", timeout_s=30.0)
    assert received_kwargs == {"api_key": "key123", "timeout_s": 30.0}


def test_multiple_providers_coexist() -> None:
    register("a", _stub_factory)
    register("b", _stub_factory)
    assert resolve("a").name == "stub"
    assert resolve("b").name == "stub"
