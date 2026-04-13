"""Frontend server — serves completed experiment results only.

Claude runs experiments via:
  .venv/bin/python run_experiment.py --strategy orb --symbols SPY QQQ ...

The frontend reads the saved reports; it does NOT trigger backtests.

Endpoints:
  GET /                            → frontend/index.html
  GET /api/experiments             → list all saved experiments (metadata + metrics)
  GET /api/experiments/<slug>      → full data for one experiment
  GET /api/universe                → full asset universe

Run with:
  .venv/bin/python server.py
"""

import json
import logging
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="frontend", static_url_path="")

ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
REPORTS_DIR = ROOT / "experiments" / "reports"

from trading.config import STOCKS, ETFS, DEFAULT_UNIVERSE


import math as _math

def _per_symbol_from_txns(transactions: list, initial_equity: float) -> dict:
    """Derive per-symbol metrics from stored transactions (backfill for old reports).

    Computes the same fields as BacktestResult.per_symbol_metrics() using pure Python
    so the server has no pandas dependency. Daily-series stats (Sharpe, DD, monthly)
    use the same realized-PnL-normalized-by-initial-equity method as the engine.
    """
    from collections import defaultdict

    fills:      dict = defaultdict(int)
    total_pnl:  dict = defaultdict(float)
    rt_count:   dict = defaultdict(int)
    win_count:  dict = defaultdict(int)
    gross_win:  dict = defaultdict(float)
    gross_loss: dict = defaultdict(float)
    daily_pnl:  dict = defaultdict(lambda: defaultdict(float))   # sym -> date -> pnl

    for t in transactions:
        sym = t.get("asset")
        if not sym:
            continue
        fills[sym] += 1
        p = t.get("pnl")
        d = t.get("date")
        if p is not None:
            total_pnl[sym] += p
            rt_count[sym]  += 1
            if d:
                daily_pnl[sym][d] += p
            if p > 0:
                win_count[sym] += 1
                gross_win[sym] += p
            else:
                gross_loss[sym] += abs(p)

    all_dates = sorted({t["date"] for t in transactions if t.get("date")})

    result = {}
    for sym in fills:
        tp = round(total_pnl[sym], 2)
        rt = rt_count[sym]
        wc = win_count[sym]
        gw = gross_win[sym]
        gl = gross_loss[sym]
        ie = initial_equity or 100_000.0

        # Daily PnL series (realized, aligned to all portfolio dates)
        sym_daily = [daily_pnl[sym].get(d, 0.0) for d in all_dates]
        daily_ret = [p / ie for p in sym_daily]

        # Sharpe (annualised √252)
        n = len(daily_ret)
        mean_r = sum(daily_ret) / n if n else 0.0
        std_r  = _math.sqrt(sum((r - mean_r) ** 2 for r in daily_ret) / (n - 1)) if n > 1 else 0.0
        sharpe = round((mean_r / std_r) * _math.sqrt(252), 2) if std_r > 0 else 0.0

        # Max drawdown on cumulative realized PnL / initial_equity
        cum = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in sym_daily:
            cum += p
            peak = max(peak, cum)
            max_dd = min(max_dd, (cum - peak) / ie * 100)

        # Monthly returns
        monthly_agg: dict = defaultdict(float)
        for d, p in zip(all_dates, sym_daily):
            monthly_agg[d[:7]] += p
        monthly_rets = {k: round(v / ie * 100, 2) for k, v in sorted(monthly_agg.items())}
        avg_monthly  = round(sum(monthly_rets.values()) / len(monthly_rets), 2) if monthly_rets else 0.0

        result[sym] = {
            "total_pnl":          tp,
            "return_pct":         round(tp / ie * 100, 2),
            "fills":              fills[sym],
            "round_trips":        rt,
            "win_count":          wc,
            "gross_win":          round(gw, 2),
            "gross_loss":         round(gl, 2),
            "win_rate_pct":       round(wc / rt * 100, 1) if rt else None,
            "profit_factor":      round(gw / gl, 2) if gl > 0 else None,
            "expectancy":         round(tp / rt, 2) if rt else None,
            "sharpe_ratio":       sharpe,
            "max_drawdown_pct":   round(max_dd, 2),
            "monthly_return_pct": avg_monthly,
            "monthly_breakdown":  monthly_rets,
        }
    return result


# ── Static ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/universe")
def universe():
    return jsonify({"stocks": STOCKS, "etfs": ETFS, "all": DEFAULT_UNIVERSE})


@app.route("/api/experiments")
def list_experiments():
    """List all saved experiment reports, newest first.
    Returns only slug, status, ran_at, metadata, metrics, extended_metrics —
    not the full transaction/calendar lists which are only fetched on demand.
    """
    experiments = []
    for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            with path.open() as f:
                data = json.load(f)
            ps = data.get("per_symbol_metrics") or {}
            if not ps:
                # Backfill from stored transactions for reports generated before
                # per_symbol_metrics was added to to_dict()
                txns = data.get("transactions", [])
                init_eq = (data.get("metrics") or {}).get("initial_equity", 100000)
                ps = _per_symbol_from_txns(txns, init_eq)
            hist = data.get("historical") or {}
            experiments.append({
                "slug":                  data.get("slug", path.stem),
                "status":                data.get("status", "in_progress"),
                "ran_at":                data.get("ran_at"),
                "rules":                 data.get("rules", []),
                "metadata":              data.get("metadata", {}),
                "metrics":               data.get("metrics", {}),
                "extended_metrics":      data.get("extended_metrics", {}),
                "per_symbol_metrics":    ps,
                "buy_and_hold":                  (data.get("metadata") or {}).get("buy_and_hold", {}),
                # Historical (2025) summary — empty dicts if run predates this feature
                "historical_metrics":           hist.get("metrics", {}),
                "historical_per_symbol_metrics": hist.get("per_symbol_metrics", {}),
                "historical_buy_and_hold":       hist.get("buy_and_hold", {}),
            })
        except Exception as e:
            logger.warning("Skipping unreadable report %s: %s", path.name, e)
    return jsonify(experiments)


@app.route("/api/experiments/<slug>")
def get_experiment(slug):
    path = REPORTS_DIR / f"{slug}.json"
    if not path.exists():
        return jsonify({"error": f"Experiment '{slug}' not found"}), 404
    with path.open() as f:
        return jsonify(json.load(f))


if __name__ == "__main__":
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting viewer at http://localhost:%d", port)
    app.run(debug=True, port=port, use_reloader=False)
