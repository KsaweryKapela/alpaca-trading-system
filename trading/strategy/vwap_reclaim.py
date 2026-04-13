"""VWAP Reclaim After Pullback — bull-regime pullback entry at VWAP.

Hypothesis:
  In bullish sessions, stocks that open above VWAP, then pull back to VWAP
  (testing support), then cross back above VWAP represent the institutional
  "reload" pattern: strong money accumulated at open, let weak hands shake
  out at VWAP, then resume the uptrend.

  This is fundamentally different from vwap_trend (which enters any VWAP
  cross, including the first one from below at 9:45 = buying the spike top).
  This strategy requires the specific sequence:
    1. Stock was above VWAP at some point after 9:45
    2. Stock dipped below VWAP (the pullback / shakeout)
    3. Stock crosses back above VWAP (the reclaim = entry signal)

  Entry = bottom of pullback, not top of spike.

Rules:
  1. Track each stock's intraday VWAP (cumulative typical × volume).
  2. Only on bullish sessions: SPY price > SPY VWAP AND SPY up > spy_min_move_pct% from open.
  3. Per-symbol state machine: BELOW_VWAP → ABOVE_VWAP (first time) → BELOW_VWAP (pullback) → ABOVE_VWAP (reclaim = entry).
  4. Entry triggered on bar where prev_close < vwap AND close >= vwap AND had_pullback is True.
  5. Stop loss: stop_pct% below entry.
  6. Profit target: profit_target_pct% above entry (0 = hold to EOD).
  7. One trade per symbol per day.
  8. No entries before 9:45 ET (15-min VWAP warmup) or after entry_end_hour.
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


class VWAPReclaimStrategy(Strategy):
    """VWAP reclaim after pullback on bullish sessions."""

    name = "vwap_reclaim"
    label = "VWAP Reclaim After Pullback"

    def __init__(
        self,
        symbols: List[str],
        stop_pct: float = 0.75,
        profit_target_pct: float = 1.5,
        spy_min_move_pct: float = 0.3,   # SPY must be this % from open to confirm bull session
        rs_min_pct: float = 0.0,         # stock must outperform SPY by this % from open at entry (0=off)
        entry_end_hour: int = 14,
    ) -> None:
        super().__init__(symbols)
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.spy_min_move_pct = spy_min_move_pct
        self.rs_min_pct = rs_min_pct
        self.entry_end_hour = entry_end_hour

        self._state: Dict[str, dict] = {}
        self._spy_state: dict = {}

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None,
            "day_open": None,
            "vwap_num": 0.0,
            "vwap_den": 0.0,
            "vwap": None,
            "prev_close": None,
            "traded_today": False,
            "stop_level": None,
            "take_profit": None,
            # State machine for reclaim pattern
            "was_above_vwap": False,   # has been above VWAP after warmup
            "had_pullback": False,      # has been below VWAP after was_above_vwap
            # RS tracking
            "day_open_price": None,    # opening price for RS calculation
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
        self._state = {sym: self._fresh_sym() for sym in self.symbols}
        self._spy_state = self._fresh_spy()

    def rules(self) -> List[str]:
        return [
            "Track each stock's intraday VWAP (cumulative typical price × volume)",
            f"Bullish session: SPY above VWAP AND SPY up >{self.spy_min_move_pct}% from open",
            "State machine per symbol:",
            "  Phase 1: stock crosses above VWAP (after 9:45 warmup) → mark was_above_vwap",
            "  Phase 2: stock crosses back below VWAP → mark had_pullback (shakeout)",
            "  Phase 3: stock reclaims VWAP (crosses from below → above) → ENTRY",
            f"Entry only after pullback confirmed (not the initial rise above VWAP)",
            *([] if self.rs_min_pct == 0 else
              [f"RS filter: stock must outperform SPY by ≥{self.rs_min_pct}% from open at entry"]),
            f"Stop loss: {self.stop_pct}% below entry",
            *([] if self.profit_target_pct == 0 else
              [f"Profit target: {self.profit_target_pct}% above entry"]),
            f"Entry window: 9:45 ET → {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_vwap(self, state: dict, bar: Bar, today) -> None:
        if state["current_date"] != today:
            state["current_date"] = today
            state["day_open"] = bar.open
            state["vwap_num"] = 0.0
            state["vwap_den"] = 0.0
            state["vwap"] = None
        typical = (bar.high + bar.low + bar.close) / 3
        state["vwap_num"] += typical * bar.volume
        state["vwap_den"] += bar.volume
        if state["vwap_den"] > 0:
            state["vwap"] = state["vwap_num"] / state["vwap_den"]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # ── Update SPY state ──────────────────────────────────────────────────
        spy_bar = bars.get("SPY")
        spy_price: Optional[float] = None
        spy_vwap: Optional[float] = None
        spy_return_pct: Optional[float] = None

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            self._update_vwap(self._spy_state, spy_bar, et_spy.date())
            spy_price = spy_bar.close
            spy_vwap = self._spy_state["vwap"]
            if self._spy_state["day_open"] and self._spy_state["day_open"] > 0:
                spy_return_pct = (spy_price - self._spy_state["day_open"]) / self._spy_state["day_open"] * 100

        spy_bullish = (spy_price is not None and spy_vwap is not None
                       and spy_price > spy_vwap
                       and spy_return_pct is not None
                       and spy_return_pct > self.spy_min_move_pct)

        for symbol in self.symbols:
            if symbol == "SPY":
                continue

            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET)
            today = et.date()
            st = self._state[symbol]

            # Skip pre/post market
            if not (et.hour > MARKET_OPEN_HOUR
                    or (et.hour == MARKET_OPEN_HOUR and et.minute >= MARKET_OPEN_MIN)):
                continue
            if et.hour >= 16:
                continue

            # Day reset
            if st["current_date"] != today:
                st.update(self._fresh_sym())
                st["current_date"] = today
                st["day_open_price"] = bar.open

            # Update VWAP
            self._update_vwap(st, bar, today)
            vwap = st["vwap"]
            prev_close = st["prev_close"]
            close = bar.close

            # ── Manage open position ─────────────────────────────────────────
            pos = portfolio.get_position(symbol)
            qty = pos.quantity if pos else 0

            if qty > 0:  # long
                if st["stop_level"] is not None and close <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAP reclaim stop {close:.2f}<={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and close >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAP reclaim TP {close:.2f}>={st['take_profit']:.2f}"))
                st["prev_close"] = close
                continue

            # ── Entry gate ───────────────────────────────────────────────────
            if (st["traded_today"]
                    or et.hour >= self.entry_end_hour
                    or vwap is None
                    or prev_close is None):
                # Still update state machine even if not entering
                if vwap is not None:
                    self._update_state_machine(st, close, vwap, et)
                st["prev_close"] = close
                continue

            # Warmup: 15 minutes after open
            open_mins = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
            bar_mins = et.hour * 60 + et.minute
            if bar_mins < open_mins + WARMUP_MINUTES:
                self._update_state_machine(st, close, vwap, et)
                st["prev_close"] = close
                continue

            # ── State machine update and entry check ─────────────────────────
            # Check for reclaim BEFORE updating state (use prev_close for cross detection)
            reclaim = (prev_close < vwap and close >= vwap
                       and st["was_above_vwap"] and st["had_pullback"])

            # RS confirmation at entry (optional)
            rs_ok = True
            if reclaim and self.rs_min_pct > 0 and spy_return_pct is not None and st["day_open_price"]:
                stock_ret = (close - st["day_open_price"]) / st["day_open_price"] * 100
                rs_at_entry = stock_ret - spy_return_pct
                rs_ok = rs_at_entry >= self.rs_min_pct

            if reclaim and spy_bullish and rs_ok:
                stop = close * (1 - self.stop_pct / 100)
                tp = (close * (1 + self.profit_target_pct / 100)
                      if self.profit_target_pct > 0 else None)
                st["traded_today"] = True
                st["stop_level"] = stop
                st["take_profit"] = tp
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"VWAP reclaim {close:.2f} VWAP={vwap:.2f}"))
                st["prev_close"] = close
                continue

            # Update state machine
            self._update_state_machine(st, close, vwap, et)
            st["prev_close"] = close

        return signals

    def _update_state_machine(self, st: dict, close: float, vwap: float, et) -> None:
        """Track the was_above_vwap and had_pullback state flags."""
        open_mins = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
        bar_mins = et.hour * 60 + et.minute
        after_warmup = bar_mins >= open_mins + WARMUP_MINUTES

        if not after_warmup:
            return

        if close > vwap:
            if not st["was_above_vwap"]:
                st["was_above_vwap"] = True
        else:  # close <= vwap
            if st["was_above_vwap"] and not st["had_pullback"]:
                st["had_pullback"] = True
