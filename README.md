# FlowScope — ETF Fund-Flow & Sector Rotation Analytics

Daily ETF fund-flow and sector-rotation pipeline built on public issuer data.
Computes true creation/redemption flows from daily shares-outstanding deltas —
not a naive price plot — and serves an interactive rotation dashboard.

## Why this exists (business context)

Institutional money moves between sectors before the moves are obvious in price.
Net ETF flows are one of the cleanest public proxies for that positioning.
FlowScope turns free issuer disclosures into a daily view of where capital is
rotating — by sector, by theme, and against the macro backdrop.

## The core idea

Real fund flows = Δ(shares outstanding) × NAV.

Shares outstanding change only when Authorized Participants create or redeem
ETF units — i.e. actual money in/out. Issuers (iShares, SPDR, Vanguard,
Invesco) publish shares outstanding and NAV daily, for free. FlowScope
reconstructs institutional-grade flow data from these files instead of buying
a flows feed.

## Architecture (medallion)

Sources → Bronze → Silver → Gold → Serving

- Bronze: raw daily issuer CSVs + price/macro pulls, landed in DuckDB,
  partitioned by ingest date. Immutable.
- Silver: cleaned, deduped, typed. Shares-outstanding deltas computed.
  Great Expectations validates continuity, non-negativity, calendar gaps.
- Gold: dbt models — daily net flows per ETF, sector/theme rollups,
  flow-vs-return, rotation matrix.
- Serving: Streamlit + Plotly dashboard reading Gold tables.

Orchestrated by Airflow (daily DAG: pull → validate → transform → refresh).

## Data sources (all free)

| Source                   | Data                              | Role                     |
|--------------------------|-----------------------------------|--------------------------|
| Issuer daily CSVs        | holdings, shares outstanding, NAV | flow engine              |
| yfinance / Alpha Vantage | prices, volume, returns           | performance context      |
| FRED                     | rates, VIX, macro series          | rotation narrative       |
| SEC N-PORT               | quarterly holdings                | data-quality cross-check |

## Dashboard views

1. Sector rotation heatmap — net flows by sector, rolling windows
2. Flow vs. performance scatter — chasing vs. front-running returns
3. Thematic flow tracker — AI / defense / crypto / clean-energy
4. Flow leaders & laggards — top inflows/outflows, drill-down to holdings
5. Macro overlay — flows vs. rates / VIX

## Tech stack

Python 3.11 · DuckDB · dbt · Great Expectations · Apache Airflow ·
Streamlit · Plotly · pandas · pyarrow · Docker · docker-compose ·
GitHub Actions

## Repository structure

```
flowscope/
├── README.md
├── Makefile
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .github/workflows/ci.yml
├── config/
│   └── etf_universe.yml          # ~20 ETFs, sector/theme tagged
├── ingestion/
│   ├── fetch_issuer_files.py     # daily holdings + shares outstanding
│   ├── fetch_prices.py           # yfinance / Alpha Vantage
│   └── fetch_macro.py            # FRED
├── warehouse/
│   └── duckdb_io.py              # bronze landing + partitioning
├── quality/
│   └── expectations/             # Great Expectations suites
├── dbt/
│   ├── models/silver/
│   └── models/gold/
├── orchestration/
│   └── dags/flowscope_daily.py   # Airflow DAG
├── app/
│   └── dashboard.py              # Streamlit + Plotly
└── tests/
    └── test_flows.py             # flow-math unit tests
```

## Data quality

Great Expectations gates every Silver load: shares-outstanding continuity,
non-negative NAV, no missing trading days vs. NYSE calendar, flow-magnitude
outlier bounds. Failed expectations fail the Airflow task, not the dashboard.

## Setup

```
make setup      # venv + deps
make ingest     # pull one day of data
make build      # dbt run silver + gold
make app        # launch Streamlit
make test       # unit + data-quality
```

Or: `docker-compose up`

## CI/CD

GitHub Actions on push: lint → unit tests → dbt compile → Great Expectations
dry-run against sample data.

Streamlit Community Cloud auto-deploys `app/dashboard.py` from `main`.
The committed `data/flowscope.duckdb` snapshot is what the live app reads.

## Cloud migration notes

Built to run locally, architected to lift to GCP:
- DuckDB → Snowflake / BigQuery
- Local Airflow → Cloud Composer
- Streamlit → Cloud Run
- Local file landing → GCS bronze bucket
- Secrets → Secret Manager

## Status

Metrics (row counts, ETF coverage, refresh latency) are placeholders —
replace with real numbers after first full run.