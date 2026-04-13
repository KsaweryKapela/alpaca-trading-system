"""SPY Intraday Mean-Reversion Strategy.

NEW STRATEGY FAMILY — tests a genuinely unexplored edge.

THESIS: When SPY drops significantly intraday (>threshold%), it tends to
revert toward the mean by close. This is mean-reversion on the INDEX,
not individual stocks (which was already proven to fail).

WHY THIS IS DIFFERENT:
  - Previous intraday strategies tested MOMENTUM (first 30min predicts rest)
    → failed because individual stocks mean-revert, not continue.
  - Previous REVERSION strategies tested individual stocks → failed because
    too much idiosyncratic noise.
  - SPY is different: it represents aggregate market sentiment. Intraday
    oversells tend to be bought by institutional dip-buyers. This is
    documented in market microstructure literature.

STRUCTURE:
  LONG SIGNAL: SPY drops >dip_threshold% from open by check_time
    - Buy SPY and/or QQQ
    - Hold until 15:25 ET (close-of-day exit)
    - Stop: dip_threshold × stop_mult below entry

  SHORT SIGNAL (optional): SPY rallies >rally_threshold% by check_time
    - Short SPY (fading the overextension)

  Can be COMBINED with v10 overnight sleeve as a separate intraday overlay.

INTRADAY ONLY: uses EOD flatten at 15:55.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")


class SPYReversionStrategy(Strategy):
    name = "spy_reversion"
    label = "SPY Intraday Mean-Reversion"

    def __init__(
        self,
        symbols: List[str],
        # Dip-buy parameters
        dip_threshold: float = 0.5,      # SPY must drop this % from open
        check_after_min: int = 60,       # earliest check (10:30 if 60min after open)
        check_end_hour: int = 14,        # latest check
        stop_mult: float = 1.5,          # stop at entry - dip_threshold * stop_mult
        exit_hour: int = 15,
        exit_minute: int = 25,
        # Which symbols to trade
        trade_spy: bool = True,
        trade_qqq: bool = True,
        trade_stocks: bool = False,      # also buy stocks on SPY dip signal?
        stocks_top_k: int = 3,           # if trading stocks, how many
        # Direction
        direction: str = "long_only",    # "long_only", "short_only", "both"
        rally_threshold: float = 0.8,    # SPY must rally this % for short
        # Require VWAP confirmation
        require_below_vwap: bool = True, # for longs: SPY must be below VWAP
    ) -> None:
        super().__init__(symbols)
        self.dip_threshold = dip_threshold
        self.check_after_min = check_after_min
        self.check_end_hour = check_end_hour
        self.stop_mult = stop_mult
        self.exit_hour = exit_hour
        self.exit_minute = exit_minute
        self.trade_spy = trade_spy
        self.trade_qqq = trade_qqq
        self.trade_stocks = trade_stocks
        self.stocks_top_k = stocks_top_k
        self.direction = direction
        self.rally_threshold = rally_threshold
        self.require_below_vwap = require_below_vwap

        self._spy: dict = {}
        self._traded_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
        }
        self._traded_today = None

    def rules(self) -> List[str]:
        r = [
            f"LONG when SPY drops >{self.dip_threshold}% from open",
            f"Check window: {self.check_after_min}min after open → {self.check_end_hour}:00",
            f"Stop: {self.stop_mult}× dip below entry",
            f"Exit: {self.exit_hour}:{self.exit_minute:02d} ET",
        ]
        if self.require_below_vwap:
            r.append("Require SPY below VWAP for long entry")
        targets = []
        if self.trade_spy:
            targets.append("SPY")
        if self.trade_qqq:
            targets.append("QQQ")
        if self.trade_stocks:
            targets.append(f"top-{self.stocks_top_k} dip stocks")
        r.append(f"Trade: {', '.join(targets)}")
        return r

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0
            spy["vwap_den"] = 0.0
            spy["vwap"] = None
            self._traded_today = None

        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

        spy_price = spy_bar.close
        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30
        exit_mins = self.exit_hour * 60 + self.exit_minute

        if not spy["day_open"] or spy["day_open"] <= 0:
            return signals

        spy_return = (spy_price - spy["day_open"]) / spy["day_open"] * 100

        # ── EXIT existing positions ──────────────────────────────────────
        for sym in list(self.symbols):
            pos = portfolio.get_position(sym)
            if not pos or pos.quantity == 0:
                continue
            bar = bars.get(sym)
            if bar is None:
                continue
            price = bar.close

            # Time exit
            if bar_mins >= exit_mins:
                signals.append(Signal(sym, Direction.FLAT, reason="sr exit"))
                continue

        # ── ENTRY ────────────────────────────────────────────────────────
        if self._traded_today == spy_today:
            return signals
        if bar_mins < open_mins + self.check_after_min:
            return signals
        if et_spy.hour >= self.check_end_hour:
            return signals

        # LONG: SPY dropped enough
        if self.direction in ("long_only", "both") and spy_return < -self.dip_threshold:
            if self.require_below_vwap and spy["vwap"] and spy_price >= spy["vwap"]:
                return signals  # not below VWAP, skip

            self._traded_today = spy_today

            if self.trade_spy:
                pos = portfolio.get_position("SPY")
                if not pos or pos.quantity == 0:
                    signals.append(Signal("SPY", Direction.LONG, reason=f"sr dip {spy_return:.1f}%"))

            if self.trade_qqq and "QQQ" in bars:
                pos = portfolio.get_position("QQQ")
                if not pos or pos.quantity == 0:
                    signals.append(Signal("QQQ", Direction.LONG, reason=f"sr dip {spy_return:.1f}%"))

        # SHORT: SPY rallied too much (optional)
        elif self.direction in ("short_only", "both") and spy_return > self.rally_threshold:
            if self.require_below_vwap:
                # For shorts, require ABOVE VWAP
                if spy["vwap"] and spy_price <= spy["vwap"]:
                    return signals

            self._traded_today = spy_today

            if self.trade_spy:
                pos = portfolio.get_position("SPY")
                if not pos or pos.quantity == 0:
                    signals.append(Signal("SPY", Direction.SHORT, reason=f"sr rally {spy_return:.1f}%"))

        return signals
