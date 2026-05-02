from __future__ import annotations

from superajan12.models import Decision, Market, OrderBookSnapshot, RiskDecision


class RiskEngine:
    """Conservative first-pass risk engine.

    The risk engine is the boss of the system. Strategy modules can suggest an
    idea, but this class decides whether the system may even create a paper-trade
    idea. Live execution will require stricter checks later.
    """

    def __init__(
        self,
        max_market_risk_usdc: float,
        max_daily_loss_usdc: float,
        min_volume_usdc: float,
        max_spread_bps: float,
        min_liquidity_usdc: float,
    ) -> None:
        self.max_market_risk_usdc = max_market_risk_usdc
        self.max_daily_loss_usdc = max_daily_loss_usdc
        self.min_volume_usdc = min_volume_usdc
        self.max_spread_bps = max_spread_bps
        self.min_liquidity_usdc = min_liquidity_usdc

    def evaluate_market(
        self,
        market: Market,
        order_book: OrderBookSnapshot | None,
        current_daily_pnl_usdc: float = 0.0,
        safe_mode: bool = False,
        reference_gate_ok: bool | None = None,
        reference_gate_reasons: list[str] | None = None,
    ) -> RiskDecision:
        reasons: list[str] = []

        if safe_mode:
            reasons.append("safe-mode aktif; yeni islem yok")

        if current_daily_pnl_usdc <= -abs(self.max_daily_loss_usdc):
            reasons.append("gunluk zarar limiti dolmus")

        if market.closed or not market.active:
            reasons.append("market aktif degil")

        if market.volume_usdc < self.min_volume_usdc:
            reasons.append(
                f"hacim dusuk: {market.volume_usdc:.2f} < {self.min_volume_usdc:.2f} USDC"
            )

        if market.liquidity_usdc < self.min_liquidity_usdc:
            reasons.append(
                f"likidite dusuk: {market.liquidity_usdc:.2f} < {self.min_liquidity_usdc:.2f} USDC"
            )

        if order_book is None:
            reasons.append("orderbook okunamadi")
        else:
            if order_book.best_bid is None or order_book.best_ask is None:
                reasons.append("orderbook eksik")
            elif order_book.spread_bps is None:
                reasons.append("spread hesaplanamadi")
            elif order_book.spread_bps > self.max_spread_bps:
                reasons.append(
                    f"spread genis: {order_book.spread_bps:.1f} bps > {self.max_spread_bps:.1f} bps"
                )

        if reference_gate_ok is False:
            reasons.append("referans fiyat kapisi reddetti")
            if reference_gate_reasons:
                reasons.extend(reference_gate_reasons)

        if reasons:
            return RiskDecision(decision=Decision.REJECT, max_risk_usdc=0.0, reasons=reasons)

        return RiskDecision(
            decision=Decision.APPROVE,
            max_risk_usdc=self.max_market_risk_usdc,
            reasons=["risk kontrolleri gecti"],
        )
