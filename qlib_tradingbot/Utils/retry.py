"""Utils/retry.py

Small, dependency-free retry helper with exponential backoff + jitter.

Design goals:
- Works offline / in pytest (no network calls during import).
- Keeps call sites clean.
- Retries only on known-transient errors.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Type, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_s: float = 0.4
    max_delay_s: float = 8.0
    jitter_s: float = 0.2


def call_with_retries(
    fn: Callable[[], T],
    *,
    retry_on: Sequence[Type[BaseException]],
    policy: RetryPolicy = RetryPolicy(),
    on_retry: Optional[Callable[[int, BaseException, float], None]] = None,
) -> T:
    """Call `fn()` with retries.

    Args:
        fn: Zero-arg callable.
        retry_on: Exception types to retry.
        policy: RetryPolicy.
        on_retry: Callback(attempt, exc, sleep_s).
    """
    attempt = 1
    while True:
        try:
            return fn()
        except tuple(retry_on) as e:
            if attempt >= int(policy.max_attempts):
                raise
            backoff = min(policy.max_delay_s, policy.base_delay_s * (2 ** (attempt - 1)))
            sleep_s = max(0.0, float(backoff) + random.uniform(0.0, float(policy.jitter_s)))
            if on_retry is not None:
                try:
                    on_retry(attempt, e, sleep_s)
                except Exception:
                    pass
            time.sleep(sleep_s)
            attempt += 1
