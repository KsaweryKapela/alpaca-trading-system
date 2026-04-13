"""EMA Trend Pullback — intraday trend-following on 1m bars.

Hypothesis:
  When the fast EMA (9) is above/below the slow EMA (21), the intraday trend
  is established. Wait for price to pull back to the fast EMA, then enter in
  the trend direction. This exploits the tendency of trending moves to
  consolidate and resume.

Rules:
  1. Compute 9-period and 21-period EMA on 1m closes (rolling, not reset daily).
  2. Trend = BULL when EMA9 > EMA21; BEAR when EMA9 < EMA21.
  3. LONG entry: trend is BULL AND bar close crosses UP through EMA9
     (i.e., prev_close < prev_ema9 and close >= ema9).
  4. SHORT entry: trend is BEAR AND bar close crosses DOWN through EMA9
     (i.e., prev_close > prev_ema9 and close <= ema9).
  5. Stop loss: stop_pct% from entry in the wrong direction.
  6. Profit target: profit_mult × stop_distance from entry.
  7. Only one trade per asset per day — no re-entry after any exit.
  8. No new entries before 9:45 ET (allow EMAs to warm up for the day).
  9. No new entries after entry_end_hour (default 14:00 ET).
  10. EOD flatten by engine at 15:55 ET.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
# Minimum bars before allowing entries (warm-up period, in minutes past open)
MIN_MINUTES_IN_SESSION = 15


class EMATrendStrategy(Strategy):
    """Intraday EMA trend-following with pullback entries."""

    name = "ema_trend"
    label = "EMA Trend Pullback"

    def __init__(
        self,
        symbols: List[str],
        fast_period: int = 9,
        slow_period: int = 21,
        stop_pct: float = 0.3,
        profit_mult: float = 2.0,
        entry_end_hour: int = 14,
        direction: str = "both",       # "both" | "long_only" | "short_only"
        regime_filter: bool = False,   # gate direction by SPY VWAP (long only when SPY bullish, etc.)
    ) -> None:
        super().__init__(symbols)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.stop_pct = stop_pct
        self.profit_mult = profit_mult
        self.entry_end_hour = entry_end_hour
        self.direction = direction
        self.regime_filter = regime_filter

        # Per-symbol EMA state (persists across days — EMAs are continuous)
        self._ema_fast: Dict[str, Optional[float]] = {}
        self._ema_slow: Dict[str, Optional[float]] = {}
        self._prev_close: Dict[str, Optional[float]] = {}
        self._prev_ema_fast: Dict[str, Optional[float]] = {}
        self._bars_seen: Dict[str, int] = {}

        # Per-symbol daily state (reset each day)
        self._daily: Dict[str, dict] = {}

        # SPY VWAP state for regime filter
        self._spy_vwap_state: dict = {"current_date": None, "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None}

    def on_start(self) -> None:
        for sym in self.symbols:
            self._ema_fast[sym] = None
            self._ema_slow[sym] = None
            self._prev_close[sym] = None
            self._prev_ema_fast[sym] = None
            self._bars_seen[sym] = 0
            self._daily[sym] = self._fresh_day()
        self._spy_vwap_state = {"current_date": None, "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "traded_today": False,
            "entry_price": None,
            "take_profit": None,
            "stop_level": None,
            "position_side": None,
            "bars_in_session": 0,
        }

    @staticmethod
    def _ema_update(prev_ema: Optional[float], price: float, period: int) -> float:
        k = 2.0 / (period + 1)
        if prev_ema is None:
            return price
        return price * k + prev_ema * (1 - k)

    def rules(self) -> List[str]:
        dir_rule = {
            "both": "Trade LONG on bullish EMA pullback AND SHORT on bearish EMA pullback",
            "long_only": "Trade LONG pullbacks only (EMA9 > EMA21 required)",
            "short_only": "Trade SHORT pullbacks only (EMA9 < EMA21 required)",
        }.get(self.direction, f"Direction: {self.direction}")
        return [
            f"Trend filter: EMA{self.fast_period} vs EMA{self.slow_period} on 1m bars (continuous)",
            dir_rule,
            f"LONG entry: EMA9 > EMA21 AND close crosses up through EMA9 (pullback bounce)",
            f"SHORT entry: EMA9 < EMA21 AND close crosses down through EMA9 (pullback rejection)",
            f"Stop loss: {self.stop_pct}% from entry",
            f"Profit target: {self.profit_mult}× stop distance ({self.stop_pct * self.profit_mult:.2f}% from entry)",
            f"No new entries before 9:45 ET (warm-up) or after {self.entry_end_hour}:00 ET",
            f"One trade per asset per day — no re-entry",
            f"EOD flatten at 15:55 ET by engine",
        ]

    def _update_spy_vwap(self, bars: Dict[str, Bar]) -> Optional[float]:
        """Track SPY VWAP for the regime filter. Returns current SPY price or None."""
        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return None
        et = spy_bar.timestamp.astimezone(ET) if hasattr(spy_bar.timestamp, "astimezone") else spy_bar.timestamp
        today = et.date()
        sv = self._spy_vwap_state
        if sv["current_date"] != today:
            sv["current_date"] = today
            sv["vwap_num"] = 0.0
            sv["vwap_den"] = 0.0
            sv["vwap"] = None
        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        sv["vwap_num"] += typical * spy_bar.volume
        sv["vwap_den"] += spy_bar.volume
        if sv["vwap_den"] > 0:
            sv["vwap"] = sv["vwap_num"] / sv["vwap_den"]
        return spy_bar.close

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # Compute SPY VWAP for regime filter
        spy_price = self._update_spy_vwap(bars) if self.regime_filter else None
        spy_vwap = self._spy_vwap_state["vwap"]
        spy_bullish = spy_price is not None and spy_vwap is not None and spy_price > spy_vwap
        spy_bearish = spy_price is not None and spy_vwap is not None and spy_price < spy_vwap

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET) if hasattr(ts, "astimezone") else ts

            # Skip pre/post-market
            if not (et.hour > MARKET_OPEN_HOUR or (et.hour == MARKET_OPEN_HOUR and et.minute >= MARKET_OPEN_MIN)):
                continue
            if et.hour >= 16:
                continue

            today = et.date()
            daily = self._daily[symbol]

            # Reset daily state on new day
            if daily["current_date"] != today:
                daily.update(self._fresh_day())
                daily["current_date"] = today

            close = bar.close
            daily["bars_in_session"] += 1

            # Update EMAs (continuous, not reset daily)
            prev_ema_fast = self._ema_fast[symbol]
            self._ema_fast[symbol] = self._ema_update(self._ema_fast[symbol], close, self.fast_period)
            self._ema_slow[symbol] = self._ema_update(self._ema_slow[symbol], close, self.slow_period)
            self._bars_seen[symbol] += 1

            ema_fast = self._ema_fast[symbol]
            ema_slow = self._ema_slow[symbol]
            prev_close = self._prev_close[symbol]

            # Manage open position
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            if current_qty > 0:  # long position
                if daily["stop_level"] is not None and bar.close <= daily["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"EMA long stop {bar.close:.2f}<={daily['stop_level']:.2f}"))
                elif daily["take_profit"] is not None and bar.close >= daily["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"EMA long TP {bar.close:.2f}>={daily['take_profit']:.2f}"))
            elif current_qty < 0:  # short position
                if daily["stop_level"] is not None and bar.close >= daily["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"EMA short stop {bar.close:.2f}>={daily['stop_level']:.2f}"))
                elif daily["take_profit"] is not None and bar.close <= daily["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"EMA short TP {bar.close:.2f}<={daily['take_profit']:.2f}"))

            # Entry logic — only if not yet traded today
            elif not daily["traded_today"]:
                # Need warm-up: at least slow_period bars seen + 15 min in session
                enough_history = self._bars_seen[symbol] >= self.slow_period
                past_warmup = daily["bars_in_session"] >= MIN_MINUTES_IN_SESSION
                before_cutoff = et.hour < self.entry_end_hour

                if (enough_history and past_warmup and before_cutoff
                        and prev_close is not None and prev_ema_fast is not None):

                    bull_trend = ema_fast > ema_slow
                    bear_trend = ema_fast < ema_slow

                    # LONG: pullback into EMA9 in an uptrend
                    # prev close was BELOW ema_fast (pulling back), now close crossed ABOVE
                    long_cross = prev_close < prev_ema_fast and close >= ema_fast
                    # SHORT: rejection off EMA9 in a downtrend
                    short_cross = prev_close > prev_ema_fast and close <= ema_fast

                    allow_long  = self.direction in ("both", "long_only")
                    allow_short = self.direction in ("both", "short_only")
                    if self.regime_filter:
                        allow_long  = allow_long  and spy_bullish
                        allow_short = allow_short and spy_bearish

                    if bull_trend and long_cross and allow_long:
                        stop = close * (1 - self.stop_pct / 100)
                        tp = close + (close - stop) * self.profit_mult
                        daily["traded_today"] = True
                        daily["entry_price"] = close
                        daily["stop_level"] = stop
                        daily["take_profit"] = tp
                        daily["position_side"] = "long"
                        signals.append(Signal(symbol, Direction.LONG,
                                              reason=f"EMA bull pullback {close:.2f} EMA9={ema_fast:.2f}>EMA21={ema_slow:.2f}"))

                    elif bear_trend and short_cross and allow_short:
                        stop = close * (1 + self.stop_pct / 100)
                        tp = close - (stop - close) * self.profit_mult
                        daily["traded_today"] = True
                        daily["entry_price"] = close
                        daily["stop_level"] = stop
                        daily["take_profit"] = tp
                        daily["position_side"] = "short"
                        signals.append(Signal(symbol, Direction.SHORT,
                                              reason=f"EMA bear pullback {close:.2f} EMA9={ema_fast:.2f}<EMA21={ema_slow:.2f}"))

            # Track prev values for crossover detection
            self._prev_close[symbol] = close
            self._prev_ema_fast[symbol] = ema_fast

        return signals
