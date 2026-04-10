"""Strategy registry — intraday strategies only."""

from .orb import ORBStrategy
from .vwap_reversion import VWAPReversionStrategy
from .vwap_momentum import VWAPMomentumStrategy
from .gap_fill import GapFillStrategy

STRATEGIES = {
    "orb": ORBStrategy,
    "vwap_reversion": VWAPReversionStrategy,
    "vwap_momentum": VWAPMomentumStrategy,
    "gap_fill": GapFillStrategy,
}

__all__ = ["ORBStrategy", "VWAPReversionStrategy", "VWAPMomentumStrategy",
           "GapFillStrategy", "STRATEGIES"]
