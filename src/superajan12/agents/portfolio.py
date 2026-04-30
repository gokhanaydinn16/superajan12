from __future__ import annotations

from superajan12.models import PaperPosition, PaperTradeIdea


class PaperPortfolio:
    """Turns approved ideas into simulated paper positions.

    The first version is deliberately strict: it only opens a synthetic position
    when the reference price is valid and risk is positive. This creates a paper
    ledger without touching real funds.
    """

    def open_from_idea(self, idea: PaperTradeIdea) -> PaperPosition | None:
        if idea.reference_price is None:
            return None
        if idea.reference_price <= 0 or idea.reference_price >= 1:
            return None
        if idea.risk_usdc <= 0:
            return None

        size_shares = idea.risk_usdc / idea.reference_price
        return PaperPosition(
            market_id=idea.market_id,
            question=idea.question,
            side=idea.side,
            entry_price=idea.reference_price,
            size_shares=size_shares,
            risk_usdc=idea.risk_usdc,
        )
