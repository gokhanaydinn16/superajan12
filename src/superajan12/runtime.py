from __future__ import annotations

from typing import Any

from superajan12.agents.reference import CryptoReferenceAgent
from superajan12.agents.risk import RiskEngine
from superajan12.audit import AuditLogger
from superajan12.config import Settings, get_settings
from superajan12.connectors.binance import BinanceFuturesClient
from superajan12.connectors.coinbase import CoinbasePublicClient
from superajan12.connectors.okx import OKXPublicClient
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.models import ScanResult
from superajan12.storage import SQLiteStore


def ensure_runtime_paths(settings: Settings | None = None) -> Settings:
    settings = settings or get_settings()
    SQLiteStore(settings.sqlite_path)
    settings.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    return settings


def build_polymarket_client(settings: Settings | None = None) -> PolymarketClient:
    settings = settings or get_settings()
    return PolymarketClient(
        gamma_base_url=str(settings.polymarket_gamma_base_url),
        clob_base_url=str(settings.polymarket_clob_base_url),
    )


def build_risk_engine(settings: Settings | None = None) -> RiskEngine:
    settings = settings or get_settings()
    return RiskEngine(
        max_market_risk_usdc=settings.max_market_risk_usdc,
        max_daily_loss_usdc=settings.max_daily_loss_usdc,
        min_volume_usdc=settings.min_volume_usdc,
        max_spread_bps=settings.max_spread_bps,
        min_liquidity_usdc=settings.min_liquidity_usdc,
    )


def build_reference_agent(settings: Settings | None = None) -> CryptoReferenceAgent:
    settings = settings or get_settings()
    return CryptoReferenceAgent(
        binance=BinanceFuturesClient(str(settings.binance_usds_futures_base_url)),
        okx=OKXPublicClient(str(settings.okx_base_url)),
        coinbase=CoinbasePublicClient(str(settings.coinbase_public_base_url)),
        max_deviation_bps=settings.max_reference_price_deviation_bps,
    )


def persist_scan_result(
    result: ScanResult,
    *,
    summary_event_type: str,
    settings: Settings | None = None,
) -> int:
    settings = ensure_runtime_paths(settings)
    scan_id = SQLiteStore(settings.sqlite_path).save_scan(result)
    audit = AuditLogger(settings.audit_log_path)
    audit.record(summary_event_type, {"scan_id": scan_id, **result.model_dump(mode="json")})
    for score in result.scores:
        audit.record("market.scored", {"scan_id": scan_id, **score.model_dump(mode="json")})
    for idea in result.ideas:
        audit.record("paper_trade.idea", {"scan_id": scan_id, **idea.model_dump(mode="json")})
    for position in result.paper_positions:
        audit.record("paper_position.opened", {"scan_id": scan_id, **position.model_dump(mode="json")})
    return scan_id


def build_scan_response(result: ScanResult, scan_id: int) -> dict[str, Any]:
    return {
        "scan_id": scan_id,
        "score_count": len(result.scores),
        "idea_count": len(result.ideas),
        "paper_position_count": len(result.paper_positions),
    }
