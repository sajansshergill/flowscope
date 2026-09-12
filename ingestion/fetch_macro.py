"""FRED rates, VIX, and macro series for the rotation narrative."""

from __future__ import annotations

import os
from datetime import date, timedelta
from io import StringIO

import pandas as pd
import requests
from dotenv import load_dotenv

from warehouse.duckdb_io import load_macro_series, write_bronze

load_dotenv()

LOOKBACK_DAYS = 400
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _from_fred_api(series_id: str, start: date) -> pd.DataFrame:
    from fredapi import Fred

    raw = Fred(api_key=os.environ["FRED_API_KEY"]).get_series(
        series_id, observation_start=start.isoformat()
    )
    frame = raw.rename("value").to_frame().reset_index()
    frame.columns = ["as_of_date", "value"]
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
    frame["series_id"] = series_id
    return frame.dropna(subset=["value"])


def _from_fred_csv(series_id: str, start: date) -> pd.DataFrame:
    resp = requests.get(
        FRED_CSV,
        params={"id": series_id, "cosd": start.isoformat()},
        timeout=30,
    )
    resp.raise_for_status()
    frame = pd.read_csv(StringIO(resp.text))
    date_col, value_col = frame.columns[0], frame.columns[1]
    frame = frame.rename(columns={date_col: "as_of_date", value_col: "value"})
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"], errors="coerce").dt.date
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame["series_id"] = series_id
    return frame.dropna(subset=["as_of_date", "value"])


def fetch_macro(lookback_days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    start = date.today() - timedelta(days=lookback_days)
    use_api = bool(os.environ.get("FRED_API_KEY"))
    frames: list[pd.DataFrame] = []
    for series in load_macro_series():
        series_id = series["series_id"]
        try:
            frame = (
                _from_fred_api(series_id, start)
                if use_api
                else _from_fred_csv(series_id, start)
            )
        except Exception as exc:  # noqa: BLE001 — one series must not abort the pull
            print(f"skip {series_id}: {exc}")
            continue
        if not frame.empty:
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    df = fetch_macro()
    n = write_bronze("macro", df)
    source = "fredapi" if os.environ.get("FRED_API_KEY") else "fred.csv"
    print(f"landed {n} macro rows via {source}")


if __name__ == "__main__":
    main()
