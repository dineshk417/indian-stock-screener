"""
Page 7: Signal Log & Performance Dashboard
"""
import time
import datetime as _dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import pytz

try:
    from signals.signal_logger import (
        get_signal_logger,
        OUTCOME_OPEN, OUTCOME_TARGET1, OUTCOME_TARGET2,
        OUTCOME_STOPPED, OUTCOME_SQUARED_OFF, OUTCOME_EXPIRED,
    )
    from signals.trade_costs import DEFAULT_POSITION_SIZE_INR
    _import_error = None
except Exception as _exc:
    import traceback as _tb
    _import_error = _tb.format_exc()

st.set_page_config(page_title="Signal Log · ShareSaathi", layout="wide", page_icon="📋")
from ui.styles import inject_global_css; inject_global_css()

if _import_error:
    st.error("Import error — check logs.")
    st.code(_import_error, language="python")
    st.stop()

IST = pytz.timezone("Asia/Kolkata")

OUTCOME_LABELS = {
    OUTCOME_TARGET2:     "Target 2 Hit",
    OUTCOME_TARGET1:     "Target 1 Hit",
    OUTCOME_STOPPED:     "Stopped Out",
    OUTCOME_SQUARED_OFF: "Squared Off",
    OUTCOME_EXPIRED:     "Expired",
    OUTCOME_OPEN:        "Open",
}
OUTCOME_COLORS = {
    OUTCOME_TARGET2:     "#00C896",
    OUTCOME_TARGET1:     "#5AD8A6",
    OUTCOME_STOPPED:     "#ff4d6d",
    OUTCOME_SQUARED_OFF: "#f0b429",
    OUTCOME_EXPIRED:     "#6b7a99",
    OUTCOME_OPEN:        "#7c83fd",
}
OUTCOME_BADGE = {
    OUTCOME_TARGET2:     ("T2 HIT",  "#00C896"),
    OUTCOME_TARGET1:     ("T1 HIT",  "#5AD8A6"),
    OUTCOME_STOPPED:     ("STOPPED", "#ff4d6d"),
    OUTCOME_SQUARED_OFF: ("SQ OFF",  "#f0b429"),
    OUTCOME_EXPIRED:     ("EXPIRED", "#6b7a99"),
    OUTCOME_OPEN:        ("OPEN",    "#7c83fd"),
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    timeframe_opt = st.selectbox("Timeframe", ["All", "SWING", "INTRADAY"])
    timeframe     = None if timeframe_opt == "All" else timeframe_opt

    period_opt = st.selectbox("Period", ["Last 7 days", "Last 30 days", "Last 60 days", "Last 90 days", "All time"])
    _period_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 60 days": 60, "Last 90 days": 90, "All time": 365}
    days_back   = _period_map[period_opt]

    st.divider()
    st.subheader("Cost Settings")
    position_size = st.number_input(
        "Position Size (₹)", min_value=10_000, max_value=10_000_000,
        value=int(DEFAULT_POSITION_SIZE_INR), step=10_000,
        help="Capital per trade used to calculate costs and P&L.",
    )

# ── Core data ─────────────────────────────────────────────────────────────────
log       = get_signal_logger()
today_str = _dt.date.today().isoformat()
now_ist   = _dt.datetime.now(IST)

# Auto-resolve: always run for stale signals, otherwise throttle to 5 min
_open_all   = log.get_open_signals()
_last_res   = st.session_state.get("_last_resolve_ts", 0)
_has_stale  = any(s["signal_date"] < today_str for s in _open_all)
_should_res = _has_stale or (time.time() - _last_res) > 300

if _should_res and _open_all:
    try:
        from signals.outcome_tracker import update_open_signal_outcomes
        _n = update_open_signal_outcomes(position_size_inr=float(position_size))
        st.session_state["_last_resolve_ts"] = time.time()
        if _n:
            st.rerun()
    except Exception:
        pass
    if not _has_stale:
        st.session_state["_last_resolve_ts"] = time.time()

perf    = log.get_performance_summary(timeframe=timeframe, days_back=days_back)
signals = log.get_signals(timeframe=timeframe, days_back=days_back)
open_signals   = [s for s in signals if s["outcome"] == OUTCOME_OPEN]
closed_signals = [s for s in signals if s["outcome"] != OUTCOME_OPEN]

# ── Page header ────────────────────────────────────────────────────────────────
from data.market_status import is_market_open as _is_mkt_open
_mkt_live = _is_mkt_open()
_dot_col  = "#00c896" if _mkt_live else "#f0b429"
_dot_rgb  = "0,200,150" if _mkt_live else "240,180,41"
_pulse    = "animation:pulse 1.4s ease-in-out infinite;" if _mkt_live else ""

st.markdown(
    '<div style="margin-bottom:4px;">'
    '<span style="font-size:0.72rem;font-weight:700;color:#64748b;'
    'text-transform:uppercase;letter-spacing:0.1em;">NSE · Trade Journal · Forward Test</span>'
    '</div>',
    unsafe_allow_html=True,
)

hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.title("📋 Signal Log")
with hcol2:
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    _run_scan = st.button("▶ Run Scan Now", type="primary", use_container_width=True)

# ── Run Scan ───────────────────────────────────────────────────────────────────
if _run_scan:
    with st.spinner("Generating signals…"):
        try:
            from signals.swing_signals import generate_swing_signals
            from config.stock_universe import NIFTY_50
            tickers = list(NIFTY_50.values())
            new_sigs = generate_swing_signals(tickers, use_cache=False)
            n_new    = sum(1 for s in new_sigs)
            st.success(f"Scan complete — {len(new_sigs)} swing signal(s) generated, {n_new} logged.")
        except Exception as _e:
            st.error(f"Scan error: {_e}")

        if _mkt_live:
            try:
                from signals.intraday_signals import generate_intraday_signals
                from config.stock_universe import NIFTY_50
                i_sigs = generate_intraday_signals(list(NIFTY_50.values()))
                if i_sigs:
                    st.info(f"{len(i_sigs)} intraday signal(s) also generated.")
            except Exception:
                pass
        st.rerun()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_live, tab_perf, tab_hist = st.tabs(["📍 Live Positions", "📊 Performance", "📜 History"])

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — LIVE POSITIONS                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_live:

    # Status bar
    _last_ts   = st.session_state.get("_last_resolve_ts", 0)
    _mins_ago  = int((time.time() - _last_ts) / 60) if _last_ts else None
    st.markdown(
        f'<div style="background:rgba({_dot_rgb},0.05);border:1px solid rgba({_dot_rgb},0.15);'
        f'border-radius:10px;padding:10px 16px;display:flex;align-items:center;'
        f'justify-content:space-between;margin-bottom:16px;">'
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="width:7px;height:7px;border-radius:50%;background:{_dot_col};{_pulse}"></div>'
        f'<span style="color:{_dot_col};font-weight:700;font-size:0.8rem;">'
        f'{"Market Live" if _mkt_live else "Market Closed"}</span>'
        f'<span style="color:#475569;font-size:0.75rem;margin-left:4px;">'
        f'{"· prices updating live" if _mkt_live else "· showing last close"}</span>'
        f'</div>'
        f'<span style="color:#475569;font-size:0.72rem;">'
        f'{len(_open_all)} open · checked {f"{_mins_ago}m ago" if _mins_ago else "on load"}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _check_col, _ = st.columns([1, 3])
    with _check_col:
        if st.button("🔄 Check Outcomes Now", use_container_width=True):
            with st.spinner("Resolving…"):
                try:
                    from signals.outcome_tracker import update_open_signal_outcomes
                    _n = update_open_signal_outcomes(position_size_inr=float(position_size))
                    st.session_state["_last_resolve_ts"] = time.time()
                    if _n:
                        st.success(f"Resolved {_n} signal(s).")
                        st.rerun()
                    else:
                        st.info("Nothing resolved — all signals still active.")
                except Exception as _e:
                    st.error(str(_e))

    # Filter open signals by sidebar timeframe
    _open_filtered = [s for s in _open_all if timeframe is None or s["timeframe"] == timeframe]

    if not _open_filtered:
        st.markdown(
            '<div style="background:rgba(124,131,253,0.06);border:1px solid rgba(124,131,253,0.12);'
            'border-radius:14px;padding:32px;text-align:center;margin:16px 0;">'
            '<div style="font-size:1.8rem;margin-bottom:10px;">📭</div>'
            '<div style="color:#e2e8f0;font-weight:700;margin-bottom:6px;">No open positions</div>'
            '<div style="color:#475569;font-size:0.82rem;line-height:1.6;">'
            'Run a scan to generate signals — they appear here automatically as open trades.'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        @st.fragment(run_every=120 if _mkt_live else None)
        def _live_positions():
            _is_live = _is_mkt_open()
            for sig in _open_filtered:
                ticker    = sig["ticker"]
                entry     = sig["entry_price"]
                stop      = sig["stop_loss"]
                t1        = sig["target_1"]
                t2        = sig["target_2"]
                direction = sig["direction"]
                is_long   = direction == "LONG"
                label     = ticker.replace(".NS", "")
                dir_col   = "#00c896" if is_long else "#ff4d6d"
                dir_arr   = "↑ LONG" if is_long else "↓ SHORT"

                curr_price = None
                if _is_live:
                    try:
                        curr_price = float(yf.Ticker(ticker).fast_info.last_price)
                    except Exception:
                        pass
                # Fallback: use last daily close
                if curr_price is None:
                    try:
                        _df = yf.Ticker(ticker).history(period="2d", interval="1d", auto_adjust=True)
                        if not _df.empty:
                            curr_price = float(_df["Close"].iloc[-1])
                    except Exception:
                        pass

                if curr_price is not None:
                    pnl_pct = ((curr_price - entry) / entry * 100) if is_long else ((entry - curr_price) / entry * 100)
                    pnl_inr = pnl_pct / 100 * float(position_size)
                    pnl_col = "#00c896" if pnl_pct >= 0 else "#ff4d6d"

                    # Progress bar: entry=0%, T2=100%, stop = negative
                    total_range = t2 - entry if is_long else entry - t2
                    if total_range > 0:
                        progress = ((curr_price - entry) / total_range * 100) if is_long else ((entry - curr_price) / total_range * 100)
                        progress = max(-50, min(110, progress))
                    else:
                        progress = 0

                    # Status
                    if is_long:
                        if curr_price <= stop:              status_l, status_c = "STOPPED",    "#ff4d6d"
                        elif curr_price >= t2:              status_l, status_c = "T2 HIT",     "#00c896"
                        elif curr_price >= t1:              status_l, status_c = "T1 HIT",     "#5AD8A6"
                        elif (entry - curr_price) / abs(entry - stop) > 0.6:
                                                            status_l, status_c = "NEAR SL",    "#f0b429"
                        else:                               status_l, status_c = "ACTIVE",     "#7c83fd"
                    else:
                        if curr_price >= stop:              status_l, status_c = "STOPPED",    "#ff4d6d"
                        elif curr_price <= t2:              status_l, status_c = "T2 HIT",     "#00c896"
                        elif curr_price <= t1:              status_l, status_c = "T1 HIT",     "#5AD8A6"
                        elif (curr_price - entry) / abs(stop - entry) > 0.6:
                                                            status_l, status_c = "NEAR SL",    "#f0b429"
                        else:                               status_l, status_c = "ACTIVE",     "#7c83fd"

                    bar_fill_w = max(0, min(100, progress))
                    bar_color  = "#00c896" if progress >= 50 else "#f0b429" if progress >= 0 else "#ff4d6d"
                    days_held  = (_dt.date.today() - _dt.date.fromisoformat(sig["signal_date"])).days
                    days_str   = f"{days_held}d" if days_held > 0 else "today"

                    html = (
                        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
                        f'border:1px solid rgba(255,255,255,0.07);border-left:4px solid {dir_col};'
                        f'border-radius:14px;padding:16px 18px;margin:8px 0;">'

                        # Header row
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
                        f'<div style="display:flex;align-items:center;gap:10px;">'
                        f'<span style="font-size:1.05rem;font-weight:800;color:#e2e8f0;">{label}</span>'
                        f'<span style="background:{dir_col}22;color:{dir_col};border:1px solid {dir_col}44;'
                        f'border-radius:5px;padding:2px 8px;font-size:0.7rem;font-weight:700;">{dir_arr}</span>'
                        f'<span style="color:#475569;font-size:0.72rem;">{sig.get("strategy","")} · {sig.get("timeframe","")} · {days_str}</span>'
                        f'</div>'
                        f'<span style="background:{status_c}22;color:{status_c};border:1px solid {status_c}44;'
                        f'border-radius:6px;padding:3px 12px;font-size:0.78rem;font-weight:700;">{status_l}</span>'
                        f'</div>'

                        # Price grid
                        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:14px;">'

                        f'<div style="text-align:center;">'
                        f'<div style="font-size:0.58rem;color:#6b7a99;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Entry</div>'
                        f'<div style="font-size:0.95rem;font-weight:700;color:#e2e8f0;">₹{entry:,.2f}</div></div>'

                        f'<div style="text-align:center;">'
                        f'<div style="font-size:0.58rem;color:#6b7a99;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Current</div>'
                        f'<div style="font-size:0.95rem;font-weight:800;color:#f1f5f9;">₹{curr_price:,.2f}</div>'
                        f'<div style="font-size:0.78rem;font-weight:700;color:{pnl_col};">{pnl_pct:+.2f}% · ₹{pnl_inr:+,.0f}</div></div>'

                        f'<div style="text-align:center;">'
                        f'<div style="font-size:0.58rem;color:#6b7a99;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Stop Loss</div>'
                        f'<div style="font-size:0.95rem;font-weight:700;color:#ff4d6d;">₹{stop:,.2f}</div>'
                        f'<div style="font-size:0.72rem;color:#475569;">{abs(entry-stop)/entry*100:.1f}% away</div></div>'

                        f'<div style="text-align:center;">'
                        f'<div style="font-size:0.58rem;color:#6b7a99;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Target 1</div>'
                        f'<div style="font-size:0.95rem;font-weight:700;color:#5AD8A6;">₹{t1:,.2f}</div>'
                        f'<div style="font-size:0.72rem;color:#475569;">{abs(t1-entry)/entry*100:.1f}% away</div></div>'

                        f'<div style="text-align:center;">'
                        f'<div style="font-size:0.58rem;color:#6b7a99;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Target 2</div>'
                        f'<div style="font-size:0.95rem;font-weight:700;color:#00c896;">₹{t2:,.2f}</div>'
                        f'<div style="font-size:0.72rem;color:#475569;">{abs(t2-entry)/entry*100:.1f}% away</div></div>'

                        f'</div>'

                        # Progress bar: SL ──── entry ──── T1 ──── T2
                        f'<div style="margin-top:4px;">'
                        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                        f'<span style="font-size:0.62rem;color:#ff4d6d;">◄ SL</span>'
                        f'<span style="font-size:0.62rem;color:#6b7a99;">Entry</span>'
                        f'<span style="font-size:0.62rem;color:#5AD8A6;">T1</span>'
                        f'<span style="font-size:0.62rem;color:#00c896;">T2 ►</span>'
                        f'</div>'
                        f'<div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;overflow:hidden;">'
                        f'<div style="width:{bar_fill_w}%;height:100%;background:{bar_color};border-radius:4px;'
                        f'transition:width 0.3s ease;"></div></div>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(html, unsafe_allow_html=True)
                else:
                    days_held = (_dt.date.today() - _dt.date.fromisoformat(sig["signal_date"])).days
                    st.markdown(
                        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
                        f'border-left:4px solid {dir_col};border-radius:14px;padding:14px 18px;margin:8px 0;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<div>'
                        f'<span style="font-size:1rem;font-weight:800;color:#e2e8f0;">{label}</span>'
                        f'<span style="color:#6b7a99;font-size:0.75rem;margin-left:10px;">{sig.get("strategy","")} · {sig.get("timeframe","")} · {days_held}d held</span>'
                        f'</div>'
                        f'<span style="color:#6b7a99;font-size:0.78rem;">Price unavailable</span>'
                        f'</div>'
                        f'<div style="margin-top:8px;color:#475569;font-size:0.75rem;">'
                        f'Entry ₹{entry:,.2f} · SL ₹{stop:,.2f} · T1 ₹{t1:,.2f} · T2 ₹{t2:,.2f}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

        _live_positions()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — PERFORMANCE                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_perf:
    total_closed = perf["won"] + perf["lost"] + perf["squared_off"]
    net_pnl      = perf.get("total_net_pnl_inr")
    avg_r        = perf.get("avg_r")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    wr_col   = "#00c896" if total_closed > 0 and perf["win_rate"] >= 50 else "#ff4d6d" if total_closed > 0 else "#475569"
    pnl_col  = "#00c896" if (net_pnl or 0) >= 0 else "#ff4d6d"
    r_col    = "#00c896" if (avg_r or 0) >= 0 else "#ff4d6d"

    pf_won   = perf["won"]
    pf_lost  = perf["lost"]
    prof_fac = round(pf_won / pf_lost, 2) if pf_lost > 0 else None

    kpi_html = (
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px;">'

        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">Win Rate</div>'
        f'<div style="color:{wr_col};font-size:1.6rem;font-weight:800;">{perf["win_rate"]}%</div>'
        f'<div style="color:#475569;font-size:0.72rem;margin-top:3px;">{pf_won}W · {pf_lost}L · {perf["squared_off"]}SQ</div>'
        f'</div>'

        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">Net P&L</div>'
        f'<div style="color:{pnl_col};font-size:1.6rem;font-weight:800;">{"₹{:+,.0f}".format(net_pnl) if net_pnl is not None else "—"}</div>'
        f'<div style="color:#475569;font-size:0.72rem;margin-top:3px;">After costs · ₹{int(position_size):,}/trade</div>'
        f'</div>'

        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">Avg R-Multiple</div>'
        f'<div style="color:{r_col};font-size:1.6rem;font-weight:800;">{f"{avg_r:+.2f}R" if avg_r is not None else "—"}</div>'
        f'<div style="color:#475569;font-size:0.72rem;margin-top:3px;">Risk-adjusted return per trade</div>'
        f'</div>'

        f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:16px;">'
        f'<div style="color:#64748b;font-size:0.6rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:6px;">Trades</div>'
        f'<div style="color:#f1f5f9;font-size:1.6rem;font-weight:800;">{perf["total"]}</div>'
        f'<div style="color:#475569;font-size:0.72rem;margin-top:3px;">{perf["open"]} open · {total_closed} closed · {perf.get("expired",0)} expired</div>'
        f'</div>'

        f'</div>'
    )
    st.markdown(kpi_html, unsafe_allow_html=True)

    if perf["total"] == 0:
        st.markdown(
            '<div style="background:rgba(124,131,253,0.06);border:1px solid rgba(124,131,253,0.12);'
            'border-radius:14px;padding:32px;text-align:center;margin:16px 0;">'
            '<div style="font-size:1.8rem;margin-bottom:10px;">📊</div>'
            '<div style="color:#e2e8f0;font-weight:700;margin-bottom:6px;">No signals in this period</div>'
            '<div style="color:#475569;font-size:0.82rem;line-height:1.6;">'
            'Use <b style="color:#f0b429;">▶ Run Scan Now</b> above to generate signals, '
            'or change the Period filter in the sidebar.'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        # ── Charts row ────────────────────────────────────────────────────────
        cc1, cc2 = st.columns(2)

        with cc1:
            st.markdown('<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin-bottom:6px;">Outcome Distribution</div>', unsafe_allow_html=True)
            by_outcome = perf.get("by_outcome", {})
            if by_outcome:
                labels = [OUTCOME_LABELS.get(k, k) for k in by_outcome]
                values = list(by_outcome.values())
                colors = [OUTCOME_COLORS.get(k, "#ccc") for k in by_outcome]
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    marker=dict(colors=colors),
                    hole=0.45, textinfo="label+percent",
                ))
                fig.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), height=240,
                    showlegend=False,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        with cc2:
            st.markdown('<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin-bottom:6px;">Cumulative Net P&L (₹)</div>', unsafe_allow_html=True)
            _closed_dated = sorted(
                [s for s in closed_signals if s.get("outcome_at")],
                key=lambda x: x["outcome_at"],
            )
            if _closed_dated:
                dates, cum = [], []
                running = 0.0
                for s in _closed_dated:
                    val = s.get("net_pnl_inr")
                    if val is None:
                        r   = s.get("pnl_r") or 0.0
                        sl  = (s.get("sl_pct") or 2.0) / 100
                        val = r * sl * float(position_size)
                    running += val
                    dates.append(s["outcome_at"][:10])
                    cum.append(running)

                lc = "#00C896" if running >= 0 else "#ff4d6d"
                fc = "rgba(0,200,150,0.08)" if running >= 0 else "rgba(255,77,109,0.08)"
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=dates, y=cum, mode="lines+markers",
                    line=dict(color=lc, width=2), marker=dict(size=4),
                    fill="tozeroy", fillcolor=fc,
                    hovertemplate="Date: %{x}<br>Net P&L: ₹%{y:+,.0f}<extra></extra>",
                ))
                fig2.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.15)")
                fig2.update_layout(
                    yaxis_title="₹", margin=dict(t=10, b=30, l=50, r=10), height=240,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.caption("No closed trades yet.")

        # ── Strategy breakdown ────────────────────────────────────────────────
        by_strat = perf.get("by_strategy", {})
        if by_strat:
            st.markdown('<div style="font-size:0.78rem;font-weight:700;color:#94a3b8;margin:16px 0 8px;">By Strategy</div>', unsafe_allow_html=True)
            s_rows = []
            for sname, s in by_strat.items():
                s_closed = s["wins"] + s["losses"]
                s_rows.append({
                    "Strategy":  sname,
                    "Trades":    s["total"],
                    "Won":       s["wins"],
                    "Stopped":   s["losses"],
                    "Win Rate":  f"{s['win_rate']}%" if s_closed > 0 else "—",
                    "Avg R":     f"{s['avg_r']:+.2f}R" if s.get("avg_r") is not None else "—",
                    "Net P&L":   f"₹{s['net_pnl_inr']:+,.0f}" if s.get("net_pnl_inr") is not None else "—",
                })
            st.dataframe(pd.DataFrame(s_rows).set_index("Strategy"), use_container_width=True)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 3 — HISTORY                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with tab_hist:
    if not signals:
        st.caption("No signals in the selected period. Change the Period filter or run a scan.")
    else:
        # Build table (all signals, open + closed)
        rows = []
        for s in sorted(signals, key=lambda x: x["signal_date"], reverse=True):
            badge_l, badge_c = OUTCOME_BADGE.get(s["outcome"], (s["outcome"], "#6b7a99"))
            rows.append({
                "Date":      s["signal_date"],
                "Ticker":    s["ticker"].replace(".NS", ""),
                "TF":        s["timeframe"],
                "Dir":       s["direction"],
                "Strategy":  s["strategy"],
                "Entry ₹":   round(s["entry_price"], 2),
                "Exit ₹":    round(s.get("outcome_price") or 0, 2) or None,
                "SL ₹":      round(s["stop_loss"], 2),
                "T1 ₹":      round(s["target_1"], 2),
                "T2 ₹":      round(s["target_2"], 2),
                "Outcome":   s["outcome"],
                "R":         round(s["pnl_r"], 2) if s.get("pnl_r") is not None else None,
                "Net P&L ₹": round(s["net_pnl_inr"], 2) if s.get("net_pnl_inr") is not None else None,
                "Conf":      s.get("confidence") or 1,
                "Exit Time": (s.get("outcome_at") or "")[:16],
            })

        df_j = pd.DataFrame(rows)

        def _pnl_style(v):
            if v is None or v == "": return ""
            try:
                f = float(v)
                return "color:#00C896;font-weight:600" if f > 0 else ("color:#ff4d6d;font-weight:600" if f < 0 else "")
            except (TypeError, ValueError):
                return ""

        styled = (
            df_j.style
            .map(_pnl_style, subset=["R", "Net P&L ₹"])
            .format({
                "Entry ₹":   lambda v: f"₹{v:,.2f}" if v else "",
                "Exit ₹":    lambda v: f"₹{v:,.2f}" if v else "—",
                "SL ₹":      lambda v: f"₹{v:,.2f}" if v else "",
                "T1 ₹":      lambda v: f"₹{v:,.2f}" if v else "",
                "T2 ₹":      lambda v: f"₹{v:,.2f}" if v else "",
                "R":         lambda v: f"{v:+.2f}R" if v is not None else "—",
                "Net P&L ₹": lambda v: f"₹{v:+,.0f}" if v is not None else "—",
                "Conf":      lambda v: "★" * int(v),
            }, na_rep="—")
        )
        st.dataframe(styled, use_container_width=True, height=500, hide_index=True)

        csv = df_j.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇ Download CSV",
            data=csv,
            file_name=f"signal_log_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        with st.expander("Transaction Cost Model"):
            st.markdown(f"""
| Charge | Intraday | Swing |
|--------|----------|-------|
| Brokerage | ₹20/order × 2 | ₹20/order × 2 |
| STT | 0.025% sell-side | 0.1% turnover |
| Exchange (NSE) | 0.00345% | 0.00345% |
| Stamp Duty | 0.003% buy | 0.015% buy |
| GST | 18% on charges | 18% on charges |

*Position size: ₹{int(position_size):,} · figures scale linearly*
""")
