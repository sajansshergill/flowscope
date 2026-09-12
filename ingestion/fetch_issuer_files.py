"""Daily holdings + shares outstanding from issuer NAV history (not a single snapshot)."""

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
import requests

from warehouse.duckdb_io import load_universe, seed_universe, write_bronze

LOOKBACK_DAYS = 400
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SPDR_NAVHIST = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "navhist-us-en-{ticker}.xlsx"
)


def _http_get(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=45)
    resp.raise_for_status()
    return resp.content


def _from_spdr(ticker: str, start: date) -> pd.DataFrame:
    url = SPDR_NAVHIST.format(ticker=ticker.lower())
    raw = pd.read_excel(io.BytesIO(_http_get(url)), header=None)
    header_idx = next(
        (i for i, row in raw.iterrows() if str(row.iloc[0]).strip().lower() == "date"),
        None,
    )
    if header_idx is None:
        return pd.DataFrame()
    df = raw.iloc[header_idx + 1 :, :3].copy()
    df.columns = ["as_of_date", "nav", "shares_outstanding"]
    df["as_of_date"] = pd.to_datetime(df["as_of_date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["shares_outstanding"] = pd.to_numeric(df["shares_outstanding"], errors="coerce")
    df = df.dropna(subset=["as_of_date", "nav", "shares_outstanding"])
    df = df[df["as_of_date"] >= pd.Timestamp(start)]
    df["as_of_date"] = df["as_of_date"].dt.date
    df["ticker"] = ticker
    df["source"] = "spdr_navhist"
    return df[["as_of_date", "ticker", "shares_outstanding", "nav", "source"]]


def fetch_one(etf: dict, start: date) -> pd.DataFrame:
    ticker = etf["ticker"]
    issuer = etf.get("issuer", "")
    if issuer == "spdr":
        return _from_spdr(ticker, start)
    raise ValueError(f"no daily shares-outstanding source for {ticker} ({issuer})")


def fetch_issuer_daily(lookback_days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    start = date.today() - timedelta(days=lookback_days)
    frames: list[pd.DataFrame] = []
    for etf in load_universe():
        try:
            frame = fetch_one(etf, start)
        except Exception as exc:  # noqa: BLE001 — one ticker must not abort the pull
            print(f"skip {etf['ticker']}: {exc}")
            continue
        if not frame.empty:
            n_so = frame["shares_outstanding"].nunique()
            print(f"{etf['ticker']}: {len(frame)} rows, SO unique={n_so}")
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    seed_universe()
    df = fetch_issuer_daily()
    n = write_bronze("issuer_daily", df, replace=True)
    print(f"landed {n} issuer_daily rows")


if __name__ == "__main__":
    main()
