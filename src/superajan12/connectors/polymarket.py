from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from superajan12.models import Market, OrderBookLevel, OrderBookSnapshot


class PolymarketClient:
    """Public-data Polymarket client.

    This client only reads market data. It does not sign orders and does not send
    live trades. That is intentional for the first implementation phase.
    """

    def __init__(self, gamma_base_url: str, clob_base_url: str, timeout: float = 15.0) -> None:
        self.gamma_base_url = gamma_base_url.rstrip("/")
        self.clob_base_url = clob_base_url.rstrip("/")
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def list_markets(self, limit: int = 50, offset: int = 0) -> list[Market]:
        """Fetch active Gamma markets.

        Official quickstart examples use Gamma /markets with active, closed and
        limit parameters. The docs also list offset pagination, so the method
        keeps offset support while the caller can later move to event-based
        discovery for larger crawls.
        """

        params = {
            "limit": limit,
            "offset": offset,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.gamma_base_url}/markets", params=params)
            response.raise_for_status()
            payload = response.json()

        if isinstance(payload, dict):
            items = payload.get("markets") or payload.get("data") or []
        else:
            items = payload

        return [self._parse_market(item) for item in items if isinstance(item, dict)]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def get_order_book(self, token_id: str, market_id: str) -> OrderBookSnapshot:
        """Fetch an order book snapshot for a CLOB token id."""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.clob_base_url}/book", params={"token_id": token_id})
            response.raise_for_status()
            payload = response.json()

        bids = self._parse_levels(payload.get("bids", []), reverse=True)
        asks = self._parse_levels(payload.get("asks", []), reverse=False)
        return OrderBookSnapshot(market_id=market_id, yes_bids=bids, yes_asks=asks)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def get_midpoint(self, token_id: str) -> float | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.clob_base_url}/midpoint", params={"token_id": token_id})
            response.raise_for_status()
            payload = response.json()
        return self._float_or_none(payload.get("mid") or payload.get("midpoint"))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def get_spread(self, token_id: str) -> float | None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.clob_base_url}/spread", params={"token_id": token_id})
            response.raise_for_status()
            payload = response.json()
        return self._float_or_none(payload.get("spread"))

    def snapshot_from_mid_and_spread(
        self, *, token_id: str, market_id: str, midpoint: float | None, spread: float | None
    ) -> OrderBookSnapshot | None:
        """Build a lightweight synthetic BBO snapshot when full book is unavailable."""

        if midpoint is None or spread is None or midpoint <= 0:
            return None
        bid = max(0.0, midpoint - spread / 2)
        ask = min(1.0, midpoint + spread / 2)
        return OrderBookSnapshot(
            market_id=market_id,
            yes_bids=[OrderBookLevel(price=bid, size=0.0)],
            yes_asks=[OrderBookLevel(price=ask, size=0.0)],
        )

    def extract_yes_token_id(self, market: Market) -> str | None:
        raw = market.raw
        candidates: list[Any] = []
        for key in ("clobTokenIds", "clobTokenIDs", "tokenIds", "outcomeTokenIds"):
            value = raw.get(key)
            if value:
                candidates.append(value)

        for value in candidates:
            normalized = self._normalize_token_id_list(value)
            if normalized:
                return normalized[0]
        return None

    def _normalize_token_id_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
            stripped = stripped.strip("[]")
            return [part.strip().strip('"').strip("'") for part in stripped.split(",") if part.strip()]
        return []

    def _parse_market(self, item: dict[str, Any]) -> Market:
        end_date = None
        raw_end_date = item.get("endDate") or item.get("end_date")
        if isinstance(raw_end_date, str):
            try:
                end_date = datetime.fromisoformat(raw_end_date.replace("Z", "+00:00"))
            except ValueError:
                end_date = None

        return Market(
            id=str(item.get("id") or item.get("conditionId") or item.get("slug") or "unknown"),
            question=str(item.get("question") or item.get("title") or "Untitled market"),
            slug=item.get("slug"),
            category=item.get("category"),
            active=bool(item.get("active", True)),
            closed=bool(item.get("closed", False)),
            volume_usdc=self._float_or_zero(item.get("volume") or item.get("volumeNum")),
            liquidity_usdc=self._float_or_zero(item.get("liquidity") or item.get("liquidityNum")),
            end_date=end_date,
            resolution_source=item.get("resolutionSource") or item.get("resolution_source"),
            raw=item,
        )

    def _parse_levels(self, levels: list[Any], reverse: bool) -> list[OrderBookLevel]:
        parsed: list[OrderBookLevel] = []
        for level in levels:
            if isinstance(level, dict):
                price = level.get("price")
                size = level.get("size")
            elif isinstance(level, list | tuple) and len(level) >= 2:
                price, size = level[0], level[1]
            else:
                continue
            try:
                parsed.append(OrderBookLevel(price=float(price), size=float(size)))
            except (TypeError, ValueError):
                continue
        return sorted(parsed, key=lambda row: row.price, reverse=reverse)

    def _float_or_zero(self, value: Any) -> float:
        parsed = self._float_or_none(value)
        return parsed if parsed is not None else 0.0

    def _float_or_none(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
