from __future__ import annotations

from contextlib import contextmanager


class _Mark:
    def asyncio(self, func):
        return func


mark = _Mark()


@contextmanager
def raises(expected_exception):
    try:
        yield
    except expected_exception:
        return
    except Exception as exc:
        raise AssertionError(f"Expected {expected_exception.__name__}, got {type(exc).__name__}") from exc
    raise AssertionError(f"Expected {expected_exception.__name__} to be raised")
