"""Historical market data providers.

Primary source: yfinance (free, no API key needed).
Optional source: Alpaca historical API (requires credentials, more reliable).

Both return the same iterator interface consumed by the backtest engine.
"""

import logging
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
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV bars from Alpaca historical data API."""
    if not api_key or not secret_key:
        raise ValueError(
            "Alpaca credentials required for --data-source alpaca. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in your .env file."
        )

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    barset = client.get_stock_bars(request)
    raw_df = barset.df  # MultiIndex (symbol, timestamp)

    dfs: Dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            sdf = raw_df.loc[symbol].copy()
            sdf.index = pd.to_datetime(sdf.index, utc=True)
            sdf.columns = [c.capitalize() for c in sdf.columns]
            dfs[symbol] = sdf[["Open", "High", "Low", "Close", "Volume"]]
            logger.info("Loaded %d bars for %s (Alpaca)", len(sdf), symbol)
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
