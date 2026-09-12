"""Bronze landing in DuckDB, partitioned by ingest date. Immutable appends."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "flowscope.duckdb"
UNIVERSE_PATH = ROOT / "config" / "etf_universe.yml"
BRONZE_TABLES = ("issuer_daily", "prices", "macro", "etf_universe")


def db_path() -> Path:
    return Path(os.environ.get("FLOWSCOPE_DB_PATH", DEFAULT_DB))


def get_connection() -> duckdb.DuckDBPyConnection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    return con


def load_universe() -> list[dict]:
    with UNIVERSE_PATH.open() as fh:
        return yaml.safe_load(fh)["etfs"]


def load_macro_series() -> list[dict]:
    with UNIVERSE_PATH.open() as fh:
        return yaml.safe_load(fh)["macro_series"]


def ensure_bronze_tables(con: duckdb.DuckDBPyConnection | None = None) -> None:
    own = con is None
    con = con or get_connection()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.issuer_daily (
            as_of_date DATE,
            ticker VARCHAR,
            shares_outstanding DOUBLE,
            nav DOUBLE,
            source VARCHAR,
            ingest_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.prices (
            as_of_date DATE,
            ticker VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            source VARCHAR,
            ingest_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.macro (
            as_of_date DATE,
            series_id VARCHAR,
            value DOUBLE,
            ingest_date DATE
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.etf_universe (
            ticker VARCHAR,
            name VARCHAR,
            issuer VARCHAR,
            sector VARCHAR,
            theme VARCHAR
        )
        """
    )
    if own:
        con.close()


def seed_universe(con: duckdb.DuckDBPyConnection | None = None) -> None:
    own = con is None
    con = con or get_connection()
    ensure_bronze_tables(con)
    rows = [
        {
            "ticker": e["ticker"],
            "name": e["name"],
            "issuer": e["issuer"],
            "sector": e["sector"],
            "theme": e["theme"],
        }
        for e in load_universe()
    ]
    universe = pd.DataFrame(rows)
    con.register("universe", universe)
    con.execute("DELETE FROM bronze.etf_universe")
    con.execute("INSERT INTO bronze.etf_universe SELECT * FROM universe")
    con.unregister("universe")
    if own:
        con.close()


def write_bronze(
    table: str,
    df: pd.DataFrame,
    ingest_on: date | None = None,
    *,
    replace: bool = False,
) -> int:
    """Bronze write, tagged with ingest_date. replace=True wipes the table first."""
    if table not in BRONZE_TABLES:
        raise ValueError(f"Unknown bronze table: {table}")
    if df.empty:
        return 0

    landed = df.copy()
    if "ingest_date" not in landed.columns:
        landed["ingest_date"] = pd.to_datetime(ingest_on or date.today()).date()

    con = get_connection()
    try:
        ensure_bronze_tables(con)
        cols = [row[0] for row in con.execute(f"DESCRIBE bronze.{table}").fetchall()]
        missing = [c for c in cols if c not in landed.columns]
        if missing:
            raise ValueError(f"bronze.{table} missing columns {missing}")
        col_sql = ", ".join(cols)
        if replace:
            con.execute(f"DELETE FROM bronze.{table}")
        con.register("landed", landed[cols])
        con.execute(f"INSERT INTO bronze.{table} ({col_sql}) SELECT {col_sql} FROM landed")
        con.unregister("landed")
        return len(landed)
    finally:
        con.close()


def read_table(schema: str, table: str) -> pd.DataFrame:
    con = get_connection()
    try:
        return con.execute(f"SELECT * FROM {schema}.{table}").df()
    except duckdb.CatalogException:
        return pd.DataFrame()
    finally:
        con.close()


def compute_net_flow(shares_t: float, shares_prev: float, nav_t: float) -> float:
    """True creation/redemption flow: Δ(shares outstanding) × NAV."""
    return (shares_t - shares_prev) * nav_t
