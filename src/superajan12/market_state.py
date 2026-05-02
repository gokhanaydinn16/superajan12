from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from superajan12.models import Market, OrderBookLevel, OrderBookSnapshot


@dataclass(frozen=True)
class VenueValidationRules:
    max_snapshot_age_seconds: float = 15.0
    hard_snapshot_age_seconds: float = 60.0
    require_sequence_for_diff: bool = True
    require_checksum_for_diff: bool = True
    allow_synthetic_fallback: bool = True


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
    venue: str | None
    snapshot_kind: str | None
    is_synthetic: bool
    structure_status: str
    freshness_status: str
    sequence_status: str
    checksum_status: str
    sequence_start: int | None
    sequence_end: int | None
    checksum_valid: bool | None


_RULES_BY_VENUE: dict[str, VenueValidationRules] = {
    "polymarket_clob": VenueValidationRules(),
    "midpoint_spread_fallback": VenueValidationRules(allow_synthetic_fallback=True),
}


class MarketStateValidator:
    """Validate whether a local order-book view is coherent enough for downstream logic."""

    def __init__(
        self,
        *,
        max_spread_bps: float = 1_200.0,
        min_depth_usdc: float = 100.0,
        min_midpoint: float = 0.01,
        max_midpoint: float = 0.99,
        venue_rules: dict[str, VenueValidationRules] | None = None,
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.min_depth_usdc = min_depth_usdc
        self.min_midpoint = min_midpoint
        self.max_midpoint = max_midpoint
        self.venue_rules = dict(_RULES_BY_VENUE)
        if venue_rules:
            self.venue_rules.update(venue_rules)

    def validate(
        self,
        market: Market,
        order_book: OrderBookSnapshot | None,
    ) -> MarketStateValidation:
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
                venue=None,
                snapshot_kind=None,
                is_synthetic=False,
                structure_status="invalid",
                freshness_status="unavailable",
                sequence_status="unavailable",
                checksum_status="unavailable",
                sequence_start=None,
                sequence_end=None,
                checksum_valid=None,
            )

        rules = self.venue_rules.get(order_book.venue, VenueValidationRules())
        issues: list[str] = []
        warnings: list[str] = []

        structure_status = self._validate_structure(market, order_book, issues)
        freshness_status = self._validate_freshness(order_book, rules, issues, warnings)
        sequence_status = self._validate_sequence(order_book, rules, issues, warnings)
        checksum_status = self._validate_checksum(order_book, rules, issues, warnings)

        best_bid = order_book.best_bid
        best_ask = order_book.best_ask
        midpoint = order_book.mid
        spread_bps = order_book.spread_bps
        bid_depth = order_book.bid_depth_usdc
        ask_depth = order_book.ask_depth_usdc

        if best_bid is None or best_ask is None:
            issues.append("best bid/ask missing")
        else:
            if best_bid < 0 or best_bid > 1 or best_ask < 0 or best_ask > 1:
                issues.append("best bid/ask outside prediction-market bounds")
            if best_bid >= best_ask:
                issues.append("crossed or locked book detected")

        if midpoint is None:
            issues.append("midpoint unavailable")
        else:
            if midpoint <= self.min_midpoint or midpoint >= self.max_midpoint:
                warnings.append("midpoint near edge of range")

        if spread_bps is None:
            issues.append("spread unavailable")
        elif spread_bps > self.max_spread_bps:
            warnings.append("spread wider than validator threshold")

        if bid_depth < self.min_depth_usdc:
            warnings.append("bid depth below validator threshold")
        if ask_depth < self.min_depth_usdc:
            warnings.append("ask depth below validator threshold")

        if order_book.is_synthetic:
            if rules.allow_synthetic_fallback:
                warnings.append("synthetic fallback snapshot in use")
            else:
                issues.append("synthetic fallback snapshot is not allowed for this venue")

        if not market.active or market.closed:
            issues.append("market inactive")

        if issues:
            status = "invalid"
            confidence = 0.0
            ok = False
            reasons = tuple(dict.fromkeys(issues + warnings))
        elif warnings:
            status = "degraded"
            confidence = max(0.35, 1.0 - 0.12 * len(warnings))
            ok = True
            reasons = tuple(dict.fromkeys(warnings))
        else:
            status = "healthy"
            confidence = 1.0
            ok = True
            reasons = ("market state validated",)

        return MarketStateValidation(
            ok=ok,
            status=status,
            confidence=round(confidence, 3),
            reasons=reasons,
            midpoint=midpoint,
            spread_bps=spread_bps,
            bid_depth_usdc=bid_depth,
            ask_depth_usdc=ask_depth,
            orderbook_source=order_book.source,
            venue=order_book.venue,
            snapshot_kind=order_book.snapshot_kind,
            is_synthetic=order_book.is_synthetic,
            structure_status=structure_status,
            freshness_status=freshness_status,
            sequence_status=sequence_status,
            checksum_status=checksum_status,
            sequence_start=order_book.sequence_start,
            sequence_end=order_book.sequence_end,
            checksum_valid=order_book.checksum_valid,
        )

    def _validate_structure(
        self,
        market: Market,
        order_book: OrderBookSnapshot,
        issues: list[str],
    ) -> str:
        if order_book.market_id != market.id:
            issues.append("order book market id does not match requested market")

        bids_ok = self._validate_side(
            levels=order_book.yes_bids,
            descending=True,
            label="bid",
            issues=issues,
        )
        asks_ok = self._validate_side(
            levels=order_book.yes_asks,
            descending=False,
            label="ask",
            issues=issues,
        )

        if bids_ok and asks_ok:
            return "validated"
        return "invalid"

    def _validate_side(
        self,
        *,
        levels: list[OrderBookLevel],
        descending: bool,
        label: str,
        issues: list[str],
    ) -> bool:
        previous_price: float | None = None
        seen_prices: set[float] = set()
        for level in levels:
            if level.price < 0 or level.price > 1:
                issues.append(f"{label} level outside prediction-market bounds")
                return False
            if level.size < 0:
                issues.append(f"{label} level has negative size")
                return False
            if level.size == 0:
                issues.append(f"{label} level has zero size")
                return False
            if level.price in seen_prices:
                issues.append(f"duplicate {label} price level detected")
                return False
            seen_prices.add(level.price)
            if previous_price is not None:
                if descending and level.price > previous_price:
                    issues.append(f"{label} side is not sorted descending")
                    return False
                if not descending and level.price < previous_price:
                    issues.append(f"{label} side is not sorted ascending")
                    return False
            previous_price = level.price
        return True

    def _validate_freshness(
        self,
        order_book: OrderBookSnapshot,
        rules: VenueValidationRules,
        issues: list[str],
        warnings: list[str],
    ) -> str:
        latest_timestamp = self._latest_timestamp(order_book)
        age_seconds = max((datetime.now(timezone.utc) - latest_timestamp).total_seconds(), 0.0)
        if age_seconds > rules.hard_snapshot_age_seconds:
            issues.append(f"snapshot stale for {age_seconds:.1f}s")
            return "invalid"
        if age_seconds > rules.max_snapshot_age_seconds:
            warnings.append(f"snapshot age {age_seconds:.1f}s exceeds soft limit")
            return "degraded"
        return "validated"

    def _validate_sequence(
        self,
        order_book: OrderBookSnapshot,
        rules: VenueValidationRules,
        issues: list[str],
        warnings: list[str],
    ) -> str:
        if order_book.sequence_end is None:
            if order_book.snapshot_kind == "diff" and rules.require_sequence_for_diff:
                issues.append("diff update missing sequence metadata")
                return "invalid"
            return "unavailable"

        if order_book.sequence_start is not None and order_book.sequence_start > order_book.sequence_end:
            issues.append("sequence metadata is reversed")
            return "invalid"

        if (
            order_book.previous_sequence_end is not None
            and order_book.sequence_start is not None
            and order_book.sequence_start > order_book.previous_sequence_end + 1
        ):
            issues.append("sequence gap detected")
            return "invalid"

        if (
            order_book.previous_sequence_end is not None
            and order_book.sequence_end <= order_book.previous_sequence_end
        ):
            warnings.append("sequence did not advance beyond previous snapshot")
            return "degraded"

        return "validated"

    def _validate_checksum(
        self,
        order_book: OrderBookSnapshot,
        rules: VenueValidationRules,
        issues: list[str],
        warnings: list[str],
    ) -> str:
        if order_book.checksum_valid is False:
            issues.append("order book checksum mismatch")
            return "invalid"
        if order_book.checksum_valid is True:
            return "validated"
        if order_book.snapshot_kind == "diff" and rules.require_checksum_for_diff:
            warnings.append("checksum validation unavailable for diff update")
            return "degraded"
        if order_book.checksum is not None:
            warnings.append("checksum present but not validated")
            return "degraded"
        return "unavailable"

    def _latest_timestamp(self, order_book: OrderBookSnapshot) -> datetime:
        captured = order_book.captured_at
        received = order_book.received_at
        if received > captured:
            return received
        return captured
