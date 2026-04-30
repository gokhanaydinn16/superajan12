from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from superajan12.connectors.binance import BinanceFuturesClient
from superajan12.connectors.coinbase import CoinbasePublicClient
from superajan12.connectors.okx import OKXPublicClient


@dataclass(frozen=True)
class ReferenceSource:
    source: str
    symbol: str
    price: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class ReferenceCheck:
    symbol: str
    ok: bool
    median_price: float | None
    max_deviation_bps: float | None
    sources: tuple[ReferenceSource, ...]
    reasons: tuple[str, ...]


class CryptoReferenceAgent:
    """Cross-checks crypto reference prices across public data sources.

    This agent is a protection layer. If Binance, OKX and Coinbase disagree too
    much, the system should not trust crypto-related prediction market signals.
    """

    def __init__(
        self,
        binance: BinanceFuturesClient,
        okx: OKXPublicClient,
        coinbase: CoinbasePublicClient,
        max_deviation_bps: float,
    ) -> None:
        self.binance = binance
        self.okx = okx
        self.coinbase = coinbase
        self.max_deviation_bps = max_deviation_bps

    async def check_btc(self) -> ReferenceCheck:
        return await self.check(
            canonical_symbol="BTC",
            binance_symbol="BTCUSDT",
            okx_inst_id="BTC-USDT",
            coinbase_product_id="BTC-USD",
        )

    async def check_eth(self) -> ReferenceCheck:
        return await self.check(
            canonical_symbol="ETH",
            binance_symbol="ETHUSDT",
            okx_inst_id="ETH-USDT",
            coinbase_product_id="ETH-USD",
        )

    async def check_sol(self) -> ReferenceCheck:
        return await self.check(
            canonical_symbol="SOL",
            binance_symbol="SOLUSDT",
            okx_inst_id="SOL-USDT",
            coinbase_product_id="SOL-USD",
        )

    async def check(
        self,
        canonical_symbol: str,
        binance_symbol: str,
        okx_inst_id: str,
        coinbase_product_id: str,
    ) -> ReferenceCheck:
        sources: list[ReferenceSource] = []
        reasons: list[str] = []

        for name, coro in (
            ("binance", self.binance.reference_snapshot(binance_symbol)),
            ("okx", self.okx.reference_snapshot(okx_inst_id)),
            ("coinbase", self.coinbase.reference_snapshot(coinbase_product_id)),
        ):
            try:
                snapshot = await coro
                price = _extract_reference_price(snapshot)
                sources.append(ReferenceSource(source=name, symbol=canonical_symbol, price=price, raw=snapshot))
                if price is None:
                    reasons.append(f"{name} price missing")
            except Exception as exc:  # noqa: BLE001
                reasons.append(f"{name} failed: {exc.__class__.__name__}")
                sources.append(ReferenceSource(source=name, symbol=canonical_symbol, price=None, raw={}))

        prices = [source.price for source in sources if source.price is not None and source.price > 0]
        if len(prices) < 2:
            return ReferenceCheck(
                symbol=canonical_symbol,
                ok=False,
                median_price=None,
                max_deviation_bps=None,
                sources=tuple(sources),
                reasons=tuple(reasons + ["not enough valid reference prices"]),
            )

        med = median(prices)
        deviations = [abs(price - med) / med * 10_000 for price in prices]
        max_dev = max(deviations)
        ok = max_dev <= self.max_deviation_bps
        if not ok:
            reasons.append(f"reference price deviation too high: {max_dev:.1f} bps")
        else:
            reasons.append("reference prices agree")

        return ReferenceCheck(
            symbol=canonical_symbol,
            ok=ok,
            median_price=med,
            max_deviation_bps=max_dev,
            sources=tuple(sources),
            reasons=tuple(reasons),
        )


def _extract_reference_price(snapshot: dict[str, Any]) -> float | None:
    for key in ("mark_price", "index_price", "last_price"):
        value = snapshot.get(key)
        if isinstance(value, int | float) and value > 0:
            return float(value)
    bid = snapshot.get("bid_price")
    ask = snapshot.get("ask_price")
    if isinstance(bid, int | float) and isinstance(ask, int | float) and bid > 0 and ask > 0:
        return (float(bid) + float(ask)) / 2
    return None
