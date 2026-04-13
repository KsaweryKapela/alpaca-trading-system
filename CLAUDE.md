# CLAUDE.md — Strategy Research Operating Manual

This file defines how Claude works in this repo.  
The research loop is driven by Claude. The frontend is a viewer for completed results.  
Read this at the start of every session to know where to pick up.

---

## 1. Current State

> **Update this section at the end of every session.**

- **Last session:** Runs 166–231 completed (2026-04-12/13). 65+ runs across v6–v12, gap_context, closing_momentum, spy_reversion, prior_day_levels, dynamic_select, trend_regime strategies.
- **Best result: 217_v10_stop30** → Combined +29.07% (2026: +11.40% Sharpe 3.09, 2025: +17.67% Sharpe 1.35)
- **Phase:** Dynamic stock selection + margin overlay + optimal stop/target. Now testing `dynamic_select` strategy which selects stocks by RVOL/range/gap each morning before applying tactics.

**KEY INNOVATIONS (this session):**
1. **Margin overlay (v10):** Delay RS short close to 15:35 so short proceeds fund more overnight longs at 15:30. +22% swing in 2025.
2. **20-minute exit:** Optimal overnight exit (parabolic curve 10-45min).
3. **3.0% stop / 3.0% target:** 1:1 R:R with 54.5% WR. Wider stop reduces premature stops.
4. **Dynamic stock selection:** New family — score stocks by RVOL + range expansion + gap + momentum, only trade top-N each day.

**10-YEAR VALIDATION WARNING:** The overnight + RS short framework was tested on 2015 S&P top-10 (blue chips) and FAILS catastrophically (-160% over 10 years). The edge is universe-dependent on high-beta tech. This is a known limitation.

**NEW STRATEGIES ADDED:** allweather_v6 through v12, prior_day_levels, closing_momentum, spy_reversion, gap_context, trend_regime, dynamic_select.
**NEW METRICS:** Sortino, Calmar, payoff ratio, avg win/loss, worst day/week, commission drag.

---

### BEAR SLEEVE — SOLVED ✓

**Best candidate: 069_rs_3dfilt_3x**
- Strategy: `relative_strength`, short_only, RS threshold=1.0%, stop=1.0%, TP=2.0%, entry_after_min=15
- Filters: SPY VWAP regime filter + SPY 3-day trend filter (only short when SPY < close 3 days ago)
- Leverage: 3×
- 2026: Sharpe **3.38**, Monthly **2.01%**, Total +8.23%, DD -2.55%, WR 49.5%, PF 1.72 → **PROMISING**
- 2025: +0.23% total (barely positive — regime gating, not bull edge)

**Bear sleeve refinements tested (070–080):**
| Run | Change | 2026/mo | 2025 total | Verdict |
|-----|--------|---------|-----------|---------|
| 069 (base) | 3d filter, 3× | 2.01% | +0.23% | PROMISING |
| 074 combined | + ITM long sleeve | 2.33% | -8.85% | Worse — ITM drags 2025 |
| 076 top-3 signals | max 3/day | 1.23% | -6.02% | Worse 2026, worse 2025 |
| 077 ATR filter | active sessions only | 0.82% | **+1.31%** | Better 2025, worse 2026 |

**077 note**: ATR filter nudges 2025 from +0.23% to +1.31% but drops 2026 from 2.01% to 0.82%/mo. Trade-off is unfavorable at current targets (need ≥2%/mo 2026 AND ≥20% 2025).

---

### BULL SLEEVE — structurally absent at 1m resolution

**Intraday time-series momentum — REFUTED (runs 070–073, 078–080):**
All 7 ITM variants fail:
- 070 (both, all syms): 2026 -1.3%, 2025 -29.9% → catastrophic
- 071 (long_only, all syms): 2026 -2.6%, 2025 -15.0% → catastrophic
- 072 (both, ETF only): 2026 -0.2%, 2025 -3.4% → ETFs slightly less bad
- 073 (long_only, ETF only): 2026 +0.5%, 2025 -2.1% → ETFs best but still losing in 2025

