"""Provider registry — name to factory mapping."""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points

from .provider import Provider

_FACTORIES: dict[str, Callable[..., Provider]] = {}


def register(name: str, factory: Callable[..., Provider]) -> None:
    """Register a provider factory under the given name.

    Args:
        name: The provider name (e.g. "anthropic", "ollama").
        factory: A callable that accepts keyword arguments and returns a Provider.
    """
    _FACTORIES[name] = factory


def resolve(name: str, **kwargs: object) -> Provider:
    """Resolve a provider by name, loading entry points if needed.

    Args:
        name: The provider name to look up.
        **kwargs: Keyword arguments forwarded to the provider factory.

    Returns:
        An instantiated Provider.

    Raises:
        KeyError: If no provider is registered under the given name.
    """
    if name not in _FACTORIES:
        _load_entry_points()
    if name not in _FACTORIES:
        raise KeyError(f"Unknown provider: {name!r}. Known: {list(_FACTORIES)}")
    return _FACTORIES[name](**kwargs)


def _load_entry_points() -> None:
    """Discover and register providers declared via package entry points."""
    for ep in entry_points(group="norreroute.providers"):
        register(ep.name, ep.load())


__all__ = ["register", "resolve"]
