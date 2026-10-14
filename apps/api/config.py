from decimal import Decimal
from pathlib import Path
from typing import Literal

from midas.paper.broker import AccountConfig
from midas.risk.engine import Limits
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MIDAS_", env_file=".env", extra="ignore")
    reality_workspace: Path = Path(".")
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
