"""Flow-math unit tests: net flow = Δ(shares outstanding) × NAV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from quality.run_expectations import ExpectationFailed, validate
from warehouse.duckdb_io import compute_net_flow

FIXTURE = Path(__file__).parent / "fixtures" / "sample_issuer.csv"


def test_creation_is_positive_flow() -> None:
    assert compute_net_flow(1_000_100, 1_000_000, 500.0) == pytest.approx(50_000.0)


def test_redemption_is_negative_flow() -> None:
    assert compute_net_flow(999_000, 1_000_000, 250.0) == pytest.approx(-250_000.0)


def test_unchanged_shares_is_zero_flow() -> None:
    assert compute_net_flow(5_000_000, 5_000_000, 412.33) == 0.0


def test_fixture_flows_match_delta_times_nav() -> None:
    df = pd.read_csv(FIXTURE, parse_dates=["as_of_date"]).sort_values("as_of_date")
    prev = df["shares_outstanding"].shift(1)
    expected = (df["shares_outstanding"] - prev) * df["nav"]
    actual = [
        compute_net_flow(so, p, nav) if pd.notna(p) else float("nan")
        for so, p, nav in zip(df["shares_outstanding"], prev, df["nav"], strict=True)
    ]
    pd.testing.assert_series_equal(
        expected.reset_index(drop=True),
        pd.Series(actual, dtype="float64"),
        check_names=False,
    )


def test_sample_passes_silver_expectations() -> None:
    validate(pd.read_csv(FIXTURE, parse_dates=["as_of_date"]))


def test_negative_nav_fails_expectations() -> None:
    df = pd.read_csv(FIXTURE, parse_dates=["as_of_date"])
    df.loc[0, "nav"] = -1
    with pytest.raises(ExpectationFailed, match="non-negative"):
        validate(df)
