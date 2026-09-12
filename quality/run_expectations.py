"""Run Great Expectations-style suites against Silver (or sample data in dry-run)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pandas_market_calendars as mcal

from warehouse.duckdb_io import compute_net_flow, read_table

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "quality" / "expectations" / "silver_etf_daily.json"
SAMPLE_PATH = ROOT / "tests" / "fixtures" / "sample_issuer.csv"


class ExpectationFailed(Exception):
    pass


def _load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text())


def _nyse_sessions(start, end) -> set:
    cal = mcal.get_calendar("XNYS")
    return set(cal.valid_days(start_date=start, end_date=end).date)


def _check_non_negative_nav(df: pd.DataFrame) -> None:
    if (df["nav"] < 0).any():
        raise ExpectationFailed("NAV must be non-negative")


def _check_shares_continuity(df: pd.DataFrame) -> None:
    if df["shares_outstanding"].isna().any():
        raise ExpectationFailed("shares_outstanding has nulls")


def _check_trading_calendar(df: pd.DataFrame) -> None:
    if df.empty:
        return
    start, end = df["as_of_date"].min(), df["as_of_date"].max()
    sessions = _nyse_sessions(start, end)
    for ticker, grp in df.groupby("ticker"):
        have = set(pd.to_datetime(grp["as_of_date"]).dt.date)
        missing = sessions - have
        if missing:
            sample = sorted(missing)[:5]
            raise ExpectationFailed(f"{ticker} missing NYSE sessions: {sample}")


def _check_flow_bounds(df: pd.DataFrame, z_max: float = 8.0) -> None:
    if "net_flow" not in df.columns:
        ordered = df.sort_values(["ticker", "as_of_date"])
        prev = ordered.groupby("ticker")["shares_outstanding"].shift(1)
        df = ordered.assign(
            net_flow=[
                compute_net_flow(so, p, nav) if pd.notna(p) else 0.0
                for so, p, nav in zip(
                    ordered["shares_outstanding"], prev, ordered["nav"], strict=True
                )
            ]
        )
    flows = df["net_flow"].dropna()
    if flows.empty or flows.std() == 0:
        return
    z = (flows - flows.mean()).abs() / flows.std()
    if (z > z_max).any():
        raise ExpectationFailed(f"flow z-score exceeds {z_max}")


def validate(df: pd.DataFrame) -> None:
    _load_suite()
    _check_non_negative_nav(df)
    _check_shares_continuity(df)
    _check_trading_calendar(df)
    _check_flow_bounds(df)


def _sample_frame() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_PATH, parse_dates=["as_of_date"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the checked-in sample instead of Silver tables.",
    )
    args = parser.parse_args()

    df = _sample_frame() if args.dry_run else read_table("silver", "stg_issuer_daily")
    if df.empty:
        raise SystemExit("no rows to validate")
    validate(df)
    print(f"expectations passed ({len(df)} rows)")


if __name__ == "__main__":
    main()
