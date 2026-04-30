from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SourceStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    LOADING = "loading"
    LIVE = "live"
    STALE = "stale"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass(frozen=True)
class SourceHealth:
    name: str
    status: SourceStatus
    last_ok_at: datetime | None = None
    last_error_at: datetime | None = None
    latency_ms: float | None = None
    stale_after_seconds: int = 60
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.status is SourceStatus.LIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "last_ok_at": self.last_ok_at.isoformat() if self.last_ok_at else None,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "latency_ms": self.latency_ms,
            "stale_after_seconds": self.stale_after_seconds,
            "error": self.error,
            "metadata": self.metadata,
        }


class SourceHealthRegistry:
    """In-memory source health registry for the desktop/backend runtime.

    This is the first runtime health layer. It avoids fake UI data by making every
    source explicit: live, stale, offline, error, loading, or not configured.
    """

    def __init__(self) -> None:
        self._sources: dict[str, SourceHealth] = {}

    def set_not_configured(self, name: str, reason: str | None = None) -> SourceHealth:
        health = SourceHealth(
            name=name,
            status=SourceStatus.NOT_CONFIGURED,
            metadata={"reason": reason} if reason else {},
        )
        self._sources[name] = health
        return health

    def set_loading(self, name: str) -> SourceHealth:
        health = SourceHealth(name=name, status=SourceStatus.LOADING)
        self._sources[name] = health
        return health

    def set_live(
        self,
        name: str,
        latency_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SourceHealth:
        health = SourceHealth(
            name=name,
            status=SourceStatus.LIVE,
            last_ok_at=datetime.now(timezone.utc),
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        self._sources[name] = health
        return health

    def set_error(self, name: str, error: str) -> SourceHealth:
        previous = self._sources.get(name)
        health = SourceHealth(
            name=name,
            status=SourceStatus.ERROR,
            last_ok_at=previous.last_ok_at if previous else None,
            last_error_at=datetime.now(timezone.utc),
            latency_ms=previous.latency_ms if previous else None,
            error=error,
            metadata=previous.metadata if previous else {},
        )
        self._sources[name] = health
        return health

    def set_offline(self, name: str, reason: str | None = None) -> SourceHealth:
        previous = self._sources.get(name)
        health = SourceHealth(
            name=name,
            status=SourceStatus.OFFLINE,
            last_ok_at=previous.last_ok_at if previous else None,
            last_error_at=datetime.now(timezone.utc),
            error=reason,
            metadata=previous.metadata if previous else {},
        )
        self._sources[name] = health
        return health

    def all(self) -> list[SourceHealth]:
        return list(self._sources.values())

    def snapshot(self) -> list[dict[str, Any]]:
        return [source.to_dict() for source in self.all()]


DEFAULT_SOURCES = (
    "polymarket_gamma",
    "polymarket_clob",
    "kalshi",
    "binance_futures",
    "okx",
    "coinbase",
    "dune",
    "nansen",
    "glassnode",
)


def build_default_health_registry() -> SourceHealthRegistry:
    registry = SourceHealthRegistry()
    for source in DEFAULT_SOURCES:
        registry.set_not_configured(source, reason="not checked yet")
    return registry
