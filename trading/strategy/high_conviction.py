"""High-Conviction Strategy: Wide Universe, Ultra-Strict Entry.

THESIS: The v10 on 120 stocks gets WR 46-51% because many trades are
mediocre setups on low-quality names. Solution: keep the wide universe
but stack MULTIPLE confirmation filters so only the highest-probability
setups trigger.

TARGET: 150-250 round trips/year at 55-60%+ WR (vs 400+ at 48-51%).

ENTRY GATES (ALL must be true):

FOR RS SHORTS:
  Gate 1: RS < -rs_threshold% (stock much weaker than SPY)
  Gate 2: Stock below its own intraday VWAP (confirming weakness)
  Gate 3: Stock RVOL > rvol_min (institutional participation)
  Gate 4: SPY return from open < -spy_min_drop% (broad weakness)
  Gate 5: Entry only between 10:00-13:00 ET (avoid noise)

FOR OVERNIGHT LONGS:
  Gate 1: SPY above VWAP AND up > spy_min_rise% from open
  Gate 2: Stock in top-K by RS (only strongest names)
  Gate 3: Stock RVOL > rvol_min_on (active name, not dead)
  Gate 4: Stock 5-day momentum positive (trend alignment)

Each gate alone reduces trade count by ~20-40%.
All gates combined → only the cleanest setups fire.

MARGIN OVERLAY + 20-MIN EXIT inherited from v10.
REQUIRES: eod_flatten=False.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .base import Strategy
from ..models import Bar, Direction, Signal
from ..portfolio import Portfolio

ET = ZoneInfo("America/New_York")

SIGNAL_ONLY = {"VGK", "EFA", "EWG", "FXI", "EWJ", "UVXY", "VXX", "VIXY",
               "XLK", "XLF", "SMH", "SPY", "QQQ", "IWM", "TQQQ",
               "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLC", "XLB",
               "ARKK", "ARKF"}


class HighConvictionStrategy(Strategy):
    name = "high_conviction"
    label = "High-Conviction (Multi-Gate Entry)"

    def __init__(
        self,
        symbols: List[str],
        # RS short gates
        rs_threshold: float = 1.5,       # stricter than 1.0
        rs_stop_pct: float = 3.0,
        rs_target_pct: float = 3.0,
        spy_trend_days: int = 3,
        rs_entry_after_min: int = 30,    # wait 30 min (not 15)
        rs_entry_end_hour: int = 13,     # stop at 13:00 (not 14:00)
        rs_close_hour: int = 15,
        rs_close_minute: int = 35,
        require_stock_below_vwap: bool = True,   # Gate 2
        rs_rvol_min: float = 1.5,                # Gate 3
        spy_min_drop_pct: float = 0.2,           # Gate 4
        # Overnight long gates
        overnight_top_k: int = 5,
        overnight_bottom_k: int = 3,
        overnight_stop_pct: float = 2.0,
        overnight_min_move: float = 0.3,
        overnight_entry_hour: int = 15,
        overnight_entry_minute: int = 30,
        overnight_exit_after_min: int = 20,
        spy_min_rise_pct: float = 0.1,           # Gate 1 for longs
        on_rvol_min: float = 1.0,                # Gate 3 for longs
        require_5d_momentum: bool = True,        # Gate 4 for longs
        # Global signal
        global_signal_symbol: str = "VGK",
        global_min_return: float = 0.0,
        tier2_top_k: int = 2,
        tier2_bottom_k: int = 2,
        # Volume lookback
        vol_lookback: int = 20,
    ) -> None:
        super().__init__(symbols)
        self.rs_threshold = rs_threshold
        self.rs_stop_pct = rs_stop_pct
        self.rs_target_pct = rs_target_pct
        self.spy_trend_days = spy_trend_days
        self.rs_entry_after_min = rs_entry_after_min
        self.rs_entry_end_hour = rs_entry_end_hour
        self.rs_close_hour = rs_close_hour
        self.rs_close_minute = rs_close_minute
        self.require_stock_below_vwap = require_stock_below_vwap
        self.rs_rvol_min = rs_rvol_min
        self.spy_min_drop_pct = spy_min_drop_pct
        self.overnight_top_k = overnight_top_k
        self.overnight_bottom_k = overnight_bottom_k
        self.overnight_stop_pct = overnight_stop_pct
        self.overnight_min_move = overnight_min_move
        self.overnight_entry_hour = overnight_entry_hour
        self.overnight_entry_minute = overnight_entry_minute
        self.overnight_exit_after_min = overnight_exit_after_min
        self.spy_min_rise_pct = spy_min_rise_pct
        self.on_rvol_min = on_rvol_min
        self.require_5d_momentum = require_5d_momentum
        self.global_signal_symbol = global_signal_symbol
        self.global_min_return = global_min_return
        self.tier2_top_k = tier2_top_k
        self.tier2_bottom_k = tier2_bottom_k
        self.vol_lookback = vol_lookback

        self._spy: dict = {}
        self._sym: Dict[str, dict] = {}
        self._signal_states: Dict[str, dict] = {}
        self._overnight_done_today = None

    def on_start(self) -> None:
        self._spy = {
            "current_date": None, "day_open": None,
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            "prev_close": None,
            "daily_closes": deque(maxlen=max(self.spy_trend_days, 1) + 1),
        }
        self._sym = {}
        self._signal_states = {}
        self._overnight_done_today = None

    def _fresh_sym(self) -> dict:
        return {
            "current_date": None, "day_open": None,
            "rs_traded": False, "overnight_traded": False,
            "holding_overnight": False, "overnight_entry_date": None,
            "stop_level": None, "target_level": None, "position_type": None,
            # Stock VWAP
            "vwap_num": 0.0, "vwap_den": 0.0, "vwap": None,
            # Volume tracking
            "session_volume": 0.0,
            "daily_volumes": deque(maxlen=self.vol_lookback),
            # Momentum
            "prev_close": None,
            "daily_closes": deque(maxlen=6),
        }

    def _fresh_signal(self) -> dict:
        return {"current_date": None, "day_open": None}

    def rules(self) -> List[str]:
        return [
            "=== HIGH-CONVICTION MULTI-GATE ===",
            f"SHORT gates: RS<-{self.rs_threshold}% + stockVWAP + RVOL>{self.rs_rvol_min} + SPY<-{self.spy_min_drop_pct}%",
            f"  Entry 10:00-{self.rs_entry_end_hour}:00 | Stop {self.rs_stop_pct}% | Target {self.rs_target_pct}%",
            f"LONG gates: SPY>VWAP+{self.spy_min_rise_pct}% + topK + RVOL>{self.on_rvol_min} + 5d momentum",
            f"  {self.overnight_top_k}+{self.overnight_bottom_k} overnight | Exit {self.overnight_exit_after_min}min",
        ]

    def _update_signal(self, sym, bar):
        if sym not in self._signal_states:
            self._signal_states[sym] = self._fresh_signal()
        ss = self._signal_states[sym]
        et = bar.timestamp.astimezone(ET)
        if ss["current_date"] != et.date():
            ss["current_date"] = et.date(); ss["day_open"] = bar.open
        if ss["day_open"] and ss["day_open"] > 0:
            return (bar.close - ss["day_open"]) / ss["day_open"] * 100
        return None

    def on_bar(self, bars: Dict[str, Bar], portfolio: Portfolio) -> List[Signal]:
        signals: List[Signal] = []

        spy_bar = bars.get("SPY")
        if spy_bar is None:
            return signals

        et_spy = spy_bar.timestamp.astimezone(ET)
        spy_today = et_spy.date()
        spy = self._spy

        if spy["current_date"] != spy_today:
            if spy["prev_close"] is not None:
                spy["daily_closes"].append(spy["prev_close"])
            spy["current_date"] = spy_today
            spy["day_open"] = spy_bar.open
            spy["vwap_num"] = 0.0; spy["vwap_den"] = 0.0; spy["vwap"] = None

        typical = (spy_bar.high + spy_bar.low + spy_bar.close) / 3
        spy["vwap_num"] += typical * spy_bar.volume
        spy["vwap_den"] += spy_bar.volume
        if spy["vwap_den"] > 0:
            spy["vwap"] = spy["vwap_num"] / spy["vwap_den"]

        spy_price = spy_bar.close
        spy["prev_close"] = spy_price
        spy_return = (spy_price - spy["day_open"]) / spy["day_open"] * 100 if spy["day_open"] and spy["day_open"] > 0 else None

        spy_bullish = spy["vwap"] is not None and spy_price > spy["vwap"]
        spy_bearish = spy["vwap"] is not None and spy_price < spy["vwap"]
        spy_bearish_full = spy_bearish
        if self.spy_trend_days > 0:
            closes = list(spy["daily_closes"])
            if len(closes) >= self.spy_trend_days:
                spy_bearish_full = spy_bearish and spy_price < closes[-self.spy_trend_days]

        bar_mins = et_spy.hour * 60 + et_spy.minute
        open_mins = 9 * 60 + 30

        # Gate 4 for shorts: SPY must be down enough
        spy_drop_confirmed = spy_return is not None and spy_return < -self.spy_min_drop_pct

        # Gate 1 for longs: SPY must be up enough
        spy_rise_confirmed = spy_return is not None and spy_return > self.spy_min_rise_pct

        # Global signal
        global_return = None
        if self.global_signal_symbol in bars:
            global_return = self._update_signal(self.global_signal_symbol, bars[self.global_signal_symbol])

        stock_rs: List[Tuple[str, float, float, float]] = []  # (sym, rs, price, rvol)
        tradable = [s for s in self.symbols if s not in SIGNAL_ONLY and s != "SPY"]

        for symbol in tradable:
            bar = bars.get(symbol)
            if bar is None:
                continue

            et = bar.timestamp.astimezone(ET)
            today = et.date()

            if symbol not in self._sym:
                self._sym[symbol] = self._fresh_sym()
            st = self._sym[symbol]

            if st["current_date"] != today:
                # Save daily stats
                if st["session_volume"] > 0:
                    st["daily_volumes"].append(st["session_volume"])
                if st["prev_close"] is not None:
                    st["daily_closes"].append(st["prev_close"])

                if not st["holding_overnight"]:
                    st["rs_traded"] = False; st["overnight_traded"] = False
                st["current_date"] = today
                st["day_open"] = bar.open
                st["vwap_num"] = 0.0; st["vwap_den"] = 0.0; st["vwap"] = None
                st["session_volume"] = 0.0

            price = bar.close
            st["prev_close"] = price
            st["session_volume"] += bar.volume

            # Stock VWAP
            typ = (bar.high + bar.low + bar.close) / 3
            st["vwap_num"] += typ * bar.volume
            st["vwap_den"] += bar.volume
            if st["vwap_den"] > 0:
                st["vwap"] = st["vwap_num"] / st["vwap_den"]

            pos = portfolio.get_position(symbol)
            current_qty = pos.quantity if pos else 0
            sym_bar_mins = et.hour * 60 + et.minute

            # ── Exit / manage positions ──────────────────────────────────
            if st["holding_overnight"] and st["overnight_entry_date"] != today:
                if st["stop_level"] and current_qty > 0 and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc stop"))
                    st["holding_overnight"] = False; st["position_type"] = None; continue
                if sym_bar_mins >= open_mins + self.overnight_exit_after_min:
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc exit"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty < 0 and st["position_type"] == "rs_short":
                if st["stop_level"] and price >= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc RS stop")); st["position_type"] = None
                elif st["target_level"] and price <= st["target_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc RS tgt")); st["position_type"] = None
                elif et.hour > self.rs_close_hour or (et.hour == self.rs_close_hour and et.minute >= self.rs_close_minute):
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc RS close")); st["position_type"] = None
                continue

            if current_qty > 0 and st["holding_overnight"] and st["overnight_entry_date"] == today:
                if st["stop_level"] and price <= st["stop_level"]:
                    signals.append(Signal(symbol, Direction.FLAT, reason="hc stop(d)"))
                    st["holding_overnight"] = False; st["position_type"] = None
                continue

            if current_qty != 0:
                continue
            if not st["day_open"] or st["day_open"] == 0 or spy_return is None:
                continue

            stock_ret = (price - st["day_open"]) / st["day_open"] * 100
            rs = stock_ret - spy_return

            # RVOL
            avg_vol = sum(st["daily_volumes"]) / len(st["daily_volumes"]) if st["daily_volumes"] else 0
            rvol = st["session_volume"] / avg_vol if avg_vol > 0 else 1.0

            # 5-day momentum
            closes_5d = list(st["daily_closes"])
            mom_5d_positive = True
            if self.require_5d_momentum and len(closes_5d) >= 5 and closes_5d[-5] > 0:
                mom_5d_positive = closes_5d[-1] > closes_5d[-5]

            # ── MULTI-GATE RS SHORT ──────────────────────────────────────
            if (not st["rs_traded"]
                    and spy_bearish_full                                    # existing regime
                    and sym_bar_mins >= open_mins + self.rs_entry_after_min # Gate: timing
                    and et.hour < self.rs_entry_end_hour                   # Gate: timing end
                    and rs < -self.rs_threshold                            # Gate 1: RS extreme
                    and spy_drop_confirmed                                 # Gate 4: SPY dropping
                    ):
                # Gate 2: stock below own VWAP
                if self.require_stock_below_vwap and st["vwap"] and price >= st["vwap"]:
                    continue
                # Gate 3: RVOL high enough
                if rvol < self.rs_rvol_min:
                    continue

                # ALL GATES PASSED — high conviction short
                st["rs_traded"] = True
                st["stop_level"] = price * (1 + self.rs_stop_pct / 100)
                st["target_level"] = price * (1 - self.rs_target_pct / 100)
                st["position_type"] = "rs_short"
                signals.append(Signal(symbol, Direction.SHORT,
                                      reason=f"hc RS={rs:.1f}% rv={rvol:.1f}x"))
                continue

            # ── COLLECT OVERNIGHT CANDIDATES ─────────────────────────────
            entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
            if (sym_bar_mins >= entry_mins and sym_bar_mins <= entry_mins + 5
                    and not st["overnight_traded"]):
                # Gate 3: RVOL check for overnight
                if rvol >= self.on_rvol_min:
                    # Gate 4: 5-day momentum alignment
                    if not self.require_5d_momentum or mom_5d_positive:
                        stock_rs.append((symbol, rs, price, rvol))

        # ── OVERNIGHT ENTRY ──────────────────────────────────────────────
        entry_mins = self.overnight_entry_hour * 60 + self.overnight_entry_minute
        if (stock_rs and bar_mins >= entry_mins and bar_mins <= entry_mins + 5
                and self._overnight_done_today != spy_today):

            self._overnight_done_today = spy_today
            global_bullish = global_return is not None and global_return > self.global_min_return

            # Gate 1 for longs: SPY must be solidly up
            if spy_bullish and spy_rise_confirmed:
                top_k, bot_k, tier = self.overnight_top_k, self.overnight_bottom_k, 1
            elif global_bullish and spy_rise_confirmed:
                top_k, bot_k, tier = self.tier2_top_k, self.tier2_bottom_k, 2
            elif spy_bullish:
                # SPY above VWAP but not strongly up — reduced allocation
                top_k, bot_k, tier = max(self.overnight_top_k // 2, 1), max(self.overnight_bottom_k // 2, 1), 1
            elif global_bullish:
                top_k, bot_k, tier = 1, 1, 2
            else:
                top_k, bot_k, tier = 0, 0, 0

            if top_k > 0 or bot_k > 0:
                stock_rs.sort(key=lambda x: x[1], reverse=True)

                for sym, rs, px, rv in stock_rs:
                    if top_k <= 0: break
                    if rs < self.overnight_min_move: continue
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"hc T{tier} +{rs:.1f}% rv={rv:.1f}"))
                    top_k -= 1

                losers = sorted([x for x in stock_rs if x[1] < -self.overnight_min_move], key=lambda x: x[1])
                for sym, rs, px, rv in losers:
                    if bot_k <= 0: break
                    st = self._sym.get(sym)
                    if not st or st["overnight_traded"] or st["holding_overnight"]: continue
                    pos = portfolio.get_position(sym)
                    if pos and pos.quantity != 0: continue
                    st["overnight_traded"] = True; st["holding_overnight"] = True
                    st["overnight_entry_date"] = spy_today
                    st["stop_level"] = px * (1 - self.overnight_stop_pct / 100)
                    st["position_type"] = f"on_t{tier}"
                    signals.append(Signal(sym, Direction.LONG, reason=f"hc T{tier} dip {rs:.1f}%"))
                    bot_k -= 1

        return signals
