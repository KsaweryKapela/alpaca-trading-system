"""Historical market data providers.

Primary source: yfinance (free, no API key needed).
Optional source: Alpaca historical API (requires credentials, more reliable).

Both return the same iterator interface consumed by the backtest engine.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, Iterator, List

import pandas as pd
import yfinance as yf

from ..models import Bar

logger = logging.getLogger(__name__)


def load_bars_yfinance(
    symbols: List[str],
    start: datetime,
    end: datetime,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV bars from Yahoo Finance.

    Returns {symbol: DataFrame} with a UTC DatetimeIndex and
    columns: Open, High, Low, Close, Volume.
    """
    dfs: Dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            raw = yf.download(
                symbol, start=start, end=end,
                interval=interval, progress=False, auto_adjust=True,
            )
            if raw.empty:
                logger.warning("No data returned for %s", symbol)
                continue

            # Newer yfinance versions may return a MultiIndex column
            if isinstance(raw.columns, pd.MultiIndex):
                raw = raw.droplevel(level=1, axis=1)

            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.index = pd.to_datetime(df.index, utc=True)
            df = df.dropna()
            dfs[symbol] = df
            logger.info("Loaded %d bars for %s (yfinance)", len(df), symbol)
        except Exception as exc:
            logger.error("Failed to load %s: %s", symbol, exc)

    return dfs


def load_bars_alpaca(
    symbols: List[str],
    start: datetime,
    end: datetime,
    api_key: str,
    secret_key: str,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV bars from Alpaca historical data API.

    Args:
        interval: Bar size — "1m", "5m", "15m", "30m", "1h", "1d".
                  Intraday data requires valid Alpaca credentials.
                  Free (IEX) feed has limited intraday history; SIP feed has full history.
    """
    if not api_key or not secret_key:
        raise ValueError(
            "Alpaca credentials required for --data-source alpaca. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in your .env file."
        )

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    _TF_MAP = {
        "1m":  TimeFrame.Minute,
        "5m":  TimeFrame(5,  TimeFrameUnit.Minute),
        "15m": TimeFrame(15, TimeFrameUnit.Minute),
        "30m": TimeFrame(30, TimeFrameUnit.Minute),
        "1h":  TimeFrame.Hour,
        "1d":  TimeFrame.Day,
    }
    timeframe = _TF_MAP.get(interval)
    if timeframe is None:
        raise ValueError(f"Unsupported interval '{interval}'. Choose from: {list(_TF_MAP)}")

    from .cache import load_cached, save_to_cache

    dfs: Dict[str, pd.DataFrame] = {}
    symbols_to_fetch: List[str] = []

    # Check cache in parallel (disk I/O benefits from threading)
    def _check_cache(sym):
        return sym, load_cached(sym, start, end, interval)

    with ThreadPoolExecutor(max_workers=min(len(symbols), 8)) as pool:
        for sym, cached in pool.map(_check_cache, symbols):
            if cached is not None and not cached.empty:
                logger.info("  [cache] %-6s  %d bars", sym, len(cached))
                dfs[sym] = cached
            else:
                symbols_to_fetch.append(sym)

    if not symbols_to_fetch:
        logger.info("All %d symbols loaded from cache.", len(dfs))
        return dfs

    logger.info("Fetching %d symbol(s) from Alpaca: %s",
                len(symbols_to_fetch), " ".join(symbols_to_fetch))
    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockBarsRequest(
        symbol_or_symbols=symbols_to_fetch,
        timeframe=timeframe,
        start=start,
        end=end,
        feed="iex",
    )
    logger.info("Sending request to Alpaca API…")
    barset = client.get_stock_bars(request)
    raw_df = barset.df  # MultiIndex (symbol, timestamp)
    logger.info("Alpaca response received. Parsing %d symbols…", len(symbols_to_fetch))

    for symbol in symbols_to_fetch:
        try:
            sdf = raw_df.loc[symbol].copy()
            sdf.index = pd.to_datetime(sdf.index, utc=True)
            sdf.columns = [c.capitalize() for c in sdf.columns]
            sdf = sdf[["Open", "High", "Low", "Close", "Volume"]]
            dfs[symbol] = sdf
            save_to_cache(symbol, interval, sdf)
            logger.info("  [api]   %-6s  %d bars  (cached)", symbol, len(sdf))
        except KeyError:
            logger.warning("No Alpaca data for %s", symbol)

    return dfs


def iter_bars(symbol_dfs: Dict[str, pd.DataFrame]) -> Iterator[Dict[str, Bar]]:
    """Yield {symbol: Bar} for each timestamp, sorted chronologically.

    Timestamps where a symbol has no data are simply absent from the dict.
    The engine should handle sparse bars gracefully.
    """
    if not symbol_dfs:
        return

    all_timestamps = sorted(
        {ts for df in symbol_dfs.values() for ts in df.index}
    )

    for ts in all_timestamps:
        bars: Dict[str, Bar] = {}
        for symbol, df in symbol_dfs.items():
            if ts not in df.index:
                continue
            row = df.loc[ts]
            bars[symbol] = Bar(
                symbol=symbol,
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        if bars:
            yield bars
