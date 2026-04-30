from __future__ import annotations

from superajan12.agents.reference import ReferenceCheck
from superajan12.models import Decision, Market, ReferenceReliability


class ReferenceReliabilityAgent:
    def evaluate(self, market: Market, checks: list[ReferenceCheck] | None = None) -> ReferenceReliability:
        text = f"{market.question} {market.category or ''}".lower()
        crypto_terms = ("bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto")
        is_crypto_market = any(term in text for term in crypto_terms)

        if not is_crypto_market:
            return ReferenceReliability(
                decision=Decision.APPROVE,
                confidence=0.75,
                max_deviation_bps=None,
                reasons=["kripto referans kontrolu gerekmiyor"],
            )

        if not checks:
            return ReferenceReliability(
                decision=Decision.WATCH,
                confidence=0.35,
                max_deviation_bps=None,
                reasons=["kripto market ama referans fiyat kontrolu yok"],
            )

        relevant = [check for check in checks if check.symbol.lower() in text]
        if not relevant:
            relevant = checks

        max_dev = max(
            (check.max_deviation_bps for check in relevant if check.max_deviation_bps is not None),
            default=None,
        )
        if any(not check.ok for check in relevant):
            return ReferenceReliability(
                decision=Decision.REJECT,
                confidence=0.15,
                max_deviation_bps=max_dev,
                reasons=["referans fiyat kaynaklari tutarsiz"],
            )

        return ReferenceReliability(
            decision=Decision.APPROVE,
            confidence=0.85,
            max_deviation_bps=max_dev,
            reasons=["referans fiyat kaynaklari uyumlu"],
        )