**Root cause:** Stocks and ETFs up +0.3% at 10:00 ET systematically REVERSE for the rest of the day. In 2025 (bull), WR for ITM longs is 40-47% → worse than coin flip. The "first-30min predicts final-30min" academic result may apply at daily/monthly aggregation or to index futures, not to individual stocks at 1m resolution.

**Gap-and-go at 3× (075):** 2026 -0.4%, 2025 -3.0% → rejected. At 3× the negative WR (~37%) compounds losses. 1× had +0.49% in 2025 but that was too small to matter.

**Structural conclusion:** No intraday long strategy has been found that earns ≥2%/mo in 2025. The intraday horizon (9:30–15:55) appears to have a structural short bias — distribution is more profitable than accumulation at 1-minute resolution.

---

### Key learnings (runs 070–080):
- **Intraday momentum is structurally broken for longs**: WR 40-47% across all 7 variants, all time windows (10:00, 10:30), all symbol sets. Stocks that are up at 10:00 tend to reverse. This is mean-reversion, not momentum.
- **Combined RS+ITM is worse than pure RS**: The ITM bull sleeve adds losses in 2025 (-8.85% vs +0.23%), reducing 069's cross-regime positivity. Adding a broken long sleeve degrades the system.
- **ATR expansion filter helps 2025 slightly**: +1.31% vs +0.23% base, but at cost of 2026 (0.82% vs 2.01%/mo). Not a sufficient improvement.
- **Max daily signals (top-3) hurts**: Limiting to 3 signals/day cuts 2026 returns significantly (1.23%/mo vs 2.01%) with no 2025 benefit. The first-to-qualify signals are not better than later ones.
- **The 2025 bull-market problem requires a different approach**: Intraday strategies systematically underperform buy-and-hold in bull markets because the overnight/morning gap captures most of the daily return before any intraday entry.

---

- **Next action:** Push 2025 returns higher. Current best (131) earns 8.4% in 2025 vs 27.66% buy-and-hold. Remaining avenues:
  1. **Leveraged ETF rebalancing** (TQQQ/SQQQ) — documented overnight edge from daily rebalancing. Requires adding these symbols.
  2. **Multi-stock overnight with position-sizing optimization** — currently equal-weight; could weight by RS magnitude or volatility.
  3. **Accept the structural ceiling** — active overnight strategies may max out at ~10-12% in 2025 because the VWAP quality filter blocks 35-40% of nights, and removing it makes results worse.

---

### Session: Runs 070–134 (2026-04-11)

**Strategies built and tested (7 new strategy files):**
- `intraday_momentum.py` — first-30min momentum → **REFUTED** (WR 40-47%, all 7 variants)
- `combined_rs_momentum.py` — RS short + ITM long → **WORSE than RS alone** (ITM drags 2025)
- `morning_spike_fade.py` — fade morning runners → **REFUTED** (PF 0.58-0.86)
- `overnight_momentum.py` — buy at close, sell next open → **BULL COMPLEMENT FOUND** (+9.7% 2025)
- `allweather.py` (v1) — RS short intraday + overnight long → **FIRST BOTH-WINDOWS POSITIVE** (+10.5%/+4.3%)
- `allweather_v3.py` — dual overnight (momentum + reversal) → **BEST COMBINED** (131: +8.9%/+8.4%)
- `cross_sectional_revert.py`, `volume_momentum.py`, `exhaustion_fade.py` — **ALL REFUTED**

**Key architectural discovery: TIME SEPARATION is the edge.**
- Bear alpha lives INTRADAY (RS shorts during 9:45-15:25)
- Bull alpha lives OVERNIGHT (close-to-open gap on bullish sessions)
- These don't interfere because they operate at different times of day

