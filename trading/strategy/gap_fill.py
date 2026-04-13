"""Gap Fill — intraday, same-day close.

Overnight gaps on large-cap stocks and ETFs tend to fill within the session.
When today's open is significantly above/below yesterday's close, fade the gap:
go SHORT into a gap-up open, go LONG into a gap-down open.

Rules:
  1. Track yesterday's close (last bar of prior session).
  2. At market open, compute gap = (today_open − yesterday_close) / yesterday_close.
  3. If gap > +min_gap_pct: go SHORT (fade the gap-up, target yesterday's close).
  4. If gap < −min_gap_pct: go LONG (fade the gap-down, target yesterday's close).
  5. Stop loss at stop_mult × gap_size above entry (wrong-way extension).
  6. Entry only on the first bar of the day.
  7. Profit target: yesterday's close (full gap fill) or max_gap_pct cap.
  8. Only trade gaps smaller than max_gap_pct (avoid earnings/news gaps).
  9. EOD flatten enforced by the engine at 15:55 ET.
"""

from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

# Market hours (ET)
MARKET_OPEN_HOUR, MARKET_OPEN_MIN = 9, 30
MARKET_CLOSE_HOUR, MARKET_CLOSE_MIN = 16, 0


def _is_market_open(et_hour: int, et_min: int) -> bool:
    open_mins  = MARKET_OPEN_HOUR  * 60 + MARKET_OPEN_MIN
    close_mins = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN
    bar_mins   = et_hour * 60 + et_min
    return open_mins <= bar_mins < close_mins


class GapFillStrategy(Strategy):
    name = "gap_fill"
    label = "Gap Fill"

    def __init__(
        self,
        symbols: List[str],
        min_gap_pct: float = 0.3,     # minimum gap to trade (%)
        max_gap_pct: float = 3.0,     # skip runaway gaps > this % (earnings, news)
        stop_mult: float = 0.5,       # stop at stop_mult × gap_size beyond entry
        fill_target_pct: float = 1.0, # take profit at this fraction of gap (1.0 = full fill)
        direction: str = "both",      # "both" | "up_only" (fade gaps up) | "down_only"
    ) -> None:
        super().__init__(symbols)
        self.min_gap_pct = min_gap_pct
        self.max_gap_pct = max_gap_pct
        self.stop_mult = stop_mult
        self.fill_target_pct = fill_target_pct
        self.direction = direction
        self._prev_close: Dict[str, Optional[float]] = {}
        self._state: Dict[str, dict] = {}

    def _fresh_day(self) -> dict:
        return {
            "current_date": None,
            "traded_today": False,
            "entry_price": None,
            "take_profit": None,
            "stop_level": None,
        }

    def on_start(self) -> None:
        self._prev_close = {sym: None for sym in self.symbols}
        self._state = {sym: self._fresh_day() for sym in self.symbols}

    def rules(self) -> List[str]:
        return [
            f"Track yesterday's close for each symbol",
            f"Entry on first bar of day when gap [{self.min_gap_pct}%–{self.max_gap_pct}%]",
            f"Gap UP (open > prev_close + {self.min_gap_pct}%): go SHORT — bet on gap fill",
            f"Gap DOWN (open < prev_close − {self.min_gap_pct}%): go LONG — bet on gap fill",
            f"Profit target: yesterday's close (full gap fill)",
            f"Stop loss: {self.stop_mult}× gap size beyond entry (gap extension)",
            f"Profit target: {int(self.fill_target_pct * 100)}% of gap fill (partial if < 100%)",
        f"Direction filter: {self.direction} (up_only=short only, down_only=long only)",
        f"Skip gaps > {self.max_gap_pct}% (earnings / news events)",
            f"One trade per asset per day — first bar entry only",
            f"All positions closed by 15:55 ET (EOD flatten by engine)",
        ]

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        for symbol in self.symbols:
            bar = bars.get(symbol)
            if bar is None:
                continue

            ts = bar.timestamp
            et = ts.astimezone(ET) if hasattr(ts, "astimezone") else ts

            if not _is_market_open(et.hour, et.minute):
                continue

            today = et.date()
            st = self._state[symbol]

            if st["current_date"] != today:
                st.update(self._fresh_day())
                st["current_date"] = today

            price = bar.close
            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0

            # Manage open position
            if current_qty > 0:   # long (gap-down fade)
                if st["stop_level"] is not None and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap-fill long stop {price:.2f}<={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and price >= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap filled {price:.2f}>={st['take_profit']:.2f}"))
                # Update prev_close even while in position
                self._prev_close[symbol] = price
                continue

            if current_qty < 0:   # short (gap-up fade)
                if st["stop_level"] is not None and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap-fill short stop {price:.2f}>={st['stop_level']:.2f}"))
                elif st["take_profit"] is not None and price <= st["take_profit"]:
                    signals.append(Signal(symbol, Direction.FLAT,
                                          reason=f"gap filled {price:.2f}<={st['take_profit']:.2f}"))
                self._prev_close[symbol] = price
                continue

            # Entry: only on first bar of the day
            prev_close = self._prev_close.get(symbol)
            if not st["traded_today"] and prev_close is not None:
                open_price = bar.open  # use bar open for gap calculation
                gap_pct = (open_price - prev_close) / prev_close * 100

                if (self.min_gap_pct <= gap_pct <= self.max_gap_pct
                        and self.direction in ("both", "up_only")):
                    # Gap UP — short (fade)
                    gap_pts = open_price - prev_close
                    st["traded_today"] = True
                    st["entry_price"] = open_price
                    st["take_profit"] = open_price - gap_pts * self.fill_target_pct
                    st["stop_level"]  = open_price + gap_pts * self.stop_mult
                    signals.append(Signal(symbol, Direction.SHORT,
                                          reason=f"gap_up +{gap_pct:.2f}% fade short"))

                elif (-self.max_gap_pct <= gap_pct <= -self.min_gap_pct
                        and self.direction in ("both", "down_only")):
                    # Gap DOWN — long (fade)
                    gap_pts = prev_close - open_price
                    st["traded_today"] = True
                    st["entry_price"] = open_price
                    st["take_profit"] = open_price + gap_pts * self.fill_target_pct
                    st["stop_level"]  = open_price - gap_pts * self.stop_mult
                    signals.append(Signal(symbol, Direction.LONG,
                                          reason=f"gap_down {gap_pct:.2f}% fade long"))

            # Always update prev_close
            self._prev_close[symbol] = price

        return signals
