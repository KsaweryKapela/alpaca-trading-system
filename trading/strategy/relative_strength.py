"""Relative Strength vs SPY — intraday momentum.

Idea: Stocks that are performing strongly vs the market tend to continue
outperforming (intraday momentum). Stocks that are underperforming tend to
continue lagging.

In a downtrend (SPY falling), the weakest stocks fall the hardest — short them.
In an uptrend (SPY rising), the strongest stocks rise the most — buy them.

Rules:
  1. Track each stock's % return from its own day open.
  2. Track SPY's % return from its day open.
  3. Compute relative strength (RS) = stock_return_pct - spy_return_pct.
  4. Entry time window: from `entry_after_min` minutes after open until `entry_end_hour` ET.
  5. SHORT entry: RS < -rs_threshold (stock is underperforming SPY by threshold %).
  6. LONG entry:  RS > +rs_threshold (stock is outperforming SPY by threshold %).
  7. Optional regime filter: only take shorts when SPY is below its own VWAP (bearish session)
     and only take longs when SPY is above VWAP.
  8. Stop loss: stop_pct% from entry.
  9. One trade per symbol per day.
 10. EOD flatten at 15:55 ET (handled by engine).
"""

from collections import deque
from datetime import date
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
import statistics

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class RelativeStrengthStrategy(Strategy):
    name = "relative_strength"
    label = "Relative Strength vs SPY"

    def __init__(
        self,
        symbols: List[str],
        rs_threshold: float = 0.5,      # min RS difference % to enter (stock vs SPY)
        stop_pct: float = 1.0,           # % stop from entry
        profit_target_pct: float = 0.0,  # % profit target from entry (0 = no target, hold to EOD or stop)
        direction: str = "both",         # "both" | "long_only" | "short_only"
        regime_filter: bool = True,      # use SPY VWAP to gate direction
        spy_decline_pct: float = 0.0,    # additional filter: SPY must be down ≥X% from day open (0=off)
        spy_rise_pct: float = 0.0,       # additional filter: SPY must be up ≥X% from day open for longs (0=off)
        spy_trend_days: int = 0,         # multi-day trend filter: only short when SPY < close N days ago (0=off)
        spy_gap_dn_pct: float = 0.0,     # gap filter: only short when SPY opens ≥X% below prior close (0=off)
        entry_after_min: int = 5,        # wait this many minutes after open before entering
        entry_end_hour: int = 14,        # no new entries after this ET hour
        max_daily_signals: int = 0,      # cap total signals per day (0 = unlimited); approximates rank-and-trade
        atr_expansion_filter: bool = False,  # only trade when SPY session range > rolling average (skip dead tape)
        atr_lookback: int = 14,          # days to average for ATR expansion baseline
    ) -> None:
        super().__init__(symbols)
        self.rs_threshold = rs_threshold
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.spy_decline_pct = spy_decline_pct
        self.spy_rise_pct = spy_rise_pct
        self.spy_trend_days = spy_trend_days
        self.spy_gap_dn_pct = spy_gap_dn_pct
        self.entry_after_min = entry_after_min
        self.entry_end_hour = entry_end_hour
        self.max_daily_signals = max_daily_signals
        self.atr_expansion_filter = atr_expansion_filter
        self.atr_lookback = atr_lookback
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}
        self._daily_signal_count: int = 0
        self._signal_count_date = None

    def _fresh_day_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
        }

    def _fresh_spy(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "prev_close": None,                         # SPY close from previous day
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1)),  # rolling N-day close history
            "gap_dn_ok": True,   # gap-down filter: True if today's gap confirms shorting allowed
            # ATR expansion tracking
            "session_high": None,   # SPY high so far today
            "session_low": None,    # SPY low so far today
            "daily_ranges": deque(maxlen=self.atr_lookback),  # previous days' H-L ranges
            "atr_ok": True,         # True if today's session is above-average volatility
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_day_sym() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        regime_note = ("SPY VWAP regime filter — only short on bearish sessions, "
                       "only long on bullish") if self.regime_filter else "No regime filter"
        return [
            f"Track each stock's % return from its own day open",
            f"Compute Relative Strength (RS) = stock_return% - SPY_return%",
            f"SHORT when RS < -{self.rs_threshold}% (underperforming SPY — weak stock in weak market)",
            f"LONG when RS > +{self.rs_threshold}% (outperforming SPY — strong stock in strong market)",
            f"Stop loss: {self.stop_pct}% from entry",
            *([] if self.profit_target_pct == 0 else [f"Profit target: {self.profit_target_pct}% from entry"]),
            f"Direction: {self.direction}",
            f"{regime_note}",
            *([] if self.spy_decline_pct == 0 else
              [f"SPY decline filter: SPY must be ≥{self.spy_decline_pct}% below day open for shorts"]),
            *([] if self.spy_trend_days == 0 else
              [f"SPY multi-day trend filter: only short when SPY < close {self.spy_trend_days} days ago"]),
            f"Entry window: {self.entry_after_min} min after open → {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Process SPY first
        spy_bar = bars.get("SPY")
        spy_return_pct: Optional[float] = None
        spy_vwap: Optional[float] = None
        spy_price: Optional[float] = None

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_today = et_spy.date()
            spy = self._spy_state

            if spy["current_date"] != spy_today:
                # Record previous day's range for ATR expansion tracking
                if spy["session_high"] is not None and spy["session_low"] is not None:
                    spy["daily_ranges"].append(spy["session_high"] - spy["session_low"])
                # Record previous day's close before resetting
                if spy["prev_close"] is not None:
                    spy["daily_closes"].append(spy["prev_close"])
                # Compute gap-down filter for new day
                if self.spy_gap_dn_pct > 0 and spy["prev_close"] is not None and spy["prev_close"] > 0:
                    gap_pct = (spy_bar.open - spy["prev_close"]) / spy["prev_close"] * 100
                    spy["gap_dn_ok"] = gap_pct <= -self.spy_gap_dn_pct
                else:
                    spy["gap_dn_ok"] = True  # no filter → always allow
                spy["current_date"] = spy_today
                spy["day_open"] = spy_bar.open
                spy["vwap_num"] = 0.0
                spy["vwap_den"] = 0.0
                spy["vwap"] = None
                spy["session_high"] = spy_bar.high
                spy["session_low"] = spy_bar.low

            # Update SPY VWAP
            typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
            spy["vwap_num"] += typical * spy_bar.volume
            spy["vwap_den"] += spy_bar.volume
            if spy["vwap_den"] > 0:
                spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

            # Update session high/low for ATR expansion
            if spy["session_high"] is not None:
                spy["session_high"] = max(spy["session_high"], spy_bar.high)
                spy["session_low"] = min(spy["session_low"], spy_bar.low)
            else:
                spy["session_high"] = spy_bar.high
                spy["session_low"] = spy_bar.low

            # Recompute ATR expansion flag
            if self.atr_expansion_filter and len(spy["daily_ranges"]) >= 3:
                avg_range = statistics.mean(spy["daily_ranges"])
                current_range = (spy["session_high"] or 0) - (spy["session_low"] or 0)
                spy["atr_ok"] = current_range >= avg_range * 0.8  # at least 80% of avg = active
            else:
                spy["atr_ok"] = True  # filter off or insufficient history

            spy_price = spy_bar.close
            spy_vwap = spy["vwap"]
            spy["prev_close"] = spy_price  # track for next day's close recording

            if spy["day_open"] and spy["day_open"] > 0:
                spy_return_pct = (spy_price - spy["day_open"]) / spy["day_open"] * 100

        for symbol in self.symbols:
            if symbol == "SPY":
                continue  # don't trade SPY against itself

            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Day reset
            if st["current_date"] != today:
                st["current_date"] = today
                st["day_open"] = bar.open
                st["traded_today"] = False
                st["stop_level"] = None
                # Reset daily signal counter at the start of each new day
                if self._signal_count_date != today:
                    self._daily_signal_count = 0
                    self._signal_count_date = today

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="RS long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="RS long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="RS short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="RS short target"))
                continue

            # Entry gate: after warm-up minutes and before cutoff
            open_mins = 9 * 60 + 30
            bar_mins = et.hour * 60 + et.minute
            if bar_mins < open_mins + self.entry_after_min:
                continue
            if et.hour >= self.entry_end_hour:
                continue
            if st["traded_today"] or spy_return_pct is None:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            # Compute RS
            stock_return_pct = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_return_pct - spy_return_pct

            # Regime gate
            spy_bullish = spy_vwap is not None and spy_price is not None and spy_price > spy_vwap
            spy_bearish = spy_vwap is not None and spy_price is not None and spy_price < spy_vwap

            allow_long  = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            if self.regime_filter:
                allow_long  = allow_long  and spy_bullish
                allow_short = allow_short and spy_bearish

            # Additional SPY absolute-decline gate for shorts
            if self.spy_decline_pct > 0 and spy_return_pct is not None:
                allow_short = allow_short and spy_return_pct <= -self.spy_decline_pct

            # Additional SPY rise gate for longs (require strong bull session)
            if self.spy_rise_pct > 0 and spy_return_pct is not None:
                allow_long = allow_long and spy_return_pct >= self.spy_rise_pct

            # Gap-down filter: only short when SPY opens lower than previous close by spy_gap_dn_pct
            if self.spy_gap_dn_pct > 0:
                allow_short = allow_short and spy["gap_dn_ok"]

            # Multi-day trend filter: only short when SPY is below its N-day-ago close
            if self.spy_trend_days > 0 and spy_price is not None:
                closes = spy["daily_closes"]
                if len(closes) >= self.spy_trend_days:
                    spy_n_days_ago = closes[0]  # oldest entry in the rolling window
                    allow_short = allow_short and spy_price < spy_n_days_ago

            # ATR expansion filter: only trade on active/volatile sessions
            if self.atr_expansion_filter:
                allow_short = allow_short and spy["atr_ok"]
                allow_long  = allow_long  and spy["atr_ok"]

            # Max daily signals cap (approximates rank-and-trade by limiting churn)
            if self.max_daily_signals > 0 and self._daily_signal_count >= self.max_daily_signals:
                continue

            # SHORT: stock is weaker than SPY (underperforming in a down move)
            if rs < -self.rs_threshold and allow_short:
                st["traded_today"] = True
                self._daily_signal_count += 1
                st["stop_level"] = price * (1 + self.stop_pct / 100)
                st["take_profit"] = (price * (1 - self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"RS={rs:.2f}%<-{self.rs_threshold}% weak vs SPY"))

            # LONG: stock is stronger than SPY (leading in an up move)
            elif rs > self.rs_threshold and allow_long:
                st["traded_today"] = True
                self._daily_signal_count += 1
                st["stop_level"] = price * (1 - self.stop_pct / 100)
                st["take_profit"] = (price * (1 + self.profit_target_pct / 100)
                                     if self.profit_target_pct > 0 else None)
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"RS={rs:.2f}%>+{self.rs_threshold}% strong vs SPY"))

        return signals