**What was systematically refuted (113+ experiments):**
- ALL intraday long strategies at 1m on individual stocks (momentum, reversal, volume, cross-sectional, VWAP, fade)
- Cross-sectional intraday reversal (academic HKS finding doesn't survive at 1m)
- Volume as a signal filter for intraday entries (high RVOL selects worse moves)
- Exhaustion gating for mean reversion (PF <0.9 across all variants)
- Overnight on ETFs only (too concentrated, no diversification)
- Multi-day holding (next-day intraday noise erases overnight gap)
- SMA-based overnight regime (worse than VWAP — intraday quality matters more than multi-day trend)

---

## 2. The Research Loop

Each cycle follows these steps in order:

```
1. RESEARCH → What did the previous run teach us? What failed and why?
               Synthesise findings before picking anything new.
               Check key assumptions (trend regime, session volatility, stop placement,
               and whether the strategy is intended to be intraday-only or allowed
               to hold overnight).

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
              Always use the Jan–Apr 2026 window as the primary window.
              Also review the 2025 robustness window before promoting anything.

5. FIX      → If there's a bug in execution, data, or metrics — fix it now.
              Log the issue, root cause, and fix before continuing.

6. EVAL     → Score the result against the candidate criteria below.
              Review ALL metrics. Evaluate 2026 and 2025 separately.
              Verify the observed holding period matches the strategy design.

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
| **1m bars preferred** | Use `--interval 1m` by default; use a different bar size only when the hypothesis clearly requires it |
| **Holding period must be explicit** | Every strategy must state whether it is intraday-only or allowed to hold overnight |
| **EOD flatten when applicable** | Use engine EOD flatten for intraday strategies; do not force it on strategies intentionally designed to hold overnight |
| **Multi-asset** | Always test on ≥ 5 symbols: mix of ETFs (SPY, QQQ) and large-caps (AAPL, MSFT, NVDA) |
| **Two-window evaluation** | Jan–Apr 2026 is the primary window, but 2025 robustness is mandatory in evaluation |
| **Alpaca data** | Use `--data-source alpaca` — bar cache prevents repeated fetches |

---

## 5. Candidate Criteria (Backtest → Promising)

A strategy must meet **all** before being marked promising:

| Metric | Target |
|---|---|
| 2026 monthly return | ≥ 2% |
| 2026 total return | Positive |
| 2025 monthly return | ≥ 2% — must compete with buy-and-hold in bull conditions |
| 2025 total return | ≥ 20% (buy-and-hold benchmark: +27.66%; strategy must approach this) |
| Sharpe ratio (daily, √252) | ≥ 0.5 |
| Max drawdown | ≤ 20% |
| Round trips | ≥ 30 (meaningful sample) |
| Win rate | ≥ 40% |
| Profit factor | ≥ 1.5 |
| Expectancy | Positive |
| Max consecutive losses | ≤ 6 |
| Symbols | ≥ 5 tested, results consistent across them |
| Cross-window behavior | Must be classified honestly: robust, 2026-only, 2025-only, or unstable |
| Holding-period check | Intraday strategies should end flat daily; overnight strategies must explicitly justify and track overnight risk |

Promotion rules:
- A strategy must compete with buy-and-hold in **both** windows to be marked promising.
- Buy-and-hold benchmark: +27.66% in 2025. The strategy must approach this, not just avoid losses.
- Near-flat or low-single-digit 2025 is **not sufficient** — that is regime-gating, not a real edge.
- If it is strong in 2026 but far below buy-and-hold in 2025, label it regime-specific (not solved).
- The goal is a strategy that beats or matches buy-and-hold across regimes, not one that hides in cash.
- **Overfitting caution:** After 69+ variants, the probability of backtest overfitting (PBO) is real. "Works in 2026, fails in 2025" is the exact pattern PBO flags. A result that only appears after many parameter tweaks on the same window is suspect. Treat cross-window consistency as the primary overfitting check.

---

## 6. Adding a New Strategy

1. Create `trading/strategy/<name>.py`, subclass `Strategy`
2. Implement `on_bar(bars, portfolio) → List[Signal]` and `rules() → List[str]`
3. Add `name` and `label` class attributes
4. Register in `trading/strategy/__init__.py` under `STRATEGIES`
5. The strategy will be available to `run_experiment.py` immediately

**Signals:** `Direction.LONG`, `Direction.SHORT`, `Direction.FLAT` (close position).  
**EOD flatten:** Use it for intraday strategies. Overnight strategies may manage exits differently if that is part of the hypothesis.  
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

- **Alpaca free IEX feed** — sufficient for the Jan–Apr 2026 primary window and the 2025 robustness window used in evaluation.
- **Bar cache:** `bar_cache/{SYMBOL}_{interval}.parquet` — fetched once, reused on all subsequent runs.
- **Delete a .parquet file** to force a fresh API fetch.
- **Credentials:** `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`.

---

## 10. Asset Universe

**ETFs:** QQQ, SPY  
**Stocks:** NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP  
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

## 12. Evaluation Standard

Do not optimize only for the highest Jan-Apr 2026 monthly return.

Every strategy must now be judged on both:
- **Primary window:** Jan-Apr 2026
- **Robustness window:** full-year 2025

Classify every strategy as one of:
- `robust across both windows`
- `2026-only / bear-regime only`
- `2025-only`
- `unstable / reject`

Do not present a strategy as solved if it only works in one regime.

If a strategy is designed as intraday-only:
- it should open and close within the same day
- it should end each day flat

If a strategy is designed to hold overnight:
- that is allowed
- but the holding period must be explicit in the rules and run note
- overnight risk must be acknowledged during evaluation

---

## 12. Scope

In scope: strategy research, backtesting, experiment logging, results viewing.  
Out of scope: live trading, paper trading, walk-forward (add if needed later).

---

## 13. Exploration & Filters (When to Trade vs How to Trade)

This system does not assume that strategies alone create edge.

Claude must actively explore:
- **when a strategy works**
- **when it fails**
- **what conditions improve it**

Treat every experiment as:

> Strategy × Conditions → Result

---

### 13.1 Exploration Requirement

Claude is expected to go beyond predefined strategies.

You are allowed and encouraged to:
- Use Google to research trading ideas, filters, and tactics
- Explore trading communities (e.g. Reddit, blogs, discussions)
- Reference existing documentation and known concepts
- Adapt ideas into simple, testable hypotheses

Do NOT copy strategies blindly.  
Translate ideas into minimal, testable rules.

---

### 13.2 Filters (Critical Concept)

Every strategy should be evaluated with and without filters.

Filters define:
- when trading is allowed
- which symbols are eligible
- which direction is preferred

Examples of filter dimensions (not exhaustive):

- Market regime (e.g. using SPY behaviour)
- Multi-day momentum (recent daily direction)
- Trend structure (e.g. higher timeframe alignment)
- Relative strength (stock vs market)
- Volatility (ATR, range expansion)
- Volume (participation / liquidity)
- Intraday behaviour (open vs midday vs close)

Claude should:
- test filters individually
- test combinations of filters
- observe which filters improve consistency

---

### 13.3 Hypothesis-Driven Filtering

Before each run, explicitly state:

- Why this strategy might work
- Under what conditions it should work better
- What filter is being tested (if any)

Example:

> Hypothesis: ORB short works better when market is trending down intraday  
> Filter: Only trade when SPY is below VWAP and declining from open  

---

### 13.4 Iterative Filter Discovery

Filters should evolve over time.

Claude should:
- reuse filters that improved past results
- discard filters that had no impact
- refine thresholds (e.g. % move, EMA length)

Do NOT:
- lock into one fixed filter set too early
- assume one filter works universally

---

### 13.5 Strategy–Filter Pairing

Different strategies may require different conditions.

Claude should learn:

- Trend strategies → trending environments  
- Mean reversion → range-bound environments  
- Breakouts → high volatility / expansion  
- Momentum → volume + directional bias  

This mapping should emerge through experiments.

---

### 13.6 Stock Selection as a Filter

Stock choice is part of the edge.

Claude may:
- dynamically select subsets of symbols
- prefer high-volatility or high-momentum stocks
- exclude consistently underperforming assets

Do not assume all symbols behave equally.

---

### 13.7 Minimalism Rule

When adding filters:

- Prefer simple logic over complex indicators
- Avoid stacking too many conditions at once
- Add one variable at a time where possible

Goal:
Understand causality, not just optimize results.

---

### 13.8 Continuous Learning

At the start of each session:

- Review previous runs
- Identify which conditions improved performance
- Form new hypotheses based on that

At the end of each session:

- Update "Key learnings"
- Explicitly mention which filters or conditions mattered

---

### 13.9 Guiding Principle

The edge is not only in the strategy.

The edge is often:

> Selecting the right conditions for the strategy to operate

Claude should prioritize discovering this relationship.

---

## 14. Research Priors (Evidence-Based Hypotheses)

These are experiment directions grounded in published research or well-documented practitioner findings.
They are not guaranteed to work — they are informed starting points for the next research cycle.

---

### 14.1 Three-Factor Regime Gate (upgrade to current 3d filter)

**Prior:** A single trend-down gate is directionally right but includes "dead tape" days where microstructure dominates and there is no real directional fuel. Adding volatility + breadth confirmation filters these out.

**Hypothesis:** Only short when ALL three conditions hold:
1. SPY trend-down (current 3-day filter)
2. Volatility active — SPY ATR or intraday range above its recent average (not a choppy drift day)
3. Breadth weak — more stocks declining than advancing (index move is broadly confirmed, not driven by a few names)

**Why it should help:** Reduces false signals on low-conviction down days. Preserves 2026 edge while potentially improving signal quality.

**Test as:** Add ATR-based "range expansion" check and a simple advance/decline proxy to the RS short strategy.

---

### 14.2 RVOL Dynamic Universe Selection

**Prior:** Higher relative volume (current volume vs average) correlates with better liquidity, more reliable follow-through, and reduced execution costs. Static hand-picked universes introduce selection bias.

**Hypothesis:** At a fixed time each morning (e.g. 9:35–9:40 ET), rank the full symbol universe by relative volume (today's first N minutes vs average). Only allow trades in the top 5–8 names by RVOL that session.

**Why it should help:** Concentrates exposure on names that are actually "in play" that day. Avoids paying spread on dead names. Reduces universe-dilution that consistently hurt full-universe runs.

**Test as:** Pre-session RVOL filter layered onto the RS short strategy. Compare round trips, WR, and PF vs full-universe baseline.

---

### 14.3 Rank-and-Trade (Top K Weakest Only)

**Prior:** Taking every RS signal that crosses the threshold generates churn. Cross-sectional research supports selecting the most extreme signals rather than all signals above a threshold.

**Hypothesis:** At each decision point, rank all eligible symbols by their RS score (most negative first for shorts). Only enter the top 1–3 weakest names per session, even if more qualify.

**Why it should help:** Higher average expectancy per trade. Fewer round trips = lower cost drag. Forces the strategy to concentrate on the highest-conviction setups.

**Test as:** Add a `max_trades_per_day` parameter to the RS strategy. Test max_trades=2 vs unlimited on the 069 base configuration.

---

### 14.4 Intraday Time-Series Momentum (Bull Complement Candidate)

**Prior:** Published evidence (global sample, multiple markets) shows the first 30-minute return of a session predicts the final 30-minute return. This is statistically and economically significant and persists out-of-sample. It is index-level, so it does not depend on stock selection edge.

**Hypothesis:** If SPY is up in the first 30 minutes after open (9:30–10:00 ET), go LONG SPY or QQQ at 10:00 ET targeting a close near end of day. If SPY is down in the first 30 minutes, this confirms the bear sleeve conditions.

**Why it should help:** Regime-adaptive by construction (conditions on what happened that morning). Naturally complements the RS short: on down-open days → RS shorts; on up-open days → index long. Does not require stock-selection edge.

**Test as:** New strategy `intraday_momentum` — SPY/QQQ only, entry at 10:00 ET based on 9:30–10:00 return direction, exit at 15:30–15:45 ET.

---

### 14.5 Exhaustion Reversion (Conditional Mean Reversion)

**Prior:** VWAP/RSI/gap reversion strategies fail in trending regimes because they fade structured moves. But short-term reversals can dominate after extreme moves with breadth capitulation signals. The condition gate — not the reversion logic itself — is what was missing.

**Hypothesis:** Only enter mean-reversion trades when ALL of the following hold:
1. Volatility is high (ATR expanded, or session range already >1.5% on SPY)
2. A stock has made an extreme intraday move (e.g. >3% from open)
3. Breadth/participation shows exhaustion (RSI >80 or <20, or volume spike without further price progress)

**Why it should help:** Distinguishes "structured trend day" (do not fade) from "panic/squeeze exhaustion" (fade is valid). Previous reversion attempts lacked this gate entirely.

**Test as:** Revise `vwap_reversion` or `rsi_intraday` to require ATR expansion + extreme move threshold before allowing any mean-reversion entry.
