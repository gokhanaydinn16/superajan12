from __future__ import annotations

import asyncio
import os
from time import perf_counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from superajan12.config import Settings, get_settings
from superajan12.connectors.binance import BinanceFuturesClient
from superajan12.connectors.coinbase import CoinbasePublicClient
from superajan12.connectors.kalshi import KalshiPublicClient
from superajan12.connectors.okx import OKXPublicClient
from superajan12.connectors.polymarket import PolymarketClient


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


async def build_live_health_registry(settings: Settings | None = None) -> SourceHealthRegistry:
    settings = settings or get_settings()
    registry = SourceHealthRegistry()

    probe_results = await asyncio.gather(
        _probe_polymarket_gamma(settings),
        _probe_polymarket_clob(settings),
        _probe_kalshi(settings),
        _probe_binance(settings),
        _probe_okx(settings),
        _probe_coinbase(settings),
    )

    for name, ok, latency_ms, metadata, error in probe_results:
        if ok:
            registry.set_live(name, latency_ms=latency_ms, metadata=metadata)
        else:
            registry.set_error(name, error or "health probe failed")

    for source, env_name in (
        ("dune", "DUNE_API_KEY"),
        ("nansen", "NANSEN_API_KEY"),
        ("glassnode", "GLASSNODE_API_KEY"),
    ):
        if os.getenv(env_name):
            registry.set_offline(source, reason="provider adapter not implemented yet")
        else:
            registry.set_not_configured(source, reason=f"{env_name} missing")

    return registry


async def _probe_polymarket_gamma(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = PolymarketClient(
        gamma_base_url=str(settings.polymarket_gamma_base_url),
        clob_base_url=str(settings.polymarket_clob_base_url),
    )
    started = perf_counter()
    try:
        markets = await client.list_markets(limit=1)
        elapsed = (perf_counter() - started) * 1000
        return (
            "polymarket_gamma",
            bool(markets),
            elapsed,
            {"market_count": len(markets)},
            None if markets else "no active markets returned",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("polymarket_gamma", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")


async def _probe_polymarket_clob(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = PolymarketClient(
        gamma_base_url=str(settings.polymarket_gamma_base_url),
        clob_base_url=str(settings.polymarket_clob_base_url),
    )
    started = perf_counter()
    try:
        markets = await client.list_markets(limit=3)
        market = next((item for item in markets if client.extract_yes_token_id(item)), None)
        if market is None:
            elapsed = (perf_counter() - started) * 1000
            return ("polymarket_clob", False, elapsed, {}, "no market with YES token id found")
        midpoint = await client.get_midpoint(client.extract_yes_token_id(market) or "")
        elapsed = (perf_counter() - started) * 1000
        return (
            "polymarket_clob",
            midpoint is not None,
            elapsed,
            {"market_id": market.id, "midpoint": midpoint},
            None if midpoint is not None else "midpoint unavailable",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("polymarket_clob", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")


async def _probe_kalshi(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = KalshiPublicClient(str(settings.kalshi_base_url))
    started = perf_counter()
    try:
        markets = await client.list_markets(limit=1)
        elapsed = (perf_counter() - started) * 1000
        return (
            "kalshi",
            bool(markets),
            elapsed,
            {"market_count": len(markets)},
            None if markets else "no markets returned",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("kalshi", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")


async def _probe_binance(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = BinanceFuturesClient(str(settings.binance_usds_futures_base_url))
    started = perf_counter()
    try:
        snapshot = await client.mark_price("BTCUSDT")
        elapsed = (perf_counter() - started) * 1000
        return (
            "binance_futures",
            bool(snapshot.get("markPrice")),
            elapsed,
            {"symbol": "BTCUSDT", "mark_price": snapshot.get("markPrice")},
            None if snapshot.get("markPrice") else "mark price missing",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("binance_futures", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")


async def _probe_okx(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = OKXPublicClient(str(settings.okx_base_url))
    started = perf_counter()
    try:
        snapshot = await client.ticker("BTC-USDT")
        elapsed = (perf_counter() - started) * 1000
        return (
            "okx",
            bool(snapshot.get("last")),
            elapsed,
            {"symbol": "BTC-USDT", "last_price": snapshot.get("last")},
            None if snapshot.get("last") else "last price missing",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("okx", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")


async def _probe_coinbase(
    settings: Settings,
) -> tuple[str, bool, float | None, dict[str, Any], str | None]:
    client = CoinbasePublicClient(str(settings.coinbase_public_base_url))
    started = perf_counter()
    try:
        snapshot = await client.product("BTC-USD")
        elapsed = (perf_counter() - started) * 1000
        return (
            "coinbase",
            bool(snapshot.get("price")),
            elapsed,
            {"symbol": "BTC-USD", "price": snapshot.get("price")},
            None if snapshot.get("price") else "price missing",
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = (perf_counter() - started) * 1000
        return ("coinbase", False, elapsed, {}, f"{exc.__class__.__name__}: {exc}")
