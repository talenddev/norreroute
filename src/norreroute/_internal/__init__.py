"""Private internal helpers — not part of the public API."""

from __future__ import annotations

import random


def full_jitter(
    initial_delay: float, multiplier: float, max_delay: float, attempt: int
) -> float:
    """Compute AWS-style full-jitter delay.

    Formula: uniform(0, min(max_delay, initial_delay * multiplier**attempt))

    Args:
        initial_delay: Base delay in seconds.
        multiplier: Exponential backoff multiplier.
        max_delay: Maximum cap on the delay before jitter.
        attempt: Zero-based attempt number (0 = first retry).

    Returns:
        A randomised delay in seconds.
    """
    cap = min(max_delay, initial_delay * (multiplier**attempt))
    return random.uniform(0, cap)


__all__ = ["full_jitter"]
