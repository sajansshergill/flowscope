"""Streamlit + Plotly serving layer over Gold tables."""

from __future__ import annotations

import sys
from pathlib import Path

# Community Cloud runs app/dashboard.py with app/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from warehouse.duckdb_io import db_path, read_table

st.set_page_config(page_title="FlowScope", layout="wide")
st.title("FlowScope")
st.caption("ETF fund-flow and sector-rotation analytics — Δ(shares outstanding) × NAV")


@st.cache_data(ttl=60)
def load_gold(table: str, db_mtime: float) -> pd.DataFrame:
    return read_table("gold", table)


def _empty(name: str) -> None:
    st.info(f"No rows in gold.{name}. Run `make ingest` then `make build`.")


_db_mtime = db_path().stat().st_mtime if db_path().exists() else 0.0
flows = load_gold("fct_etf_daily_flows", _db_mtime)
sector = load_gold("agg_sector_flows", _db_mtime)
theme = load_gold("agg_theme_flows", _db_mtime)
vs_ret = load_gold("fct_flow_vs_return", _db_mtime)
rotation = load_gold("agg_rotation_matrix", _db_mtime)
macro = read_table("silver", "stg_macro")

tab_heat, tab_scatter, tab_theme, tab_leaders, tab_macro = st.tabs(
    [
        "Sector rotation",
        "Flow vs performance",
        "Thematic tracker",
        "Leaders & laggards",
        "Macro overlay",
    ]
)

with tab_heat:
    st.subheader("Net flows by sector")
    if sector.empty:
        _empty("agg_sector_flows")
    else:
        window = st.selectbox("Rolling window (days)", [5, 20, 60], index=1)
        pivot = (
            sector.sort_values("as_of_date")
            .assign(
                flow_roll=lambda d: d.groupby("sector")["net_flow"].transform(
                    lambda s: s.rolling(window, min_periods=1).sum()
                )
            )
            .pivot_table(index="as_of_date", columns="sector", values="flow_roll")
        )
        millions = pivot / 1e6
        peak = float(millions.abs().to_numpy().max()) if not millions.empty else 0.0
        if peak == 0:
            st.warning(
                "All sector flows are $0 — shares outstanding did not change in this window."
            )
        finite = millions.to_numpy().ravel()
        finite = finite[pd.notna(finite)]
        bound = float(pd.Series(finite).abs().quantile(0.95)) if len(finite) else 0.0
        bound = bound or peak
        fig = px.imshow(
            millions.T,
            aspect="auto",
            color_continuous_scale="RdBu",
            color_continuous_midpoint=0,
            zmin=-bound if bound else None,
            zmax=bound if bound else None,
            labels={"color": "Net flow ($M)", "x": "Date", "y": "Sector"},
            template="plotly_dark",
        )
        fig.update_xaxes(tickformat="%b %d")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")

with tab_scatter:
    st.subheader("Chasing vs. front-running returns")
    if vs_ret.empty:
        _empty("fct_flow_vs_return")
    else:
        latest = vs_ret.dropna(subset=["daily_return", "net_flow"])
        if latest.empty:
            st.info("Need overlapping flow and return rows.")
        else:
            fig = px.scatter(
                latest,
                x="daily_return",
                y="net_flow",
                color="sector",
                hover_data=["ticker", "as_of_date"],
                labels={"daily_return": "Daily return", "net_flow": "Net flow"},
            )
            st.plotly_chart(fig, width="stretch")

with tab_theme:
    st.subheader("AI / defense / crypto / clean-energy")
    if theme.empty:
        _empty("agg_theme_flows")
    else:
        fig = px.line(
            theme,
            x="as_of_date",
            y="net_flow",
            color="theme",
            labels={"as_of_date": "Date", "net_flow": "Net flow"},
        )
        st.plotly_chart(fig, width="stretch")

with tab_leaders:
    st.subheader("Top inflows and outflows")
    if flows.empty:
        _empty("fct_etf_daily_flows")
    else:
        days = st.slider("Lookback days", 5, 60, 20)
        cutoff = pd.to_datetime(flows["as_of_date"]).max() - pd.Timedelta(days=days)
        windowed = flows[pd.to_datetime(flows["as_of_date"]) >= cutoff]
        ranked = (
            windowed.groupby(["ticker", "sector", "theme"], as_index=False)["net_flow"]
            .sum()
            .sort_values("net_flow", ascending=False)
        )
        left, right = st.columns(2)
        left.write("Inflows")
        left.dataframe(ranked.head(10), width="stretch")
        right.write("Outflows")
        right.dataframe(ranked.tail(10).iloc[::-1], width="stretch")

with tab_macro:
    st.subheader("Flows vs. rates / VIX")
    if sector.empty or macro.empty:
        st.info("Need gold sector flows and silver macro. Set FRED_API_KEY and re-ingest.")
    else:
        series = st.selectbox("Macro series", sorted(macro["series_id"].unique()))
        m = macro[macro["series_id"] == series][["as_of_date", "value"]].copy()
        s = sector.groupby("as_of_date", as_index=False)["net_flow"].sum()
        s["as_of_date"] = pd.to_datetime(s["as_of_date"])
        m["as_of_date"] = pd.to_datetime(m["as_of_date"])
        merged = s.merge(m, on="as_of_date", how="inner")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=merged["as_of_date"], y=merged["net_flow"], name="Net flow"))
        fig.add_trace(
            go.Scatter(
                x=merged["as_of_date"],
                y=merged["value"],
                name=series,
                yaxis="y2",
                mode="lines",
            )
        )
        fig.update_layout(
            yaxis=dict(title="Net flow"),
            yaxis2=dict(title=series, overlaying="y", side="right"),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, width="stretch")
