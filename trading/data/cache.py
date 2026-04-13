"""Disk cache for historical bar data.

Caches downloaded OHLCV bars as parquet files so that re-running backtests
on the same symbol/interval avoids repeated API calls.

Cache directory: ./bar_cache/ relative to the project root.
Files: bar_cache/{symbol}_{interval}.parquet  (one per symbol per interval)

Each cache file holds ALL available data fetched so far for that symbol+interval.
When a date-range request comes in:
  - Hit:  requested range is fully covered → return filtered slice (no API call)
  - Miss: fetch from API, merge with any existing cache, save, return slice

To invalidate the cache for a symbol, delete the corresponding parquet file.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

_write_lock = threading.Lock()  # prevent concurrent writes to the same cache file

logger = logging.getLogger(__name__)

# Resolved once at import time; works regardless of working directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = _PROJECT_ROOT / "bar_cache"


def _cache_file(symbol: str, interval: str) -> Path:
    safe = symbol.replace("/", "_").replace("^", "").upper()
    return CACHE_DIR / f"{safe}_{interval}.parquet"


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_cached(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: str,
) -> Optional[pd.DataFrame]:
    """Return cached bars for symbol/interval covering [start, end), or None on cache miss."""
    path = _cache_file(symbol, interval)
    if not path.exists():
        return None

    try:
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index, utc=True)
        cache_start = df.index.min()
        cache_end = df.index.max()
        req_start = pd.Timestamp(_to_utc(start))
        req_end = pd.Timestamp(_to_utc(end))

        # Compare dates only — first bar is at market open (14:30 UTC), not midnight
        if cache_start.date() > req_start.date() or cache_end.date() < (req_end - pd.Timedelta(days=1)).date():
            return None  # cache doesn't cover full requested range

        sliced = df[(df.index >= req_start) & (df.index < req_end)].copy()
        logger.info("Cache hit: %d bars for %s (%s)", len(sliced), symbol, interval)
        return sliced
    except Exception as exc:
        logger.warning("Cache read failed for %s/%s: %s", symbol, interval, exc)
        return None


def save_to_cache(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
) -> None:
    """Merge df into the cache for symbol/interval and persist."""
    if df.empty:
        return
    CACHE_DIR.mkdir(exist_ok=True)
    path = _cache_file(symbol, interval)

    try:
        with _write_lock:
            if path.exists():
                existing = pd.read_parquet(path)
                existing.index = pd.to_datetime(existing.index, utc=True)
                merged = pd.concat([existing, df]).sort_index()
                merged = merged[~merged.index.duplicated(keep="last")]
            else:
                merged = df.copy().sort_index()
            merged.to_parquet(path)
        logger.debug("Cached %d bars for %s (%s)", len(merged), symbol, interval)
    except Exception as exc:
        logger.warning("Cache write failed for %s/%s: %s", symbol, interval, exc)


def cache_stats() -> Dict[str, Dict]:
    """Return summary of what's in the cache."""
    if not CACHE_DIR.exists():
        return {}
    stats = {}
    for f in sorted(CACHE_DIR.glob("*.parquet")):
        try:
            df = pd.read_parquet(f)
            df.index = pd.to_datetime(df.index, utc=True)
            stats[f.stem] = {
                "bars": len(df),
                "from": str(df.index.min().date()),
                "to": str(df.index.max().date()),
                "size_kb": round(f.stat().st_size / 1024, 1),
            }
        except Exception:
            pass
    return stats
