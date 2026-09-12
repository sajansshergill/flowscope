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

| Source            | Data                                    | Role                    |
|-------------------|-----------------------------------------|-------------------------|
| Issuer daily CSVs | holdings, shares outstanding, NAV       | flow engine             |
| yfinance / Alpha Vantage | prices, volume, returns          | performance context     |
| FRED              | rates, VIX, macro series                | rotation narrative      |
| SEC N-PORT        | quarterly holdings                      | data-quality cross-check|

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
