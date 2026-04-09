"""System configuration loaded from environment variables and defaults."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AlpacaConfig:
    api_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    paper: bool = field(
        default_factory=lambda: os.getenv("ALPACA_PAPER", "true").lower() == "true"
    )


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_per_share: float = 0.005   # $0.005/share (IB-style)
    slippage_bps: float = 5.0             # 5 basis points


@dataclass
class RiskConfig:
    max_position_pct: float = 0.10   # max 10% of equity per position
    max_positions: int = 10
    min_cash_pct: float = 0.05       # keep at least 5% in cash


@dataclass
class Config:
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
