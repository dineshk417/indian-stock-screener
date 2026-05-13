"""
Page 9: Smart Money Tracker
Data is fetched once daily by GitHub Actions (08:30 AM IST) and stored
in data/smart_money_cache.json.  Streamlit reads the file — no live NSE calls.
"""
import datetime as _dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.smart_money import (
    cache_updated_at,
    fetch_bulk_deals,
    fetch_block_deals,
    fetch_fii_dii_flow,
    fetch_insider_trades,
    fetch_institutional_holders,
)
from config.stock_universe import NIFTY_50

st.set_page_config(page_title="Smart Money · NiftyEdge", layout="wide", page_icon="🏦")
from ui.styles import inject_global_css, page_header, show_loading, auth_guard, user_sidebar
inject_global_css()
auth_guard()

page_header(
    "🏦 Smart Money Tracker",
    subtitle="Bulk & Block · FII/DII Flow · Insider Trades · Holdings",
    badge="DAILY",
    badge_color="#7c83fd",
)

# ── Cache freshness banner ──────────────────────────────────────────────────────────────
_cache_ts = cache_updated_at()
if _cache_ts is None:
    st.markdown(
        '<div style="background:rgba(240,180,41,0.07);border:1px solid rgba(240,180,41,0.25);'
        'border-left:3px solid #f0b429;border-radius:10px;padding:12px 18px;margin-bottom:16px;">'
        '<span style="color:#f0b429;font-weight:700;">Data not yet populated · </span>'
        '<span style="color:#94a3b8;font-size:0.82rem;">'
        'The daily GitHub Actions job (<code>Smart Money Daily Data Fetch</code>) '
        'has not run yet. It runs automatically at 8:30 AM IST on trading days. '
        'You can also trigger it manually from the <b>Actions</b> tab in GitHub.'
        '</span></div>',
        unsafe_allow_html=True,
    )
