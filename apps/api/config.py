from decimal import Decimal
from pathlib import Path
from typing import Literal

from midas.frontier.models import COINBASE_MARKET_DATA_TERMS_VERSION
from midas.paper.broker import AccountConfig
from midas.risk.engine import Limits
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MIDAS_", env_file=".env", extra="ignore")
    runtime_root: Path = Path(".")
    reality_workspace: Path = Path(".")
    veritas_workspace: Path | None = None
    mode: Literal["demo", "live"] = "demo"
    laboratory_root: Path | None = None
    arena_root: Path = Path("data/arena")
    database_url: str = "sqlite+aiosqlite:///./data/midas.db"
    paper_capital: Decimal = Field(default=Decimal("100"), gt=0, allow_inf_nan=False)
    paper_execution_model: Literal["optimistic", "standard", "conservative"] = "standard"
    paper_limits: Limits = AccountConfig().limits
    polygon_rpc_url: str = "https://polygon-bor-rpc.publicnode.com"
    discovery_limit: int = Field(default=100, ge=1, le=100)
    market_limit: int = Field(default=20, ge=1, le=100)
    refresh_seconds: int = Field(default=10, ge=2, le=300)
    metadata_refresh_seconds: int = Field(default=300, ge=30)
    max_data_age_ms: int = Field(default=15000, ge=1000)
    recording_max_bytes: int = Field(default=100_000_000, ge=1000)
    recording_root: Path | None = None
    retention_days: int = Field(default=30, ge=1)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontier_root: Path = Path("data/frontier-store")
    frontier_store_max_bytes: int = Field(
        default=64 * 1024 * 1024, ge=1024 * 1024, le=512 * 1024 * 1024
    )
    frontier_polymarket_public_probe_enabled: bool = False
    frontier_kalshi_public_probe_enabled: bool = False
    frontier_kalshi_research_authorization_ref: str | None = Field(default=None, max_length=300)
    frontier_kraken_public_probe_enabled: bool = False
    frontier_kraken_market_data_permission_ref: str | None = Field(default=None, max_length=300)
    frontier_kraken_pairs: str = "XBTUSD"
    frontier_coinbase_public_probe_enabled: bool = False
    frontier_coinbase_market_data_terms_version_acknowledged: str | None = Field(
        default=None, max_length=32
    )
    frontier_coinbase_products: str = "BTC-USD"

    @property
    def frontier_kalshi_probe_allowed(self) -> bool:
        """References are descriptive; no validated Kalshi authorization loader exists yet."""
        return False

    @property
    def frontier_kraken_probe_allowed(self) -> bool:
        """References are descriptive; no validated Kraken permission loader exists yet."""
        return False

    @property
    def frontier_coinbase_terms_acknowledged(self) -> bool:
        """Record an exact terms acknowledgement; this is not source-use permission."""
        return (
            self.frontier_coinbase_market_data_terms_version_acknowledged is not None
            and self.frontier_coinbase_market_data_terms_version_acknowledged
            == COINBASE_MARKET_DATA_TERMS_VERSION
        )

    @property
    def frontier_coinbase_probe_allowed(self) -> bool:
        """No validated permission and intended-scope loader exists for Coinbase."""
        return False
