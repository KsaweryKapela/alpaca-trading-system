# CLAUDE.md — Strategy Research Operating Manual

This file defines how Claude works in this repo.  
The research loop is driven by Claude. The frontend is a viewer for completed results.  
Read this at the start of every session to know where to pick up.

---

## 1. Current State

> **Update this section at the end of every session.**

- **Last session:** Runs 002–013 completed (2026-04-10). 13 total experiments.
- **Best result:** 010_gap_dn_only — Sharpe −0.15, PF 0.97 — near-breakeven, not promising yet.
- **Phase:** Iteration — gap fill signal identified, needs WR filter to cross profitability.
- **Strategy family:** Gap Fill (`gap_fill`), down_only, min_gap=0.5%, stop_mult=0.5, full fill.
- **Key learning:** Jan-Apr 2026 is downtrending. VWAP reversion/momentum fail. Gap-down 
  fades (long into bearish opens) are the only signal with near-zero expectancy so far.
- **Next action:** Improve WR filter on 010 config. Options:
  1. Volume spike confirmation (high relative volume gap-down = panic = bounces more)
  2. Idiosyncratic filter (only trade when SPY is NOT also gapping down)
  3. Try opening range expansion at 10:00 ET instead of gap fill

---

## 2. The Research Loop

Each cycle follows these steps in order:

```
1. RESEARCH → What did the previous run teach us? What failed and why?
               Synthesise findings before picking anything new.
               Check key assumptions (trend regime, session volatility, stop placement).

2. PICK     → Choose one strategy. Write the hypothesis BEFORE touching code.
              Log it immediately in the run note and STATUS.md.

3. BUILD    → Implement or adapt the minimum code needed. One new strategy file
              in trading/strategy/ if required. Do not touch the engine or existing
              strategies unless there's a verified bug.

4. TEST     → Run the experiment:
              .venv/bin/python run_experiment.py \
                --strategy <id> \
                --symbols SPY QQQ AAPL MSFT NVDA \
                [--start 2026-01-01] [--end 2026-04-10] \
                --interval 1m \
                --data-source alpaca \
                --slug NNN_<name>

              Always test on at least 5 symbols (mix of ETFs + large-caps).
              Always use 1m bars. Always use the Jan–Apr 2026 window.

5. FIX      → If there's a bug in execution, data, or metrics — fix it now.
              Log the issue, root cause, and fix before continuing.

6. EVAL     → Score the result against the candidate criteria below.
              Review ALL metrics. Check that all trades are intraday (no overnight).

7. DECIDE   → Reject / Revise / Mark as promising.
              Update STATUS.md. Fill in the decision in the run note.

8. REPEAT   → Back to step 1.
```

---

## 3. How to Run an Experiment

```bash
.venv/bin/python run_experiment.py \
  --strategy orb \
  --symbols SPY QQQ AAPL MSFT NVDA \
  --slug 001_orb \
  --start 2026-01-01 \
  --end 2026-04-10 \
  --interval 1m \
  --data-source alpaca \
  --range-minutes 15 \
  --stop-pct 0.5
```

After the run:
1. The report is saved to `experiments/reports/001_orb.json` (read by frontend)
2. A pre-filled run note template is created at `experiments/runs/001_orb.md`
3. `experiments/STATUS.md` is updated

**Claude must then:**
- Fill in the Hypothesis section (before the run, if possible)
- Fill in the Evaluation section
- Fill in the Decision section
- Update the `--status` flag and re-run to persist the decision in the JSON:
  ```bash
  .venv/bin/python run_experiment.py --slug 001_orb --status rejected ...
  ```

---

## 4. Mandatory Constraints (Non-Negotiable)

| Rule | Detail |
|---|---|
| **1m bars only** | All experiments use `--interval 1m` |
| **Intraday only** | Every trade must open and close on the same day |
| **EOD flatten** | Engine auto-flattens all positions at 15:55 ET — do not rely on strategies to flatten manually |
| **Multi-asset** | Always test on ≥ 5 symbols: mix of ETFs (SPY, QQQ) and large-caps (AAPL, MSFT, NVDA) |
| **Jan–Apr 2026** | Primary evaluation window — always use `--start 2026-01-01` |
| **Alpaca data** | Use `--data-source alpaca` — bar cache prevents repeated fetches |