else:
    import pytz as _pytz
    _IST = _pytz.timezone("Asia/Kolkata")
    _ts_ist = _cache_ts.astimezone(_IST) if _cache_ts.tzinfo else _cache_ts
    _age_h  = (_dt.datetime.now(_pytz.utc) - _cache_ts.replace(tzinfo=_pytz.utc) if not _cache_ts.tzinfo else _dt.datetime.now(_pytz.utc) - _cache_ts).seconds // 3600
    st.markdown(
        f'<div style="background:rgba(0,200,150,0.05);border:1px solid rgba(0,200,150,0.15);'
        f'border-left:3px solid #00c896;border-radius:10px;padding:10px 18px;margin-bottom:16px;">'
        f'<span style="color:#00c896;font-weight:700;">Data as of </span>'
        f'<span style="color:#e2e8f0;">{_ts_ist.strftime("%d %b %Y %I:%M %p IST")}</span>'
        f'<span style="color:#475569;font-size:0.78rem;margin-left:10px;">({_age_h}h ago · refreshes daily at 8:30 AM IST)</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Sidebar ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    period_opt = st.selectbox("Period", ["Last 7 days", "Last 15 days", "Last 30 days", "Last 60 days"])
    _period_map = {"Last 7 days": 7, "Last 15 days": 15, "Last 30 days": 30, "Last 60 days": 60}
    days_back = _period_map[period_opt]

    txn_filter = st.radio("Transaction Type", ["All", "Buy", "Sell"], horizontal=True)

    st.divider()
    st.caption(
        "Data fetched once daily by GitHub Actions (8:30 AM IST).\n\n"
        "Sources: NSE Archive CDN · NSE API · BSE API · Yahoo Finance.\n\n"
        "All ₹ figures in Crore."
    )

    st.divider()
    user_sidebar()
# ── Tabs ──────────────────────────────────────────────────────────────────────────────
tab_deals, tab_flow, tab_insider, tab_holders = st.tabs([
    "📦 Bulk & Block Deals",
    "🌊 FII / DII Flow",
    "🔏 Insider Trades",
    "🏗 Top Holders",
])


# ── Helper: styled empty state ─────────────────────────────────────────────────────────
def _empty(msg: str, sub: str = ""):
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
        f'border-radius:14px;padding:32px;text-align:center;margin:12px 0;">'
        f'<div style="font-size:1.5rem;margin-bottom:8px;">📭</div>'
        f'<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px;">{msg}</div>'
        f'<div style="color:#475569;font-size:0.8rem;">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _source_badge(source: str, color: str = "#7c83fd"):
    st.markdown(
        f'<div style="display:inline-block;background:rgba(124,131,253,0.08);'
        f'border:1px solid rgba(124,131,253,0.2);border-radius:6px;'
        f'padding:3px 10px;font-size:0.68rem;font-weight:700;'
        f'color:{color};letter-spacing:0.06em;margin-bottom:12px;">'
        f'SOURCE · {source}</div>',
        unsafe_allow_html=True,
    )


def _source_unavailable(source: str, why: str = ""):
    st.markdown(
        f'<div style="background:rgba(255,77,109,0.04);border:1px solid rgba(255,77,109,0.15);'
        f'border-left:3px solid #ff4d6d;border-radius:10px;padding:12px 16px;margin-bottom:12px;">'
        f'<span style="color:#ff4d6d;font-weight:700;">No data · {source}</span>'
        + (f'<br><span style="color:#94a3b8;font-size:0.78rem;">{why}</span>' if why else "")
        + '</div>',
        unsafe_allow_html=True,
    )


def _type_col(df: pd.DataFrame, col: str = "Type") -> pd.DataFrame:
    """Filter by Buy/Sell based on sidebar selection."""
    if txn_filter == "All" or col not in df.columns:
        return df
    return df[df[col].str.upper().str.contains(txn_filter.upper(), na=False)]


def _value_badge(val: float) -> str:
    if val >= 500:   return "#00c896"
    if val >= 100:   return "#f0b429"
    return "#94a3b8"


def _kpi_card(label: str, value: str, sub: str = "", color: str = "#f1f5f9") -> str:
    return (
        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
        f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.09em;margin-bottom:6px;">{label}</div>'
        f'<div style="color:{color};font-size:1.4rem;font-weight:800;">{value}</div>'
        f'<div style="color:#475569;font-size:0.7rem;margin-top:3px;">{sub}</div>'
        f'</div>'
    )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — BULK & BLOCK DEALS                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_deals:
    _bd_slot = show_loading("Reading bulk &amp; block deal data from cache — last 30 days of NSE trade disclosures…", "#f0b429")
    bulk_df  = fetch_bulk_deals(days_back)
    block_df = fetch_block_deals(days_back)
    _bd_slot.empty()

    # Combine bulk + block
    frames = [df for df in (bulk_df, block_df) if not df.empty]
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.rename(columns={
            "date":     "Date",
            "symbol":   "Symbol",
            "name":     "Name",
            "entity":   "Entity",
            "type":     "Type",
            "shares":   "Shares",
            "price":    "Price ₹",
            "value_cr": "Value ₹ Cr",
            "category": "Deal",
        })
        if "Deal" in combined.columns:
            combined["Deal"] = combined["Deal"].str.title()
        if "Date" in combined.columns:
            combined = combined.sort_values("Date", ascending=False)
    else:
        combined = pd.DataFrame()

    if not combined.empty:
        combined = _type_col(combined, "Type")

    # ── Stats strip ────────────────────────────────────────────────────────────────────
    if not combined.empty:
        _n_bulk    = int((combined["Deal"] == "Bulk").sum())
        _n_block   = int((combined["Deal"] == "Block").sum())
        _n_buy     = int(combined["Type"].str.upper().str.contains("BUY", na=False).sum())
        _n_sell    = len(combined) - _n_buy
        _val_total = combined["Value ₹ Cr"].sum() if "Value ₹ Cr" in combined.columns else 0

        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px;">'
            + _kpi_card("Total Deals", str(len(combined)), f"{_n_bulk} Bulk · {_n_block} Block")
            + _kpi_card("Buy Deals", str(_n_buy), "Entity buying stock", "#00c896")
            + _kpi_card("Sell Deals", str(_n_sell), "Entity selling stock", "#ff4d6d")
            + _kpi_card("Total Value", f"₹{_val_total:,.0f} Cr", "Combined turnover", "#f0b429")
            + "</div>",
            unsafe_allow_html=True,
        )

        all_symbols = sorted(combined["Symbol"].dropna().unique()) if "Symbol" in combined.columns else []
        sel_symbols = st.multiselect("Filter by Stock", all_symbols, placeholder="All stocks")
        if sel_symbols:
            combined = combined[combined["Symbol"].isin(sel_symbols)]

        st.markdown(
            '<div style="font-size:0.72rem;font-weight:700;color:#64748b;'
            'text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">'
            f'Showing {len(combined)} deal(s)</div>',
            unsafe_allow_html=True,
        )

        display_cols = [c for c in ["Date", "Symbol", "Deal", "Entity", "Type", "Shares", "Price ₹", "Value ₹ Cr"] if c in combined.columns]
        show_df = combined[display_cols].copy()
        if "Date" in show_df.columns:
            show_df["Date"] = show_df["Date"].dt.strftime("%d %b %Y")

        def _deal_type_style(v):
            v = str(v).upper()
            if "BUY" in v:   return "color:#00c896;font-weight:700"
            if "SELL" in v:  return "color:#ff4d6d;font-weight:700"
            return ""

        def _deal_kind_style(v):
            return "color:#7c83fd;font-weight:600" if v == "Block" else "color:#f0b429;font-weight:600"

        style_cols = {}
        if "Type" in show_df.columns:  style_cols["Type"] = _deal_type_style
        if "Deal" in show_df.columns:  style_cols["Deal"] = _deal_kind_style

        styled = show_df.style.map(lambda v: style_cols.get("Type", lambda x: "")(v) if "Type" in show_df.columns else "", subset=["Type"] if "Type" in show_df.columns else [])
        if "Type" in show_df.columns:
            styled = styled.map(_deal_type_style, subset=["Type"])
        if "Deal" in show_df.columns:
            styled = styled.map(_deal_kind_style, subset=["Deal"])
        if "Value ₹ Cr" in show_df.columns:
            styled = styled.format({"Value ₹ Cr": lambda v: f"₹{v:,.1f} Cr" if pd.notna(v) else "—"})
        if "Price ₹" in show_df.columns:
            styled = styled.format({"Price ₹": lambda v: f"₹{float(v):,.2f}" if pd.notna(v) else "—"})
        if "Shares" in show_df.columns:
            styled = styled.format({"Shares": lambda v: f"{int(v):,}" if pd.notna(v) else "—"})

        st.dataframe(styled, use_container_width=True, height=480, hide_index=True)

        csv = combined.to_csv(index=False).encode()
        st.download_button("⬇ Download CSV", csv,
                           file_name=f"bulk_block_deals_{_dt.date.today()}.csv",
                           mime="text/csv")
    else:
        _empty(
            "No deal data in cache",
            "Run the 'Smart Money Daily Data Fetch' GitHub Actions job to populate the cache.",
        )


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — FII / DII FLOW                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_flow:
    _fii_slot = show_loading("Loading FII &amp; DII daily net flow data — foreign vs domestic institutional buying…", "#00c896")
    flow_df = fetch_fii_dii_flow(days_back)
    _fii_slot.empty()
    if not flow_df.empty:
        flow_df = flow_df.loc[:, ~flow_df.columns.duplicated()]

    if flow_df.empty:
        _empty(
            "No FII/DII data in cache",
            "Run the 'Smart Money Daily Data Fetch' GitHub Actions job to populate the cache.",
        )
    else:
        _fii = flow_df[flow_df["Category"].str.upper().str.contains("FII|FPI", na=False)] if "Category" in flow_df.columns else pd.DataFrame()
        _dii = flow_df[flow_df["Category"].str.upper().str.contains("DII", na=False)] if "Category" in flow_df.columns else pd.DataFrame()

        def _net_sum(df: pd.DataFrame) -> float:
            if "Net ₹Cr" not in df.columns or df.empty:
                return 0.0
            col = df["Net ₹Cr"]
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
            return float(pd.to_numeric(col, errors="coerce").sum())

        fii_net = _net_sum(_fii)
        dii_net = _net_sum(_dii)
        combined_net = fii_net + dii_net

        fii_col = "#00c896" if fii_net >= 0 else "#ff4d6d"
        dii_col = "#00c896" if dii_net >= 0 else "#ff4d6d"
        cmb_col = "#00c896" if combined_net >= 0 else "#ff4d6d"

        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;">'
            + _kpi_card("FII / FPI Net", f"₹{fii_net:+,.0f} Cr", f"{'Buying' if fii_net>=0 else 'Selling'} in period", fii_col)
            + _kpi_card("DII Net", f"₹{dii_net:+,.0f} Cr", f"{'Buying' if dii_net>=0 else 'Selling'} in period", dii_col)
            + _kpi_card("Combined Net", f"₹{combined_net:+,.0f} Cr", "FII + DII market direction", cmb_col)
            + "</div>",
            unsafe_allow_html=True,
        )

        if not _fii.empty and "Date" in _fii.columns and "Net ₹Cr" in _fii.columns:
            _fii_sorted = _fii.copy()
            _fii_sorted["Net ₹Cr"] = pd.to_numeric(_fii_sorted["Net ₹Cr"], errors="coerce")
            _fii_sorted = _fii_sorted.sort_values("Date")
            _dii_cp = _dii.copy() if not _dii.empty else pd.DataFrame()
            if not _dii_cp.empty and "Net ₹Cr" in _dii_cp.columns:
                _dii_cp["Net ₹Cr"] = pd.to_numeric(_dii_cp["Net ₹Cr"], errors="coerce")
            _dii_sorted = _dii_cp.sort_values("Date") if not _dii_cp.empty else pd.DataFrame()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=_fii_sorted["Date"],
                y=_fii_sorted["Net ₹Cr"],
                name="FII / FPI",
                marker_color=[("#00c896" if v >= 0 else "#ff4d6d") for v in _fii_sorted["Net ₹Cr"]],
                opacity=0.85,
                hovertemplate="<b>FII</b> %{x}<br>Net: ₹%{y:+,.0f} Cr<extra></extra>",
            ))
            if not _dii_sorted.empty and "Net ₹Cr" in _dii_sorted.columns:
                fig.add_trace(go.Bar(
                    x=_dii_sorted["Date"],
                    y=_dii_sorted["Net ₹Cr"],
                    name="DII",
                    marker_color=[("#7c83fd" if v >= 0 else "#f0b429") for v in _dii_sorted["Net ₹Cr"]],
                    opacity=0.85,
                    hovertemplate="<b>DII</b> %{x}<br>Net: ₹%{y:+,.0f} Cr<extra></extra>",
                ))
            fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.15)")
            fig.update_layout(
                title=dict(text="Daily Net Institutional Flow (₹ Cr)", font=dict(color="#94a3b8", size=13)),
                barmode="group",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=40, b=40, l=60, r=20), height=320,
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99")),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99"), title="₹ Cr"),
            )
            st.plotly_chart(fig, use_container_width=True)

        if not _fii.empty and "Date" in _fii.columns and "Net ₹Cr" in _fii.columns:
            _fii_c = _fii.sort_values("Date").copy()
            _fii_c["Net ₹Cr"] = pd.to_numeric(_fii_c["Net ₹Cr"], errors="coerce")
            _fii_c["Cumulative"] = _fii_c["Net ₹Cr"].cumsum()
            final = float(_fii_c["Cumulative"].iloc[-1])
            lc = "#00c896" if final >= 0 else "#ff4d6d"
            fc = "rgba(0,200,150,0.08)" if final >= 0 else "rgba(255,77,109,0.08)"

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=_fii_c["Date"], y=_fii_c["Cumulative"],
                mode="lines+markers",
                name="FII Cumulative",
                line=dict(color=lc, width=2),
                fill="tozeroy", fillcolor=fc,
                hovertemplate="%{x}<br>Cumulative: ₹%{y:+,.0f} Cr<extra></extra>",
            ))
            fig2.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.15)")
            fig2.update_layout(
                title=dict(text="FII Cumulative Net Flow (₹ Cr)", font=dict(color="#94a3b8", size=13)),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=40, b=40, l=60, r=20), height=260,
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99")),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99"), title="₹ Cr"),
            )
            st.plotly_chart(fig2, use_container_width=True)

        with st.expander("Raw Daily Data"):
            show = flow_df.copy()
            if "Date" in show.columns:
                show["Date"] = show["Date"].dt.strftime("%d %b %Y")
            st.dataframe(show, use_container_width=True, hide_index=True)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 3 — INSIDER / PROMOTER TRADES                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_insider:
    _ins_slot = show_loading("Loading insider &amp; promoter trade disclosures (SEBI PIT regulations)…", "#7c83fd")
    insider_df = fetch_insider_trades(days_back)
    _ins_slot.empty()

    if insider_df.empty:
        _empty(
            "No insider trade data in cache",
            "Run the 'Smart Money Daily Data Fetch' GitHub Actions job to populate the cache.",
        )
    else:
        insider_df = _type_col(insider_df, "Txn")

        _n_buy  = int(insider_df["Txn"].str.upper().str.contains("BUY|ACQUI", na=False).sum()) if "Txn" in insider_df.columns else 0
        _n_sell = len(insider_df) - _n_buy
        _val    = insider_df["Value ₹ Cr"].sum() if "Value ₹ Cr" in insider_df.columns else 0

        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;">'
            + _kpi_card("Total Disclosures", str(len(insider_df)), f"Last {days_back} days")
            + _kpi_card("Acquisitions", str(_n_buy), "Buy / acquire", "#00c896")
            + _kpi_card("Disposals", str(_n_sell), "Sell / dispose", "#ff4d6d")
            + "</div>",
            unsafe_allow_html=True,
        )

        # ── Charts ────────────────────────────────────────────────────────────
        _ic1, _ic2 = st.columns(2)

        if "Disclosed" in insider_df.columns and "Txn" in insider_df.columns:
            _ins_ts = insider_df.copy()
            _ins_ts["_date"] = pd.to_datetime(_ins_ts["Disclosed"], errors="coerce").dt.date
            _ins_ts["_is_buy"] = _ins_ts["Txn"].str.upper().str.contains("BUY|ACQUI|CREAT", na=False)
            _daily = (_ins_ts.groupby(["_date", "_is_buy"]).size()
                      .reset_index(name="Count"))
            _buy_d = _daily[_daily["_is_buy"]].set_index("_date")["Count"]
            _sel_d = _daily[~_daily["_is_buy"]].set_index("_date")["Count"]
            _all_dates = sorted(set(_buy_d.index) | set(_sel_d.index))
            if _all_dates:
                fig_ins = go.Figure()
                fig_ins.add_trace(go.Bar(x=_all_dates, y=[_buy_d.get(d, 0) for d in _all_dates],
                    name="Buy / Acquire", marker_color="#00c896"))
                fig_ins.add_trace(go.Bar(x=_all_dates, y=[_sel_d.get(d, 0) for d in _all_dates],
                    name="Sell / Dispose", marker_color="#ff4d6d"))
                fig_ins.update_layout(
                    barmode="stack", height=280, margin=dict(l=0, r=0, t=28, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#94a3b8", legend=dict(orientation="h", y=1.08),
                    title=dict(text="Daily Insider Disclosures", font_size=13, font_color="#e2e8f0"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Count"),
                )
                with _ic1:
                    st.plotly_chart(fig_ins, use_container_width=True)

        if "Company" in insider_df.columns and "Value ₹ Cr" in insider_df.columns:
            _top_co = (insider_df.copy()
                .assign(**{"Value ₹ Cr": pd.to_numeric(insider_df["Value ₹ Cr"], errors="coerce")})
                .groupby("Company", as_index=False)["Value ₹ Cr"].sum()
                .dropna(subset=["Value ₹ Cr"])
                .sort_values("Value ₹ Cr", key=abs, ascending=False)
                .head(10))
            if not _top_co.empty:
                _top_co["Color"] = _top_co["Value ₹ Cr"].apply(lambda v: "#00c896" if v >= 0 else "#ff4d6d")
                fig_co = go.Figure(go.Bar(
                    x=_top_co["Value ₹ Cr"], y=_top_co["Company"],
                    orientation="h", marker_color=_top_co["Color"],
                    hovertemplate="<b>%{y}</b><br>₹%{x:+,.1f} Cr<extra></extra>",
                ))
                fig_co.update_layout(
                    height=280, margin=dict(l=0, r=0, t=28, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#94a3b8",
                    title=dict(text="Top Companies by Insider Trade Value", font_size=13, font_color="#e2e8f0"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", title="Net ₹ Cr"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", autorange="reversed"),
                )
                with _ic2:
                    st.plotly_chart(fig_co, use_container_width=True)

        if "Category" in insider_df.columns:
            cats = sorted(insider_df["Category"].dropna().unique())
            sel_cats = st.multiselect("Filter by Category", cats, placeholder="All categories")
            if sel_cats:
                insider_df = insider_df[insider_df["Category"].isin(sel_cats)]

        disp_cols = [c for c in [
            "Disclosed", "Symbol", "Company", "Person", "Category",
            "Txn", "Shares", "Value ₹ Cr", "Before %", "After %", "Mode",
        ] if c in insider_df.columns]
        show_ins = insider_df[disp_cols].copy()
        if "Disclosed" in show_ins.columns:
            show_ins["Disclosed"] = show_ins["Disclosed"].dt.strftime("%d %b %Y")

        def _ins_txn_style(v):
            v = str(v).upper()
            if any(k in v for k in ("BUY", "ACQUI", "CREAT")):  return "color:#00c896;font-weight:700"
            if any(k in v for k in ("SELL", "DISPO", "PLEDGE")): return "color:#ff4d6d;font-weight:700"
            return "color:#94a3b8"

        styled_ins = show_ins.style
        if "Txn" in show_ins.columns:
            styled_ins = styled_ins.map(_ins_txn_style, subset=["Txn"])
        if "Value ₹ Cr" in show_ins.columns:
            styled_ins = styled_ins.format({"Value ₹ Cr": lambda v: f"₹{v:,.1f} Cr" if pd.notna(v) else "—"})

        st.dataframe(styled_ins, use_container_width=True, height=480, hide_index=True)

        csv_ins = insider_df.to_csv(index=False).encode()
        st.download_button("⬇ Download CSV", csv_ins,
                           file_name=f"insider_trades_{_dt.date.today()}.csv",
                           mime="text/csv")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 4 — TOP INSTITUTIONAL HOLDERS                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_holders:
    st.markdown(
        '<div style="font-size:0.72rem;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:0.09em;margin-bottom:4px;">Nifty 50 — Top Institutional Holdings</div>'
        '<div style="font-size:0.72rem;color:#475569;margin-bottom:14px;">'
        'Sourced from Yahoo Finance · Updates quarterly · Figures in USD (Yahoo Finance reports in USD)</div>',
        unsafe_allow_html=True,
    )

    _n50_tickers = tuple(NIFTY_50.values())

    _inst_slot = show_loading("Fetching latest institutional holder data for Nifty 50 stocks via Yahoo Finance…", "#7c83fd")
    holders_df = fetch_institutional_holders(_n50_tickers)
    _inst_slot.empty()

    if holders_df.empty:
        _empty(
            "Holdings data unavailable",
            "yfinance institutional_holders data may not be available for all NSE stocks."
        )
    else:
        all_tickers = sorted(holders_df["Ticker"].dropna().unique()) if "Ticker" in holders_df.columns else []
        sel_tickers = st.multiselect("Filter by Stock", all_tickers, placeholder="All Nifty 50 stocks")
        if sel_tickers:
            holders_df = holders_df[holders_df["Ticker"].isin(sel_tickers)]

        if "Institution" in holders_df.columns and "% Held" in holders_df.columns:
            top_inst = (
                holders_df.groupby("Institution")["% Held"]
                .mean()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            top_inst.columns = ["Institution", "Avg % Held"]

            fig3 = go.Figure(go.Bar(
                x=top_inst["Avg % Held"],
                y=top_inst["Institution"],
                orientation="h",
                marker_color="#7c83fd",
                hovertemplate="%{y}<br>Avg holding: %{x:.2f}%<extra></extra>",
            ))
            fig3.update_layout(
                title=dict(text="Top 10 Institutions by Average Stake (across held stocks)", font=dict(color="#94a3b8", size=13)),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=40, b=40, l=240, r=20), height=340,
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99"), title="Avg % Held"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickfont=dict(color="#6b7a99"), autorange="reversed"),
            )
            st.plotly_chart(fig3, use_container_width=True)

        disp_cols_h = [c for c in ["Ticker", "Institution", "Shares", "Date", "% Held", "Value $"] if c in holders_df.columns]
        show_h = holders_df[disp_cols_h].copy()
        if "Date" in show_h.columns:
            show_h["Date"] = pd.to_datetime(show_h["Date"], errors="coerce").dt.strftime("%d %b %Y")

        def _pct_style(v):
            try:
                f = float(v)
                if f >= 5:   return "color:#00c896;font-weight:700"
                if f >= 2:   return "color:#f0b429;font-weight:600"
                return "color:#94a3b8"
            except Exception:
                return ""

        styled_h = show_h.style
        if "% Held" in show_h.columns:
            styled_h = styled_h.map(_pct_style, subset=["% Held"])
            styled_h = styled_h.format({"% Held": lambda v: f"{float(v):.2f}%" if pd.notna(v) else "—"})

        st.dataframe(styled_h, use_container_width=True, height=480, hide_index=True)

        csv_h = holders_df.to_csv(index=False).encode()
        st.download_button("⬇ Download CSV", csv_h,
                           file_name=f"institutional_holders_{_dt.date.today()}.csv",
                           mime="text/csv")
