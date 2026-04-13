"""Cross-Sectional Intraday Reversal.

Hypothesis (Heston, Korajczyk & Sadka 2010, cross-sectional reversal research):
  Stocks with extreme morning returns tend to REVERSE intraday. Morning
  winners underperform, morning losers outperform. This is the opposite of
  cross-sectional momentum and is stronger intraday than continuation.

  At entry_time, rank all stocks by return from open. SHORT the top K
  performers (overbought morning runners). LONG the bottom K performers
  (oversold morning dippers). Hold to EOD.

  This is market-neutral (K longs + K shorts), captures daily dispersion,
  and should work in BOTH bull and bear regimes because:
  - Bull 2025: morning runners are retail FOMO, they reverse. Dippers
    are institutional accumulation, they recover.
  - Bear 2026: morning crashers overshoot on panic, they bounce. Any
    morning strength is a dead-cat bounce, it fades.

Rules:
  1. At entry_time ET, compute return from open for all symbols.
  2. Rank stocks by return (highest first).
  3. SHORT top K performers (morning winners → expect reversal down).
  4. LONG bottom K performers (morning losers → expect reversal up).
  5. Stop: stop_pct% from entry per position.
  6. One entry per symbol per day.
  7. EOD flatten at 15:55 ET.
"""

from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class CrossSectionalRevertStrategy(Strategy):
    name = "cross_sectional_revert"
    label = "Cross-Sectional Intraday Reversal"

    def __init__(
        self,
        symbols: List[str],
        top_k: int = 3,                 # short top K performers
        bottom_k: int = 3,              # long bottom K performers
        min_move_pct: float = 0.3,      # minimum return from open to qualify
        stop_pct: float = 1.5,          # stop from entry
        profit_target_pct: float = 0.0, # 0 = hold to EOD
        entry_hour: int = 10,           # ET hour for ranking
        entry_minute: int = 0,          # ET minute for ranking
    ) -> None:
        super().__init__(symbols)
        self.top_k = top_k
        self.bottom_k = bottom_k
        self.min_move_pct = min_move_pct
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.entry_hour = entry_hour
        self.entry_minute = entry_minute
        self._state: Dict[str, dict] = {}
        self._ranking_done_today = None  # date when ranking was last performed

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_sym() for sym in self.symbols}
        self._ranking_done_today = None

    def rules(self) -> List[str]:
        return [
            f"At {self.entry_hour}:{self.entry_minute:02d} ET: rank all stocks by return from open",
            f"SHORT top {self.top_k} performers (morning winners → expect reversal)",
            f"LONG bottom {self.bottom_k} performers (morning losers → expect reversal)",
            f"Min move: stock must be >{self.min_move_pct}% from open to qualify",
            f"Stop: {self.stop_pct}% from entry",
            *([] if self.profit_target_pct == 0 else
              [f"Target: {self.profit_target_pct}% from entry"]),
            f"Market-neutral: {self.top_k} shorts + {self.bottom_k} longs",
            f"EOD flatten at 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Collect returns for all symbols
        returns: List[Tuple[str, float, float]] = []  # (symbol, return_pct, price)

        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            if st["current_date"] != today:
                st["current_date"] = today
                st["day_open"] = bar.open
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open positions
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="XS revert long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="XS revert long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="XS revert short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="XS revert short target"))
                continue

            if st["traded_today"]:
                continue

            if st["day_open"] is not None and st["day_open"] > 0:
                ret = (price - st["day_open"]) / st["day_open"] * 100
                returns.append((symbol, ret, price))

        # Only do ranking at the specific entry time
        if not returns:
            return signals

        sample_bar = None
        for sym in self.symbols:
            b = bars.get(sym)
            if b is not None:
                sample_bar = b
                break
        if sample_bar is None:
            return signals

        et = sample_bar.timestamp.astimezone(ET)
        today = et.date()
        bar_mins = et.hour * 60 + et.minute
        entry_mins = self.entry_hour * 60 + self.entry_minute

        if bar_mins < entry_mins or bar_mins > entry_mins + 5:
            return signals
        if self._ranking_done_today == today:
            return signals

        self._ranking_done_today = today

        # Sort by return: highest first
        returns.sort(key=lambda x: x[1], reverse=True)

        # SHORT top K (morning winners that should reverse down)
        short_candidates = [(sym, ret, px) for sym, ret, px in returns
                           if ret > self.min_move_pct]
        for sym, ret, px in short_candidates[:self.top_k]:
            st = self._state[sym]
            st["traded_today"] = True
            st["stop_level"] = px * (1 + self.stop_pct / 100)
            st["take_profit"] = (px * (1 - self.profit_target_pct / 100)
                                 if self.profit_target_pct > 0 else None)
            signals.append(Signal(
                sym, Direction.SHORT,
                reason=f"XS revert: rank top, +{ret:.1f}% → fade"
            ))

        # LONG bottom K (morning losers that should reverse up)
        long_candidates = [(sym, ret, px) for sym, ret, px in returns
                          if ret < -self.min_move_pct]
        long_candidates.reverse()  # most negative first
        for sym, ret, px in long_candidates[:self.bottom_k]:
            st = self._state[sym]
            st["traded_today"] = True
            st["stop_level"] = px * (1 - self.stop_pct / 100)
            st["take_profit"] = (px * (1 + self.profit_target_pct / 100)
                                 if self.profit_target_pct > 0 else None)
            signals.append(Signal(
                sym, Direction.LONG,
                reason=f"XS revert: rank bottom, {ret:.1f}% → bounce"
            ))

        return signals
