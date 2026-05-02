from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for SuperAjan12.

    Defaults are intentionally conservative. The system starts in paper mode and
    should not send live orders until the trading connector and risk controls are
    explicitly enabled.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    env: str = Field(default="local", validation_alias="SUPERAJAN_ENV")
    mode: Literal["paper", "shadow", "live"] = Field(default="paper", validation_alias="SUPERAJAN_MODE")
    log_level: str = Field(default="INFO", validation_alias="SUPERAJAN_LOG_LEVEL")

    polymarket_gamma_base_url: AnyHttpUrl = Field(
        default="https://gamma-api.polymarket.com", validation_alias="POLYMARKET_GAMMA_BASE_URL"
    )
    polymarket_clob_base_url: AnyHttpUrl = Field(
        default="https://clob.polymarket.com", validation_alias="POLYMARKET_CLOB_BASE_URL"
    )
    kalshi_base_url: AnyHttpUrl = Field(
        default="https://trading-api.kalshi.com/trade-api/v2", validation_alias="KALSHI_BASE_URL"
    )
    binance_usds_futures_base_url: AnyHttpUrl = Field(
        default="https://fapi.binance.com", validation_alias="BINANCE_USDS_FUTURES_BASE_URL"
    )
    okx_base_url: AnyHttpUrl = Field(default="https://www.okx.com", validation_alias="OKX_BASE_URL")
    coinbase_public_base_url: AnyHttpUrl = Field(
        default="https://api.coinbase.com/api/v3/brokerage/market",
        validation_alias="COINBASE_PUBLIC_BASE_URL",
    )

    max_market_risk_usdc: float = Field(default=10.0, validation_alias="MAX_MARKET_RISK_USDC")
    max_daily_loss_usdc: float = Field(default=25.0, validation_alias="MAX_DAILY_LOSS_USDC")
    min_volume_usdc: float = Field(default=1000.0, validation_alias="MIN_VOLUME_USDC")
    max_spread_bps: float = Field(default=1200.0, validation_alias="MAX_SPREAD_BPS")
    min_liquidity_usdc: float = Field(default=250.0, validation_alias="MIN_LIQUIDITY_USDC")
    max_reference_price_deviation_bps: float = Field(
        default=75.0, validation_alias="MAX_REFERENCE_PRICE_DEVIATION_BPS"
    )
    live_stale_data_max_seconds: float = Field(
        default=15.0, validation_alias="LIVE_STALE_DATA_MAX_SECONDS"
    )
    live_disconnect_grace_seconds: float = Field(
        default=5.0, validation_alias="LIVE_DISCONNECT_GRACE_SECONDS"
    )
    live_max_open_positions: int = Field(default=3, validation_alias="LIVE_MAX_OPEN_POSITIONS")
    live_max_position_notional_usdc: float = Field(
        default=25.0, validation_alias="LIVE_MAX_POSITION_NOTIONAL_USDC"
    )
    live_cancel_on_disconnect_required: bool = Field(
        default=True, validation_alias="LIVE_CANCEL_ON_DISCONNECT_REQUIRED"
    )

    audit_log_path: Path = Field(default=Path("data/audit/events.jsonl"), validation_alias="AUDIT_LOG_PATH")
    sqlite_path: Path = Field(default=Path("data/superajan12.sqlite3"), validation_alias="SQLITE_PATH")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
