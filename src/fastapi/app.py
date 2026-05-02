from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class QueryValue:
    default: Any = ...
    ge: Any = None
    le: Any = None


def Query(default: Any = ..., ge: Any = None, le: Any = None) -> QueryValue:
    return QueryValue(default=default, ge=ge, le=le)


@dataclass
class HTTPException(Exception):
    status_code: int
    detail: Any = None

    def __str__(self) -> str:
        return str(self.detail)


class WebSocketDisconnect(Exception):
    pass


class WebSocket:
    async def accept(self) -> None:
        return None

    async def send_text(self, text: str) -> None:
        return None


@dataclass
class Route:
    method: str
    path: str
    endpoint: Callable[..., Any]
    response_class: Any = None


class FastAPI:
    def __init__(self, title: str, version: str) -> None:
        self.title = title
        self.version = version
        self.routes: list[Route] = []

    def get(self, path: str, response_class: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("GET", path, response_class=response_class)

    def post(self, path: str, response_class: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("POST", path, response_class=response_class)

    def websocket(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return self._add_route("WEBSOCKET", path)

    def _add_route(self, method: str, path: str, response_class: Any = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append(Route(method=method, path=path, endpoint=func, response_class=response_class))
            return func

        return decorator
