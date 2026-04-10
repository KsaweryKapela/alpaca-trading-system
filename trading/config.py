"""System configuration loaded from environment variables and defaults."""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()

# Default asset universe
STOCKS = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]
ETFS = ["SPY", "QQQ", "IWM", "XLF", "XLE", "XLK"]
DEFAULT_UNIVERSE = STOCKS + ETFS

# Primary evaluation window
EVAL_START = "2026-01-01"
EVAL_END = "2026-04-30"


@dataclass
class AlpacaConfig:
    api_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    paper: bool = field(
        default_factory=lambda: os.getenv("ALPACA_PAPER", "true").lower() == "true"
    )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("ALPACA_API_KEY is not set. Add it to your .env file.")
        if not self.secret_key:
            raise ValueError("ALPACA_SECRET_KEY is not set. Add it to your .env file.")


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_per_share: float = 0.005   # $0.005/share
    slippage_bps: float = 5.0             # 5 basis points
    max_volume_pct: float = 0.01          # fill at most 1% of bar volume


@dataclass
class RiskConfig:
    max_position_pct: float = 0.10   # max 10% of equity per position (before leverage)
    max_positions: int = 20
    min_cash_pct: float = 0.02       # keep at least 2% cash buffer
    max_daily_loss_pct: float = 0.0  # disabled by default (0 = off)


@dataclass
class Config:
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
