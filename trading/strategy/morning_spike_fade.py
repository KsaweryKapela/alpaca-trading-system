"""Morning Spike Fade — short overbought morning runners for mean reversion.

Hypothesis:
  Stocks up strongly in the first 15-30 minutes of trading tend to
  reverse during the remainder of the session. This is confirmed by
  runs 070-080 where ITM longs (buying morning runners) had WR 40-47%.
  Flipping the logic: SHORT the morning spike for mean reversion.

  In a bull market (2025), there are MORE morning spikes → more fade
  opportunities. In a bear market (2026), spikes are rarer but fade
  harder when they occur.

  Key filter: only fade spikes on stocks that are EXTENDED beyond VWAP.
  A stock above VWAP that has run up >X% from open is overextended —
  the institutional VWAP buyers are not supporting this level.

Rules:
  1. Track each stock's return from day open and its VWAP.
  2. Entry window: entry_after_min to entry_end_hour ET.
  3. SHORT when: stock return from open > +spike_pct%
     AND stock price > VWAP (overextended above institutional fair value)
  4. LONG when: stock return from open < -spike_pct%
     AND stock price < VWAP (oversold below institutional fair value)
  5. Stop: stop_pct% from entry.
  6. Target: target_pct% from entry (fade back toward VWAP).
  7. Direction filter: both, short_only, long_only.
  8. Optional: SPY regime filter — only fade bull spikes on bull days,
     bear spikes on bear days (fade WITH the regime, not against it).
  9. One trade per symbol per day.
 10. EOD flatten at 15:55 ET.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class MorningSpikeFadeStrategy(Strategy):
    name = "morning_spike_fade"
    label = "Morning Spike Fade (mean reversion)"

    def __init__(
        self,
        symbols: List[str],
        spike_pct: float = 1.0,          # stock must be up/down this % from open
        stop_pct: float = 1.0,           # stop from entry
        target_pct: float = 1.5,         # target from entry (fade toward VWAP)
        direction: str = "both",         # "both" | "short_only" | "long_only"
        require_vwap_extended: bool = True,  # stock must be beyond VWAP in direction of spike
        regime_filter: bool = False,     # SPY VWAP regime filter
        entry_after_min: int = 15,       # wait after open
        entry_end_hour: int = 12,        # no entries after this (fade works best morning)
    ) -> None:
        super().__init__(symbols)
        self.spike_pct = spike_pct
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.direction = direction
        self.require_vwap_extended = require_vwap_extended
        self.regime_filter = regime_filter
        self.entry_after_min = entry_after_min
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
        vwap_note = "Stock must be beyond VWAP in spike direction" if self.require_vwap_extended else "No VWAP extension required"
        regime_note = "SPY VWAP regime filter active" if self.regime_filter else "No regime filter"
        return [
            f"Track each stock's % return from day open + per-stock VWAP",
            f"SHORT when stock return > +{self.spike_pct}% from open (overextended spike)",
            f"LONG when stock return < -{self.spike_pct}% from open (oversold fade)",
            f"{vwap_note}",
            f"Stop loss: {self.stop_pct}% from entry",
            f"Profit target: {self.target_pct}% from entry (fade toward VWAP)",
            f"Direction: {self.direction}",
            f"{regime_note}",
            f"Entry window: {self.entry_after_min} min after open → {self.entry_end_hour}:00 ET",
            f"One trade per symbol per day",
            f"EOD flatten at 15:55 ET",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        # SPY regime
        spy_bar = bars.get("SPY")
        spy_bullish = False
        spy_bearish = False

        if spy_bar is not None:
            et_spy = spy_bar.timestamp.astimezone(ET)
            spy_today = et_spy.date()
            spy = self._spy_state

            if spy["current_date"] != spy_today:
                spy["current_date"] = spy_today
                spy["day_open"] = spy_bar.open
                spy["vwap_num"] = 0.0
                spy["vwap_den"] = 0.0
                spy["vwap"] = None

            typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
            spy["vwap_num"] += typical * spy_bar.volume
            spy["vwap_den"] += spy_bar.volume
            if spy["vwap_den"] > 0:
                spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

            if spy["vwap"] is not None:
                spy_bullish = spy_bar.close > spy["vwap"]
                spy_bearish = spy_bar.close < spy["vwap"]

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
                st["vwap_num"] = 0.0
                st["vwap_den"] = 0.0
                st["vwap"] = None
                st["traded_today"] = False
                st["stop_level"] = None
                st["take_profit"] = None

            # Update per-stock VWAP
            typical = (bar.high + bar.low + bar.close) / 3
            st["vwap_num"] += typical * bar.volume
            st["vwap_den"] += bar.volume
            if st["vwap_den"] > 0:
                st["vwap"] = st["vwap_num"] / st["vwap_den"]

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open positions
            if current_qty > 0:
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fade long stop"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fade long target"))
                continue

            if current_qty < 0:
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fade short stop"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="fade short target"))
                continue

            # Entry gates
            bar_mins = et.hour * 60 + et.minute
            open_mins = 9 * 60 + 30
            if bar_mins < open_mins + self.entry_after_min:
                continue
            if et.hour >= self.entry_end_hour:
                continue
            if st["traded_today"]:
                continue
            if st["day_open"] is None or st["day_open"] == 0:
                continue

            return_pct = (price - st["day_open"]) / st["day_open"] * 100
            vwap = st["vwap"]

            allow_short_fade = self.direction in ("both", "short_only")
            allow_long_fade = self.direction in ("both", "long_only")

            if self.regime_filter:
                # Fade WITH regime: short overbought on BULL days, long oversold on BEAR days
                allow_short_fade = allow_short_fade and spy_bullish
                allow_long_fade = allow_long_fade and spy_bearish

            # SHORT FADE: stock spiked UP beyond threshold → fade back down
            if return_pct > self.spike_pct and allow_short_fade:
                vwap_ok = (vwap is not None and price > vwap) if self.require_vwap_extended else True
                if vwap_ok:
                    st["traded_today"] = True
                    st["stop_level"] = price * (1 + self.stop_pct / 100)
                    st["take_profit"] = price * (1 - self.target_pct / 100)
                    signals.append(Signal(
                        symbol, Direction.SHORT,
                        reason=f"spike fade: +{return_pct:.1f}% > VWAP, shorting"
                    ))

            # LONG FADE: stock spiked DOWN beyond threshold → fade back up
            elif return_pct < -self.spike_pct and allow_long_fade:
                vwap_ok = (vwap is not None and price < vwap) if self.require_vwap_extended else True
                if vwap_ok:
                    st["traded_today"] = True
                    st["stop_level"] = price * (1 - self.stop_pct / 100)
                    st["take_profit"] = price * (1 + self.target_pct / 100)
                    signals.append(Signal(
                        symbol, Direction.LONG,
                        reason=f"spike fade: {return_pct:.1f}% < VWAP, buying dip"
                    ))

        return signals
