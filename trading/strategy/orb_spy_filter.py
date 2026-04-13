"""ORB + SPY Market Regime Filter + Individual VWAP Filter — intraday short-biased.

Hypothesis:
  ORB short breakdowns have positive expectancy when:
  1. SPY is below its VWAP (bear macro regime)
  2. The individual stock is also below its own VWAP (stock confirming bear bias)
  3. Optional: stock had a gap-down open (overnight selling pressure)

  Stable large-caps (AAPL, MSFT, AMZN, GOOGL) break the ORB range but then
  recover, generating false signals. High-beta momentum stocks (PLTR, TSLA,
  COIN, AMD) are below their VWAP when they break the ORB range, meaning the
  move is trend continuation rather than temporary dip.

Rules:
  1. Same ORB logic: first range_minutes bars establish the opening range.
  2. Direction: short_only | long_only | both.
  3. SPY VWAP filter: only enter if SPY close is BELOW SPY's running VWAP.
  4. Stock VWAP filter: only enter if symbol close is BELOW its own running VWAP.
  5. Optional gap filter: only enter if symbol opened with gap-down > min_gap_pct.
  6. Stop loss: stop_pct% above entry.
  7. Optional profit target: profit_target_pct% below entry (0 = EOD flatten only).
  8. One trade per asset per day — no re-entry.
  9. EOD flatten at 15:55 ET.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
SPY = "SPY"


class ORBSpyFilterStrategy(Strategy):
    name = "orb_spy_filter"
    label = "ORB + SPY Regime Filter"

    def __init__(
        self,
        symbols: List[str],
        range_minutes: int = 15,
        stop_pct: float = 1.0,
        profit_target_pct: float = 0.0,   # 0 = EOD only; >0 = take profit at this %
        direction: str = "short_only",    # short_only | long_only | both
        regime_filter: bool = True,       # require SPY below its VWAP for shorts
        stock_vwap_filter: bool = False,  # require stock also below its own VWAP
        gap_filter_pct: float = 0.0,      # require stock gap-down > this % (0 = off)
        max_trades_per_day: int = 1,      # max entries per symbol per day (1=no re-entry)
        reentry_cooldown: int = 5,        # bars to wait after exit before re-entering
        spy_decline_pct: float = 0.0,     # require SPY down >X% from its day open at entry (0=off)
        min_range_pct: float = 0.0,       # require ORB range width >X% of range_low (0=off)
        auto_direction: bool = False,     # auto-set direction from SPY open gap each day
        spy_gap_threshold: float = 0.0,  # min SPY gap % to trigger auto direction (0=any gap)
    ) -> None:
        super().__init__(symbols)
        self.range_minutes = range_minutes
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.regime_filter = regime_filter
        self.stock_vwap_filter = stock_vwap_filter
        self.gap_filter_pct = gap_filter_pct
        self.max_trades_per_day = max_trades_per_day
        self.reentry_cooldown = reentry_cooldown
        self.spy_decline_pct = spy_decline_pct
        self.min_range_pct = min_range_pct
        self.auto_direction = auto_direction
        self.spy_gap_threshold = spy_gap_threshold

        self._state: Dict[str, dict] = {}
        # SPY VWAP state
        self._spy_vwap_num: float = 0.0
        self._spy_vwap_den: float = 0.0
        self._spy_vwap: Optional[float] = None
        self._spy_vwap_date = None
        self._spy_day_open: Optional[float] = None  # SPY open for daily return calc
        self._spy_prev_close: Optional[float] = None  # SPY close of prior session
        self._spy_day_direction: str = direction      # auto-direction for current day
        # Per-symbol VWAP state
        self._sym_vwap: Dict[str, dict] = {}
        # Per-symbol prev close (for gap filter)
        self._prev_close: Dict[str, Optional[float]] = {}

    def _fresh_state(self) -> dict:
        return {
            "current_date": None,
            "range_bars": 0,
            "range_high": None,
            "range_low": None,
            "range_established": False,
            "trades_today": 0,       # entries taken today
            "in_position": False,    # currently in a position
            "exit_bar": None,        # bar number when last exited (for cooldown)
            "bar_count": 0,          # session bar counter
            "stop_level": None,
            "take_profit": None,
            "position_side": None,
            "day_open": None,
        }

    def on_start(self) -> None:
        self._state = {sym: self._fresh_state() for sym in self.symbols}
        self._spy_vwap_num = 0.0
        self._spy_vwap_den = 0.0
        self._spy_vwap = None
        self._spy_vwap_date = None
        self._spy_prev_close = None
        self._spy_day_direction = self.direction
        self._sym_vwap = {sym: {"num": 0.0, "den": 0.0, "val": None, "date": None}
                          for sym in self.symbols}
        self._prev_close = {sym: None for sym in self.symbols}

    def rules(self) -> List[str]:
        regime_str = "SPY below its daily VWAP" if self.regime_filter else "no SPY filter"
        vwap_str = "stock must also be below its own VWAP" if self.stock_vwap_filter else "no stock VWAP filter"
        gap_str = f"stock must have gapped down >{self.gap_filter_pct}%" if self.gap_filter_pct > 0 else "no gap filter"
        tp_str = f"{self.profit_target_pct}% profit target" if self.profit_target_pct > 0 else "EOD flatten"
        spy_dec_str = f"SPY must be down >{self.spy_decline_pct}% from day open at entry" if self.spy_decline_pct > 0 else "no SPY intraday decline filter"
        range_str = f"ORB range width must be >{self.min_range_pct}% of range_low" if self.min_range_pct > 0 else "no min range width filter"
        dir_str = (f"auto (SPY gap determines long/short each day, threshold={self.spy_gap_threshold}%)"
                   if self.auto_direction else self.direction)
        return [
            f"Opening range: first {self.range_minutes} minutes establish the range",
            f"Direction: {dir_str}",
            f"Macro regime filter: {regime_str}",
            f"SPY intraday decline filter: {spy_dec_str}",
            f"Stock VWAP filter: {vwap_str}",
            f"Gap filter: {gap_str}",
            f"Min range width filter: {range_str}",
            f"SHORT entry: breakdown below range_low (all active filters must pass)",
            f"LONG entry: breakout above range_high (when direction allows)",
            f"Stop loss: {self.stop_pct}% from entry",
            f"Exit: {tp_str}",
            f"One trade per asset per day — no re-entry",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_spy_vwap(self, bar: Bar, today) -> None:
        """Update SPY VWAP state. Resets daily, captures day open, sets auto direction."""
        if self._spy_vwap_date != today:
            # Save yesterday's close before resetting
            if self._spy_vwap_date is not None and self._spy_vwap_den > 0:
                # Approximate prev close: last computed value was the final VWAP numerator/denominator
                # We track it explicitly below
                pass
            self._spy_vwap_num = 0.0
            self._spy_vwap_den = 0.0
            self._spy_vwap = None
            self._spy_vwap_date = today
            self._spy_day_open = bar.open   # first SPY bar of the session = day open

            # Auto-direction: determine today's allowed direction from SPY opening gap
            if self.auto_direction and self._spy_prev_close is not None:
                gap_pct = (bar.open - self._spy_prev_close) / self._spy_prev_close * 100
                if gap_pct >= self.spy_gap_threshold:
                    self._spy_day_direction = "long_only"
                elif gap_pct <= -self.spy_gap_threshold:
                    self._spy_day_direction = "short_only"
                else:
                    # Gap is within threshold — no strong directional signal, skip both
                    self._spy_day_direction = "none"
            else:
                self._spy_day_direction = self.direction

        typical = (bar.high + bar.low + bar.close) / 3
        self._spy_vwap_num += typical * bar.volume
        self._spy_vwap_den += bar.volume
        if self._spy_vwap_den > 0:
            self._spy_vwap = self._spy_vwap_num / self._spy_vwap_den
        # Always update prev close so next day has it
        self._spy_prev_close = bar.close

    def _update_vwap(self, vwap_state: dict, bar: Bar, today) -> Optional[float]:
        """Update a VWAP state dict. Returns current VWAP value or None."""
        if vwap_state["date"] != today:
            vwap_state["num"] = 0.0
            vwap_state["den"] = 0.0
            vwap_state["val"] = None
            vwap_state["date"] = today
        typical = (bar.high + bar.low + bar.close) / 3
        vwap_state["num"] += typical * bar.volume
        vwap_state["den"] += bar.volume
        if vwap_state["den"] > 0:
            vwap_state["val"] = vwap_state["num"] / vwap_state["den"]
        return vwap_state["val"]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Update SPY VWAP first (needed for regime check)
        spy_bar = bars.get(SPY)
        spy_et_today = None
        if spy_bar is not None:
            ts = spy_bar.timestamp
            et = ts.astimezone(ET) if hasattr(ts, "astimezone") else ts
            spy_et_today = et.date()
            self._update_spy_vwap(spy_bar, spy_et_today)

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET) if hasattr(ts, "astimezone") else ts

            # Market hours check
            if not (et.hour > MARKET_OPEN_HOUR or (et.hour == MARKET_OPEN_HOUR and et.minute >= MARKET_OPEN_MIN)):
                continue
            if et.hour >= 16:
                continue

            today = et.date()
            st = self._state[symbol]

            if st["current_date"] != today:
                st.update(self._fresh_state())
                st["current_date"] = today

            # Update this symbol's VWAP
            sym_vwap = self._update_vwap(self._sym_vwap[symbol], bar, today)

            minutes_since_open = (et.hour - MARKET_OPEN_HOUR) * 60 + (et.minute - MARKET_OPEN_MIN)
            st["bar_count"] += 1

            # Range accumulation phase — track open price for gap filter
            if not st["range_established"]:
                if minutes_since_open < self.range_minutes:
                    if st["range_high"] is None:
                        st["range_high"] = bar.close
                        st["range_low"] = bar.close
                        st["day_open"] = bar.open   # first bar open = day open price
                    else:
                        st["range_high"] = max(st["range_high"], bar.high)
                        st["range_low"] = min(st["range_low"], bar.low)
                    st["range_bars"] += 1
                else:
                    st["range_established"] = True
                self._prev_close[symbol] = bar.close
                continue

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Sync in_position with actual portfolio state
            if current_qty == 0 and st["in_position"]:
                # Position was closed externally (EOD flatten, etc.) — mark exit
                st["in_position"] = False
                st["exit_bar"] = st["bar_count"]

            # Manage open position
            if current_qty > 0:  # long
                if st["stop_level"] and bar.close <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"long stop {bar.close:.2f}<={st['stop_level']:.2f}"))
                    st["in_position"] = False
                    st["exit_bar"] = st["bar_count"]
                elif st["take_profit"] and bar.close >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"long TP {bar.close:.2f}>={st['take_profit']:.2f}"))
                    st["in_position"] = False
                    st["exit_bar"] = st["bar_count"]
                self._prev_close[symbol] = bar.close
                continue

            if current_qty < 0:  # short
                if st["stop_level"] and bar.close >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"short stop {bar.close:.2f}>={st['stop_level']:.2f}"))
                    st["in_position"] = False
                    st["exit_bar"] = st["bar_count"]
                elif st["take_profit"] and bar.close <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"short TP {bar.close:.2f}<={st['take_profit']:.2f}"))
                    st["in_position"] = False
                    st["exit_bar"] = st["bar_count"]
                self._prev_close[symbol] = bar.close
                continue

            # Entry logic — skip if max trades reached or in cooldown
            max_reached = st["trades_today"] >= self.max_trades_per_day
            in_cooldown = (st["exit_bar"] is not None and
                           st["bar_count"] - st["exit_bar"] < self.reentry_cooldown)
            if max_reached or in_cooldown:
                self._prev_close[symbol] = bar.close
                continue

            # ── Filters ──────────────────────────────────────────────────────
            # 1. SPY regime filter
            spy_bearish = (
                not self.regime_filter
                or self._spy_vwap is None
                or (spy_bar is not None and spy_bar.close < self._spy_vwap)
            )
            spy_bullish = (
                not self.regime_filter
                or self._spy_vwap is None
                or (spy_bar is not None and spy_bar.close >= self._spy_vwap)
            )

            # 2. Stock VWAP filter (stock also below its own VWAP)
            stock_below_vwap = (
                not self.stock_vwap_filter
                or sym_vwap is None
                or bar.close < sym_vwap
            )
            stock_above_vwap = (
                not self.stock_vwap_filter
                or sym_vwap is None
                or bar.close > sym_vwap
            )

            # 3. Gap filter: stock opened with a gap-down (or gap-up for long)
            prev_close = self._prev_close.get(symbol)
            day_open = st.get("day_open")
            gap_down_ok = True
            gap_up_ok = True
            if self.gap_filter_pct > 0 and prev_close is not None and day_open is not None:
                gap_pct = (day_open - prev_close) / prev_close * 100
                gap_down_ok = gap_pct <= -self.gap_filter_pct
                gap_up_ok = gap_pct >= self.gap_filter_pct

            # 4. SPY intraday decline filter: SPY must be down >spy_decline_pct% from open
            spy_declined_ok = True
            if self.spy_decline_pct > 0 and self._spy_day_open and spy_bar is not None:
                spy_ret_pct = (spy_bar.close - self._spy_day_open) / self._spy_day_open * 100
                spy_declined_ok = spy_ret_pct <= -self.spy_decline_pct

            # 5. Min range width filter: ORB high-low spread must be wide enough
            range_wide_ok = True
            if self.min_range_pct > 0 and st["range_low"] and st["range_high"]:
                range_width = (st["range_high"] - st["range_low"]) / st["range_low"] * 100
                range_wide_ok = range_width >= self.min_range_pct

            # ── Entry signals ─────────────────────────────────────────────────
            # Use auto-direction if enabled, else use fixed direction param
            eff_direction = self._spy_day_direction if self.auto_direction else self.direction
            short_ok = (eff_direction in ("both", "short_only")
                        and spy_bearish and spy_declined_ok
                        and stock_below_vwap and gap_down_ok and range_wide_ok)
            long_ok = (eff_direction in ("both", "long_only")
                       and spy_bullish and stock_above_vwap and gap_up_ok and range_wide_ok)

            if st["range_low"] is not None and bar.close < st["range_low"] and current_qty == 0 and short_ok:
                stop = bar.close * (1 + self.stop_pct / 100)
                tp = (bar.close * (1 - self.profit_target_pct / 100)
                      if self.profit_target_pct > 0 else None)
                st["trades_today"] += 1
                st["in_position"] = True
                st["stop_level"] = stop
                st["take_profit"] = tp
                st["position_side"] = "short"
                reason = f"ORB breakdown #{st['trades_today']} {bar.close:.2f}"
                if self._spy_vwap:
                    reason += f" SPY_VWAP={self._spy_vwap:.2f}"
                signals.append(Signal(symbol, Direction.SHORT, reason=reason))

            elif st["range_high"] is not None and bar.close > st["range_high"] and current_qty == 0 and long_ok:
                stop = bar.close * (1 - self.stop_pct / 100)
                tp = (bar.close * (1 + self.profit_target_pct / 100)
                      if self.profit_target_pct > 0 else None)
                st["trades_today"] += 1
                st["in_position"] = True
                st["stop_level"] = stop
                st["take_profit"] = tp
                st["position_side"] = "long"
                reason = f"ORB breakout #{st['trades_today']} {bar.close:.2f}"
                if self._spy_vwap:
                    reason += f" SPY_VWAP={self._spy_vwap:.2f}"
                signals.append(Signal(symbol, Direction.LONG, reason=reason))

            self._prev_close[symbol] = bar.close

        return signals
