from __future__ import annotations

from collections.abc import Callable
from typing import Any


def stop_after_attempt(attempts: int) -> int:
    return attempts


def wait_exponential(**_: Any) -> None:
    return None


def retry(*_: Any, **__: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator
