# STATUS.md — Current Research State

> Mirror of Section 1 in CLAUDE.md. Keep both in sync.

- **Active strategy:** VWAP mean reversion (Run 003)
- **Phase:** Not yet started
- **Last run:** 002 — ORB with volume + regime filter — REJECTED (−0.37%, Sharpe −1.05, win rate 31.7%)
- **Next action:** Implement VWAP mean reversion in `trading/strategy/vwap_reversion.py`, run backtest on SPY with 5m Alpaca bars 2025-01-01 → 2026-01-01. Log in `experiments/runs/003_vwap_reversion.md`.
