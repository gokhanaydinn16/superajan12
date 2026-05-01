from __future__ import annotations

from dataclasses import dataclass

from superajan12.models import Market, OrderBookSnapshot


@dataclass(frozen=True)
class MarketStateValidation:
    ok: bool
    status: str
    confidence: float
    reasons: tuple[str, ...]
    midpoint: float | None
    spread_bps: float | None
    bid_depth_usdc: float
    ask_depth_usdc: float
    orderbook_source: str | None


class MarketStateValidator:
    """Validates whether a market snapshot is safe enough for downstream logic.

    This does not decide whether to trade. It decides whether the local view of
    the market is coherent enough for scoring, paper actions and later
    execution-adjacent workflows.
    """

    def __init__(
        self,
        *,
        max_spread_bps: float = 1_200.0,
        min_depth_usdc: float = 100.0,
        min_midpoint: float = 0.01,
        max_midpoint: float = 0.99,
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.min_depth_usdc = min_depth_usdc
        self.min_midpoint = min_midpoint
        self.max_midpoint = max_midpoint

    def validate(
        self,
        market: Market,
        order_book: OrderBookSnapshot | None,
    ) -> MarketStateValidation:
        reasons: list[str] = []
        warnings: list[str] = []

        if order_book is None:
            return MarketStateValidation(
                ok=False,
                status="invalid",
                confidence=0.0,
                reasons=("order book unavailable",),
                midpoint=None,
                spread_bps=None,
                bid_depth_usdc=0.0,
                ask_depth_usdc=0.0,
                orderbook_source=None,
            )

        best_bid = order_book.best_bid
        best_ask = order_book.best_ask
        midpoint = order_book.mid
        spread_bps = order_book.spread_bps
        bid_depth = order_book.bid_depth_usdc
        ask_depth = order_book.ask_depth_usdc

        if best_bid is None or best_ask is None:
            reasons.append("best bid/ask missing")
        else:
            if best_bid < 0 or best_bid > 1 or best_ask < 0 or best_ask > 1:
                reasons.append("best bid/ask outside prediction-market bounds")
            if best_bid >= best_ask:
                reasons.append("crossed or locked book detected")

        if midpoint is None:
            reasons.append("midpoint unavailable")
        else:
            if midpoint <= self.min_midpoint or midpoint >= self.max_midpoint:
                warnings.append("midpoint near edge of range")

        if spread_bps is None:
            reasons.append("spread unavailable")
        elif spread_bps > self.max_spread_bps:
            warnings.append("spread wider than validator threshold")

        if bid_depth < self.min_depth_usdc:
            warnings.append("bid depth below validator threshold")
        if ask_depth < self.min_depth_usdc:
            warnings.append("ask depth below validator threshold")

        if not market.active or market.closed:
            reasons.append("market inactive")

        if reasons:
            status = "invalid"
            confidence = 0.0
            final_reasons = tuple(reasons + warnings)
            ok = False
        elif warnings:
            status = "degraded"
            confidence = 0.5
            final_reasons = tuple(warnings)
            ok = True
        else:
            status = "healthy"
            confidence = 1.0
            final_reasons = ("market state validated",)
            ok = True

        return MarketStateValidation(
            ok=ok,
            status=status,
            confidence=confidence,
            reasons=final_reasons,
            midpoint=midpoint,
            spread_bps=spread_bps,
            bid_depth_usdc=bid_depth,
            ask_depth_usdc=ask_depth,
            orderbook_source=order_book.source,
        )
