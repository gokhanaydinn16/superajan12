from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HTTPStatusError(RuntimeError):
    pass


class RequestError(RuntimeError):
    pass


@dataclass
class Response:
    status_code: int
    text: str

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPStatusError(f"HTTP {self.status_code}")


class AsyncClient:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict[str, object] | None = None) -> Response:
        if params:
            query = urlencode({key: value for key, value in params.items() if value is not None})
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"
        request = Request(url, method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as handle:
                return Response(status_code=getattr(handle, "status", 200), text=handle.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failures depend on runtime
            raise RequestError(str(exc)) from exc
