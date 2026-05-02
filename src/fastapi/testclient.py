from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, get_type_hints

from pydantic import BaseModel

from .app import FastAPI, HTTPException, QueryValue
from .responses import HTMLResponse


@dataclass
class _Response:
    status_code: int
    _body: Any
    text: str

    def json(self) -> Any:
        return self._body


class TestClient:
    __test__ = False

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def get(self, path: str, params: dict[str, Any] | None = None) -> _Response:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> _Response:
        return self._request("POST", path, params=params, json_body=json)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> _Response:
        route = next(item for item in self.app.routes if item.method == method and item.path == path)
        kwargs = _build_kwargs(route.endpoint, params=params or {}, json_body=json_body)
        try:
            result = route.endpoint(**kwargs)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
        except HTTPException as exc:
            payload = {"detail": exc.detail}
            return _Response(status_code=exc.status_code, _body=payload, text=str(exc.detail))
        if route.response_class is HTMLResponse:
            return _Response(status_code=200, _body=result, text=str(result))
        return _Response(status_code=200, _body=result, text=str(result))


def _build_kwargs(
    func,
    *,
    params: dict[str, Any],
    json_body: dict[str, Any] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(func)
    type_hints = get_type_hints(func)
    for name, parameter in signature.parameters.items():
        annotation = type_hints.get(name, parameter.annotation)
        if name in params:
            kwargs[name] = _coerce_value(params[name], annotation)
            continue
        if json_body is not None:
            if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
                kwargs[name] = annotation(**json_body)
                continue
            if name in json_body:
                kwargs[name] = _coerce_value(json_body[name], annotation)
                continue
        default = parameter.default
        if isinstance(default, QueryValue):
            if default.default is ...:
                raise TypeError(f"Missing required query parameter: {name}")
            kwargs[name] = default.default
        elif default is not inspect._empty:
            kwargs[name] = default
        else:
            raise TypeError(f"Missing required parameter: {name}")
    return kwargs


def _coerce_value(value: Any, annotation: Any) -> Any:
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation is bool:
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)
    return value
