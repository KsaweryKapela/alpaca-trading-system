"""VWAP Trend Cross — intraday trend-following entry at VWAP.

Hypothesis:
  In trending sessions, the VWAP acts as dynamic support (bullish day) or
  resistance (bearish day). When price crosses back through VWAP *in the
  direction of the session trend*, it confirms trend resumption — not
  mean reversion. This is the institutional "fade the noise, enter on
  VWAP reclaim" pattern.

  Contrast with vwap_reversion (fades extremes FROM VWAP): this strategy
  enters AT VWAP when price is crossing in trend direction.

Rules:
  1. Track each stock's intraday VWAP (cumulative typical × volume).
  2. Track SPY VWAP + SPY return-from-open for session regime.
  3. Bullish session: SPY price > SPY VWAP AND SPY is up from open > spy_min_move_pct.
     LONG entry: stock price crosses FROM BELOW → ABOVE its own VWAP.
     (prev_close < stock_vwap AND close >= stock_vwap)
  4. Bearish session: SPY price < SPY VWAP AND SPY is down from open > spy_min_move_pct.
     SHORT entry: stock price crosses FROM ABOVE → BELOW its own VWAP.
     (prev_close > stock_vwap AND close <= stock_vwap)
  5. Optional RS confirmation: stock must also be outperforming SPY from open
     by at least rs_confirm_pct% (ensures we enter leaders, not laggards).
  6. Stop loss: stop_pct% from VWAP at entry.
  7. Profit target: profit_target_pct% from entry (0 = hold to EOD/stop).
  8. One trade per symbol per day (first valid cross wins).
  9. No entries before 9:45 ET (VWAP warm-up) or after entry_end_hour.
 10. EOD flatten at 15:55 ET by engine.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
WARMUP_MINUTES = 15   # minutes after open before entries allowed


class VWAPTrendStrategy(Strategy):
    """VWAP cross in the direction of the session trend."""

    name = "vwap_trend"
    label = "VWAP Trend Cross"

    def __init__(
        self,
        symbols: List[str],
        stop_pct: float = 0.5,
        profit_target_pct: float = 1.0,   # 0 = no target, hold to EOD
        direction: str = "both",           # "both" | "long_only" | "short_only"
        spy_min_move_pct: float = 0.2,    # SPY must be this % from open to confirm session
        rs_confirm_pct: float = 0.0,      # stock must outperform SPY by this % (0 = off)
        entry_end_hour: int = 14,
    ) -> None:
        super().__init__(symbols)
        self.stop_pct = stop_pct
        self.profit_target_pct = profit_target_pct
        self.direction = direction
        self.spy_min_move_pct = spy_min_move_pct
        self.rs_confirm_pct = rs_confirm_pct
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
        regime = (f"SPY above VWAP AND up >{self.spy_min_move_pct}% from open → bullish session"
                  if self.direction in ("both", "long_only") else "")
        return [
            "Track each stock's intraday VWAP (cumulative typical price × volume)",
            f"Bullish session (SPY > VWAP AND SPY up >{self.spy_min_move_pct}% from open):",
            f"  LONG entry: stock price crosses FROM BELOW to ABOVE its own VWAP",
            f"Bearish session (SPY < VWAP AND SPY down >{self.spy_min_move_pct}% from open):",
            f"  SHORT entry: stock price crosses FROM ABOVE to BELOW its own VWAP",
            *([] if self.rs_confirm_pct == 0 else
              [f"  RS confirmation: stock must also outperform SPY by ≥{self.rs_confirm_pct}% from open"]),
            f"Stop loss: {self.stop_pct}% from VWAP at entry",
            *([] if self.profit_target_pct == 0 else
              [f"Profit target: {self.profit_target_pct}% from entry"]),
            f"Direction: {self.direction}",
            f"Entry window: 9:45 ET → {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def _update_vwap(self, state: dict, bar: Bar, today) -> None:
        """Update VWAP accumulator, reset on new day."""
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

        # Session direction flags
        spy_bullish = (spy_price is not None and spy_vwap is not None
                       and spy_price > spy_vwap
                       and spy_return_pct is not None
                       and spy_return_pct > self.spy_min_move_pct)
        spy_bearish = (spy_price is not None and spy_vwap is not None
                       and spy_price < spy_vwap
                       and spy_return_pct is not None
                       and spy_return_pct < -self.spy_min_move_pct)

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
                old = st.copy()
                st.update(self._fresh_sym())
                st["current_date"] = today

            # Update this stock's VWAP
            self._update_vwap(st, bar, today)
            stock_vwap = st["vwap"]
            prev_close = st["prev_close"]
            close = bar.close

            # ── Manage open position ─────────────────────────────────────────
            pos = portfolio.get_position(symbol)
            qty = pos.quantity if pos else 0

            if qty > 0:  # long
                if st["stop_level"] is not None and close <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAPcross long stop {close:.2f}<={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and close >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAPcross long TP {close:.2f}>={st['take_profit']:.2f}"))
                st["prev_close"] = close
                continue

            if qty < 0:  # short
                if st["stop_level"] is not None and close >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAPcross short stop {close:.2f}>={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and close <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"VWAPcross short TP {close:.2f}<={st['take_profit']:.2f}"))
                st["prev_close"] = close
                continue

            # ── Entry logic ──────────────────────────────────────────────────
            if (st["traded_today"]
                    or et.hour >= self.entry_end_hour
                    or stock_vwap is None
                    or prev_close is None):
                st["prev_close"] = close
                continue

            # Warm-up: need 15 minutes of session before entering
            open_mins = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
            bar_mins = et.hour * 60 + et.minute
            if bar_mins < open_mins + WARMUP_MINUTES:
                st["prev_close"] = close
                continue

            allow_long  = self.direction in ("both", "long_only")
            allow_short = self.direction in ("both", "short_only")

            # RS confirmation filter (optional)
            rs: Optional[float] = None
            if self.rs_confirm_pct > 0 and spy_return_pct is not None and st["day_open"]:
                stock_ret = (close - st["day_open"]) / st["day_open"] * 100
                rs = stock_ret - spy_return_pct

            rs_ok_long  = (self.rs_confirm_pct == 0
                           or (rs is not None and rs >= self.rs_confirm_pct))
            rs_ok_short = (self.rs_confirm_pct == 0
                           or (rs is not None and rs <= -self.rs_confirm_pct))

            # LONG: price crosses from below → above stock VWAP on bullish session
            long_cross = prev_close < stock_vwap and close >= stock_vwap
            if long_cross and spy_bullish and allow_long and rs_ok_long:
                stop = close * (1 - self.stop_pct / 100)
                tp = (close * (1 + self.profit_target_pct / 100)
                      if self.profit_target_pct > 0 else None)
                st["traded_today"] = True
                st["stop_level"] = stop
                st["take_profit"] = tp
                signals.append(Signal(symbol, Direction.LONG,
                                      reason=f"VWAP cross long {close:.2f} VWAP={stock_vwap:.2f}"))
                st["prev_close"] = close
                continue

            # SHORT: price crosses from above → below stock VWAP on bearish session
            short_cross = prev_close > stock_vwap and close <= stock_vwap
            if short_cross and spy_bearish and allow_short and rs_ok_short:
                stop = close * (1 + self.stop_pct / 100)
                tp = (close * (1 - self.profit_target_pct / 100)
                      if self.profit_target_pct > 0 else None)
                st["traded_today"] = True
                st["stop_level"] = stop
                st["take_profit"] = tp
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"VWAP cross short {close:.2f} VWAP={stock_vwap:.2f}"))

            st["prev_close"] = close

        return signals
