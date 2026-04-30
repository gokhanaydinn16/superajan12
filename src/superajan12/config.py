from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for SuperAjan12.

    Defaults are intentionally conservative. The system starts in paper mode and
    should not send live orders until the trading connector and risk controls are
    explicitly enabled.
    """

    model_config = SettingsConfigDict(env_prefix="SUPERAJAN_", env_file=".env", extra="ignore")

    env: str = "local"
    mode: Literal["paper", "shadow", "live"] = "paper"
    log_level: str = "INFO"

    polymarket_gamma_base_url: AnyHttpUrl = Field(
        default="https://gamma-api.polymarket.com", alias="POLYMARKET_GAMMA_BASE_URL"
    )
    polymarket_clob_base_url: AnyHttpUrl = Field(
        default="https://clob.polymarket.com", alias="POLYMARKET_CLOB_BASE_URL"
    )

    max_market_risk_usdc: float = 10.0
    max_daily_loss_usdc: float = 25.0
    min_volume_usdc: float = 1000.0
    max_spread_bps: float = 1200.0
    min_liquidity_usdc: float = 250.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
