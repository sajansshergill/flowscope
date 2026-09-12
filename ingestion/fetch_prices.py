"""Prices, volume, and returns via yfinance or Alpha Vantage."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from warehouse.duckdb_io import load_universe, write_bronze

load_dotenv()

LOOKBACK_DAYS = 400
AV_URL = "https://www.alphavantage.co/query"


def _from_yfinance(tickers: list[str], start: date) -> pd.DataFrame:
    raw = yf.download(
        tickers,
        start=start.isoformat(),
        auto_adjust=False,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    single = len(tickers) == 1
    for ticker in tickers:
        block = raw if single else raw[ticker]
        if block.empty or "Close" not in block.columns:
            continue
        frame = block.reset_index()
        frame["as_of_date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None).dt.date
        frame["ticker"] = ticker
        frame["source"] = "yfinance"
        frames.append(
            frame.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )[
                ["as_of_date", "ticker", "open", "high", "low", "close", "volume", "source"]
            ]
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _from_alpha_vantage(ticker: str) -> pd.DataFrame:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        return pd.DataFrame()
    resp = requests.get(
        AV_URL,
        params={
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "apikey": key,
            "outputsize": "compact",
        },
        timeout=30,
    )
    resp.raise_for_status()
    series = resp.json().get("Time Series (Daily)", {})
    rows = []
    for day, values in series.items():
        rows.append(
            {
                "as_of_date": pd.to_datetime(day).date(),
                "ticker": ticker,
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "volume": int(values["6. volume"]),
                "source": "alpha_vantage",
            }
        )
    return pd.DataFrame(rows)


def fetch_prices(lookback_days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    tickers = [etf["ticker"] for etf in load_universe()]
    if os.environ.get("ALPHA_VANTAGE_API_KEY"):
        frames = [_from_alpha_vantage(t) for t in tickers]
        av = pd.concat([f for f in frames if not f.empty], ignore_index=True)
        if not av.empty:
            cutoff = date.today() - timedelta(days=lookback_days)
            return av[av["as_of_date"] >= cutoff]
    return _from_yfinance(tickers, date.today() - timedelta(days=lookback_days))


def main() -> None:
    df = fetch_prices()
    n = write_bronze("prices", df)
    print(f"landed {n} price rows")


if __name__ == "__main__":
    main()
