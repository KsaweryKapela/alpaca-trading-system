# STATUS.md — Current Research State

> Mirror of Section 1 in CLAUDE.md. Keep both in sync.

- **Active strategy:** RSI mean reversion daily (Run 005)
- **Phase:** Not yet started
- **Last run:** 004 — SMA 20/50 daily SPY+QQQ 2015-2026 — PROMISING (Sharpe 0.69, PF 3.32, +21.58%)
- **Next action:** Research RSI daily reversion, implement `trading/strategy/rsi_reversion.py`, run backtest SPY+QQQ daily 2015-2026. Log in `experiments/runs/005_rsi_reversion.md`.

## Run History

| Run | Strategy | Result | Sharpe | Return |
|---|---|---|---|---|
| 001 | ORB base (SPY+QQQ, 5m) | REJECTED | −0.04 | −1.08% |
| 002 | ORB filtered vol+regime (SPY, 5m) | REJECTED | −1.05 | −0.37% |
| 003 | VWAP reversion (SPY, 5m) | REJECTED | −0.25 | −0.09% |
| 004 | SMA 20/50 (SPY+QQQ, daily, 11yr) | **PROMISING** | **0.69** | **+21.58%** |
