"""Strategy registry — intraday strategies only."""

from .orb import ORBStrategy
from .vwap_reversion import VWAPReversionStrategy
from .vwap_momentum import VWAPMomentumStrategy
from .gap_fill import GapFillStrategy
from .ema_trend import EMATrendStrategy
from .orb_spy_filter import ORBSpyFilterStrategy
from .momentum_spike import MomentumSpikeStrategy
from .rsi_intraday import RSIIntradayStrategy
from .fake_breakout import FakeBreakoutStrategy
from .relative_strength import RelativeStrengthStrategy
from .vwap_trend import VWAPTrendStrategy
from .vwap_reclaim import VWAPReclaimStrategy
from .gap_and_go import GapAndGoStrategy
from .intraday_momentum import IntradayMomentumStrategy
from .combined_rs_momentum import CombinedRSMomentumStrategy
from .morning_spike_fade import MorningSpikeFadeStrategy
from .overnight_momentum import OvernightMomentumStrategy
from .allweather import AllWeatherStrategy
from .cross_sectional_revert import CrossSectionalRevertStrategy
from .volume_momentum import VolumeMomentumStrategy
from .exhaustion_fade import ExhaustionFadeStrategy
from .allweather_v2 import AllWeatherV2Strategy
from .allweather_v3 import AllWeatherV3Strategy
from .allweather_v4 import AllWeatherV4Strategy
from .allweather_global import AllWeatherGlobalStrategy
from .allweather_v5 import AllWeatherV5Strategy
from .allweather_v6 import AllWeatherV6Strategy
from .allweather_v7 import AllWeatherV7Strategy
from .allweather_v8 import AllWeatherV8Strategy
from .allweather_v9 import AllWeatherV9Strategy
from .allweather_v10 import AllWeatherV10Strategy
from .prior_day_levels import PriorDayLevelsStrategy
from .allweather_v11 import AllWeatherV11Strategy
from .allweather_v12 import AllWeatherV12Strategy
from .closing_momentum import ClosingMomentumStrategy
from .spy_reversion import SPYReversionStrategy
from .gap_context import GapContextStrategy
from .trend_regime import TrendRegimeStrategy
from .dynamic_select import DynamicSelectStrategy

STRATEGIES = {
    "orb": ORBStrategy,
    "vwap_reversion": VWAPReversionStrategy,
    "vwap_momentum": VWAPMomentumStrategy,
    "gap_fill": GapFillStrategy,
    "ema_trend": EMATrendStrategy,
    "orb_spy_filter": ORBSpyFilterStrategy,
    "momentum_spike": MomentumSpikeStrategy,
    "rsi_intraday": RSIIntradayStrategy,
    "fake_breakout": FakeBreakoutStrategy,
    "relative_strength": RelativeStrengthStrategy,
    "vwap_trend": VWAPTrendStrategy,
    "vwap_reclaim": VWAPReclaimStrategy,
    "gap_and_go": GapAndGoStrategy,
    "intraday_momentum": IntradayMomentumStrategy,
    "combined_rs_momentum": CombinedRSMomentumStrategy,
    "morning_spike_fade": MorningSpikeFadeStrategy,
    "overnight_momentum": OvernightMomentumStrategy,
    "allweather": AllWeatherStrategy,
    "cross_sectional_revert": CrossSectionalRevertStrategy,
    "volume_momentum": VolumeMomentumStrategy,
    "exhaustion_fade": ExhaustionFadeStrategy,
    "allweather_v2": AllWeatherV2Strategy,
    "allweather_v3": AllWeatherV3Strategy,
    "allweather_v4": AllWeatherV4Strategy,
    "allweather_global": AllWeatherGlobalStrategy,
    "allweather_v5": AllWeatherV5Strategy,
    "allweather_v6": AllWeatherV6Strategy,
    "allweather_v7": AllWeatherV7Strategy,
    "allweather_v8": AllWeatherV8Strategy,
    "allweather_v9": AllWeatherV9Strategy,
    "allweather_v10": AllWeatherV10Strategy,
    "prior_day_levels": PriorDayLevelsStrategy,
    "allweather_v11": AllWeatherV11Strategy,
    "allweather_v12": AllWeatherV12Strategy,
    "closing_momentum": ClosingMomentumStrategy,
    "spy_reversion": SPYReversionStrategy,
    "gap_context": GapContextStrategy,
    "trend_regime": TrendRegimeStrategy,
    "dynamic_select": DynamicSelectStrategy,
}

__all__ = ["ORBStrategy", "VWAPReversionStrategy", "VWAPMomentumStrategy",
           "GapFillStrategy", "EMATrendStrategy", "ORBSpyFilterStrategy",
           "MomentumSpikeStrategy", "RSIIntradayStrategy", "FakeBreakoutStrategy",
           "RelativeStrengthStrategy", "VWAPTrendStrategy", "STRATEGIES"]
