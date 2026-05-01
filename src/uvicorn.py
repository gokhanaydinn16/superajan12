from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi.app import QueryValue
from fastapi.responses import HTMLResponse


def run(app_path: str, host: str = "127.0.0.1", port: int = 8000, **_: Any) -> None:
    app = _load_app(app_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return None

        def _handle(self, method: str) -> None:
            parsed = urlparse(self.path)
            route = next((item for item in app.routes if item.method == method and item.path == parsed.path), None)
            if route is None:
                self._send_text(404, "Not Found", "text/plain; charset=utf-8")
                return

            try:
                params = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
                kwargs = _build_kwargs(route.endpoint, params)
                result = route.endpoint(**kwargs)
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
            except Exception as exc:  # pragma: no cover - runtime HTTP path
                payload = {"detail": str(exc)}
                self._send_json(500, payload)
                return

            if route.response_class is HTMLResponse:
                self._send_text(200, str(result), "text/html; charset=utf-8")
            else:
                self._send_json(200, result)

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, status: int, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual runtime stop
        pass
    finally:
        server.server_close()


def _load_app(app_path: str):
    module_name, attr = app_path.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _build_kwargs(func, params: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    signature = inspect.signature(func)
    for name, parameter in signature.parameters.items():
        if name in params:
            kwargs[name] = _coerce_value(params[name], parameter.annotation)
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
