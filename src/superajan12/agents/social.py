from __future__ import annotations

from superajan12.models import Decision, Market, SocialSignal


class SocialSignalAgent:
    """Conservative social signal placeholder.

    This version does not scrape social media yet. It only detects hype-heavy
    language in market text and prevents social noise from being treated as edge.
    """

    def evaluate(self, market: Market) -> SocialSignal:
        text = f"{market.question} {market.category or ''}".lower()
        hype_terms = ("viral", "trend", "meme", "rumor", "leak", "breaking", "pump", "moon")
        bot_terms = ("airdrop", "giveaway", "spam", "bot")

        hype_score = 0.0
        bot_risk_score = 0.0
        reasons: list[str] = []

        if any(term in text for term in hype_terms):
            hype_score += 0.35
            reasons.append("hype veya sosyal gundem ifadesi bulundu")

        if any(term in text for term in bot_terms):
            bot_risk_score += 0.35
            reasons.append("bot/spam riski ifadesi bulundu")

        if market.volume_usdc > 100_000 and hype_score > 0:
            hype_score += 0.1
            reasons.append("yuksek hacimli sosyal ilgi olabilir")

        risk = max(hype_score, bot_risk_score)
        confidence = max(0.0, min(1.0, 0.75 - risk))
        if risk >= 0.6:
            decision = Decision.REJECT
        elif risk >= 0.3:
            decision = Decision.WATCH
        else:
            decision = Decision.APPROVE

        return SocialSignal(
            decision=decision,
            confidence=confidence,
            hype_score=min(1.0, hype_score),
            bot_risk_score=min(1.0, bot_risk_score),
            reasons=reasons or ["belirgin sosyal gürültü riski yok"],
        )