---

## 5. Candidate Criteria (Backtest → Promising)

A strategy must meet **all** before being marked promising:

| Metric | Target |
|---|---|
| Monthly return | ≥ 2% (approaching ~5% target) |
| Total return (3-month) | Positive |
| Sharpe ratio (daily, √252) | ≥ 0.5 |
| Max drawdown | ≤ 20% |
| Round trips | ≥ 30 (meaningful sample) |
| Win rate | ≥ 40% |
| Profit factor | ≥ 1.5 |
| Expectancy | Positive |
| Max consecutive losses | ≤ 6 |
| Symbols | ≥ 5 tested, results consistent across them |
| Intraday check | avg_trade_duration < 6 hours; zero overnight holds |

---

## 6. Adding a New Strategy

1. Create `trading/strategy/<name>.py`, subclass `Strategy`
2. Implement `on_bar(bars, portfolio) → List[Signal]` and `rules() → List[str]`
3. Add `name` and `label` class attributes
4. Register in `trading/strategy/__init__.py` under `STRATEGIES`
5. The strategy will be available to `run_experiment.py` immediately

**Signals:** `Direction.LONG`, `Direction.SHORT`, `Direction.FLAT` (close position).  
**EOD flatten:** The engine handles this at 15:55 ET. Strategies do NOT need to do it.  
**Short positions:** Fully supported — risk manager and portfolio handle margin accounting.  
**Leverage:** Pass `--leverage N` to `run_experiment.py`.

---

## 7. Folder Structure

```
trading/
├── run_experiment.py           ← Claude runs experiments here
├── server.py                   ← Frontend server (read-only viewer)
├── bar_cache/                  ← Parquet cache (1m + 1d bars)
├── experiments/
│   ├── runs/                   ← Markdown run notes (001_orb.md, ...)
│   ├── reports/                ← JSON reports consumed by frontend
│   └── STATUS.md               ← Current state snapshot
└── trading/
    ├── config.py               ← Universe, eval window, config
    ├── models.py               ← Bar, Signal, Order, Position
    ├── portfolio.py            ← Long + short position accounting
    ├── risk.py                 ← RiskManager (sizing, leverage)
    ├── data/
    │   ├── cache.py            ← Parquet cache
    │   └── historical.py       ← Alpaca + yfinance loaders
    ├── engine/
    │   └── backtest.py         ← BacktestEngine (EOD flatten built-in)
    ├── execution/
    │   └── simulated.py        ← Fill simulator
    └── strategy/
        ├── base.py             ← Abstract Strategy
        ├── orb.py              ← Opening Range Breakout
        └── vwap_reversion.py   ← VWAP Mean Reversion
```

---

## 8. Run Note Naming

Files: `NNN_<short_name>.md` and `NNN_<short_name>.json`  
Examples: `002_vwap.md`, `003_orb_revised.md`  
Auto-numbering: `run_experiment.py` auto-increments if `--slug` is omitted.

---

## 9. Data Source & Cache

- **Alpaca free IEX feed** — 1m history covering ~2024-2026. Sufficient for the Jan–Apr 2026 window.
- **Bar cache:** `bar_cache/{SYMBOL}_{interval}.parquet` — fetched once, reused on all subsequent runs.
- **Delete a .parquet file** to force a fresh API fetch.
- **Credentials:** `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`.

---

## 10. Asset Universe

**ETFs:** SPY, QQQ, IWM, XLF, XLE, XLK  
**Stocks:** AAPL, MSFT, NVDA, AMZN, META  
Defined in `trading/config.py`. Always test on a mix; never test one symbol alone.

---

## 11. Frontend (Viewer Only)

The frontend shows **completed experiment results only**.  
Start it with: `.venv/bin/python server.py` → `http://localhost:5000`

It does NOT trigger backtests. Claude runs experiments; the frontend reads the results.

Frontend features:
- Experiment list with status, metrics summary
- Click to view: rules, metrics, calendar (with hover for per-day details), transactions
- Asset filter: filter the displayed transactions/calendar by asset from the completed run

---

## 12. Scope

In scope: strategy research, backtesting, experiment logging, results viewing.  
Out of scope: live trading, paper trading, walk-forward (add if needed later).
