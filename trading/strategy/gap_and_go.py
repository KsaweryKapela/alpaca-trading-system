"""Gap and Go — continue the gap, don't fade it.

Hypothesis:
  When a stock gaps up overnight (open > yesterday_close by ≥ min_gap_pct%)
  AND holds above the gap entry level at 9:45 ET (15-minute hold = buyers
  defended the gap), institutional demand is real and the stock should
  continue higher during the session. Entry = confirmed gap hold; stop =
  below entry (if the gap fades > stop_pct%, demand was fake).

  Contrasts with gap_fill (fade the gap = mean reversion). This is
  momentum/continuation: gap represents overnight institutional sentiment
  that persists into the session.

  Should perform best in bull-market regimes when overnight gaps are
  frequently defended. On bearish sessions (SPY weak), gaps often fill
  quickly → SPY regime filter blocks entries.

Rules:
  1. Track previous session's closing price for each symbol.
  2. At market open, compute gap% = (today_open − prev_close) / prev_close × 100.
  3. Only consider gaps in [min_gap_pct, max_gap_pct] range (avoid news blowups).
  4. At 9:45 ET (after 15-min warmup): if current price STILL above the gap
     threshold (prev_close × (1 + gap_hold_ratio × min_gap_pct/100)),
     AND SPY is in a bullish session (above VWAP and up > spy_min_move_pct%),
     → enter LONG.
  5. Stop loss: stop_pct% below entry price.
  6. Profit target: profit_target_pct% above entry (0 = hold to EOD).
  7. One trade per symbol per day.
  8. No entries after entry_end_hour ET.
  9. EOD flatten at 15:55 ET by engine.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
WARMUP_MINUTES = 15


class GapAndGoStrategy(Strategy):
    """Gap continuation — long gap-up stocks that hold after 9:45."""

    name = "gap_and_go"
    label = "Gap and Go (continuation)"

    def __init__(
        self,
        symbols: List[str],
        min_gap_pct: float = 0.5,        # minimum gap to consider
        max_gap_pct: float = 3.0,        # skip large gaps (earnings/news)
        gap_hold_ratio: float = 0.5,     # at entry, price must still be above prev_close + hold_ratio × gap
        stop_pct: float = 1.0,           # stop below entry
        profit_target_pct: float = 2.0,  # target above entry
        spy_min_move_pct: float = 0.3,   # SPY up from open threshold for bullish session
        entry_after_min: int = 15,       # minutes after open before entry check (15=9:45, 60=10:30)
        entry_end_hour: int = 11,        # only enter early (morning session)
    ) -> None:
        super().__init__(symbols)
        self.min_gap_pct = min_gap_pct
        self.max_gap_pct = max_gap_pct
        self.gap_hold_ratio = gap_hold_ratio
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.spy_min_move_pct = spy_min_move_pct
        self.entry_after_min = entry_after_min
        self.entry_end_hour = entry_end_hour

        self._prev_close: Dict[str, Optional[float]] = {}
        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "gap_pct": None,       # gap at open
            "gap_threshold": None, # minimum price to confirm gap hold
            "tried_entry": False,  # entry attempted (or confirmed no gap)
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
        }

    def on_start(self) -> None:
        self._prev_close = {sym: None for sym in self.symbols}
        self._state = {sym: self._fresh_day() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        return [
            "Track previous session's closing price for each symbol",
            f"Gap-up: today_open > prev_close × (1 + {self.min_gap_pct}/100)",
            f"Skip gaps > {self.max_gap_pct}% (earnings/news blowups)",
            f"At 9:45 ET: if price still above {int(self.gap_hold_ratio*100)}% of gap → gap is held",
            f"Session filter: SPY above VWAP AND up >{self.spy_min_move_pct}% from open",
            f"Entry: LONG on gap hold confirmation at 9:45",
            f"Stop: {self.stop_pct}% below entry",
            *([] if self.profit_target_pct == 0 else
              [f"Target: {self.profit_target_pct}% above entry"]),
            f"Entry window: 9:45 → {self.entry_end_hour}:00 ET (one trade/day)",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_spy_vwap(self, bar: Bar, today) -> None:
        s = self._spy_state
        if s["current_date"] != today:
            s["current_date"] = today
            s["day_open"] = bar.open
            s["vwap_num"] = 0.0
            s["vwap_den"] = 0.0
            s["vwap"] = None
        typical = (bar.high + bar.low + bar.close) / 3
        s["vwap_num"] += typical * bar.volume
        s["vwap_den"] += bar.volume
        if s["vwap_den"] > 0:
            s["vwap"] = s["vwap_num"] / s["vwap_den"]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── SPY session regime ────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_bullish = False

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            self._update_spy_vwap(spy_bar, et_spy.date())
            spy = self._spy_state
            if (spy["vwap"] is not None and spy["day_open"] and spy["day_open"] > 0):
                spy_return = (spy_bar.close - spy["day_open"]) / spy["day_open"] * 100
                spy_bullish = (spy_bar.close > spy["vwap"]
                               and spy_return > self.spy_min_move_pct)

        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Skip pre/post market
            if not (et.hour > MARKET_OPEN_HOUR
                    or (et.hour == MARKET_OPEN_HOUR and et.minute >= MARKET_OPEN_MIN)):
                self._prev_close[symbol] = bar.close
                continue
            if et.hour >= 16:
                continue

            # Day reset — compute gap at open
            if st["current_date"] != today:
                prev = self._prev_close.get(symbol)
                st.update(self._fresh_day())
                st["current_date"] = today
                st["day_open"] = bar.open
                if prev is not None and prev > 0:
                    gap = (bar.open - prev) / prev * 100
                    st["gap_pct"] = gap
                    if self.min_gap_pct <= gap <= self.max_gap_pct:
                        # Gap hold threshold: prev_close + gap_hold_ratio × (open − prev_close)
                        st["gap_threshold"] = prev + self.gap_hold_ratio * (bar.open - prev)

            close = bar.close
            bar_mins = et.hour * 60 + et.minute
            open_mins = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
            warmup_done = bar_mins >= open_mins + self.entry_after_min

            # ── Manage open position ─────────────────────────────────────────
            pos = portfolio.get_position(symbol)
            qty = pos.quantity if pos else 0

            if qty > 0:
                if st["stop_level"] is not None and close <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap-go stop {close:.2f}<={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and close >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap-go TP {close:.2f}>={st['take_profit']:.2f}"))
                self._prev_close[symbol] = close
                continue

            # ── Entry logic ──────────────────────────────────────────────────
            can_enter = (
                warmup_done
                and not st["traded_today"]
                and not st["tried_entry"]
                and et.hour < self.entry_end_hour
                and st["gap_threshold"] is not None
                and spy_bullish
            )

            if can_enter:
                st["tried_entry"] = True  # only try once per day
                if close >= st["gap_threshold"]:
                    stop = close * (1 - self.stop_pct / 100)
                    tp = (close * (1 + self.profit_target_pct / 100)
                          if self.profit_target_pct > 0 else None)
                    st["traded_today"] = True
                    st["stop_level"] = stop
                    st["take_profit"] = tp
                    signals.append(Signal(
                        symbol, Direction.LONG,
                        reason=f"gap-go {close:.2f} gap={st['gap_pct']:.1f}% held"
                    ))

            self._prev_close[symbol] = close

        return signals
