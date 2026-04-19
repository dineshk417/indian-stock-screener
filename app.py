"""
ShareSaathi — Main App (single-page feed)
"""
import logging
import threading
import datetime as _dt
import streamlit as st
import pytz as _pytz
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
_IST   = _pytz.timezone("Asia/Kolkata")


@st.cache_resource
def _start_scheduler():
    try:
        from scheduler.jobs import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")


def _catchup_signals():
    from datetime import date
    from data.market_status import is_trading_day
    from datetime import datetime

    ist = _pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    today = date.today().isoformat()

    try:
        from signals.signal_logger import get_signal_logger
        existing = get_signal_logger().get_signals(days_back=1)
        if any(s.get("signal_date") == today for s in existing):
            return
    except Exception:
        return

    def _generate():
        try:
            from signals.swing_signals import generate_swing_signals
            from config.stock_universe import NIFTY_50
            tickers = list(NIFTY_50.values())
            generate_swing_signals(tickers)
            if is_trading_day() and (now.hour > 9 or (now.hour == 9 and now.minute >= 30)):
                if now.hour < 15 or (now.hour == 15 and now.minute < 30):
                    from signals.intraday_signals import generate_intraday_signals
                    generate_intraday_signals(tickers)
        except Exception as e:
            logger.error(f"Catch-up signal generation failed: {e}")

    threading.Thread(target=_generate, daemon=True).start()


_start_scheduler()
try:
    from signals.signal_logger import get_signal_logger as _gl
    _gl().purge_non_trading_day_signals()
except Exception:
    pass
_catchup_signals()

st.set_page_config(
    page_title="ShareSaathi — AI Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "ShareSaathi — AI-powered stock analysis for Indian retail investors."},
)

from ui.styles import inject_global_css
inject_global_css()

# Inject horizontal-scroll CSS
st.markdown("""
<style>
.h-scroll {
    display:flex !important; overflow-x:auto !important; gap:12px !important;
    padding-bottom:6px !important; -webkit-overflow-scrolling:touch !important;
    scrollbar-width:none !important;
}
.h-scroll::-webkit-scrollbar { display:none !important; }
.feed-card {
    background:linear-gradient(145deg,#131929,#0f1420);
    border:1px solid rgba(255,255,255,0.06);border-radius:16px;
    padding:18px 20px;margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

from data.market_status import market_status, is_market_open
status  = market_status()
is_open = status["is_market_open"]
is_pre  = status["is_pre_market"]

_sc    = "#00c896" if is_open else ("#f0b429" if is_pre else "#ff4d6d")
_rgb   = "0,200,150" if is_open else ("240,180,41" if is_pre else "255,77,109")
_pulse = "animation:pulse 1.4s ease-in-out infinite;" if (is_open or is_pre) else ""
_now   = _dt.datetime.now(_IST).strftime("%H:%M IST")

# ── TOP HEADER ─────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="display:flex;align-items:center;justify-content:space-between;'
    f'padding:10px 0 18px;">'
    f'<div>'
    f'<div style="font-size:1.6rem;font-weight:900;letter-spacing:-0.03em;color:#f1f5f9;">'
    f'Share<span style="background:linear-gradient(135deg,#f0b429,#f97316);'
    f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Saathi</span></div>'
    f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;">AI-powered stock analysis · NSE/BSE</div>'
    f'</div>'
    f'<div style="display:flex;align-items:center;gap:8px;">'
    f'<div style="display:inline-flex;align-items:center;gap:6px;'
    f'background:rgba({_rgb},0.1);border:1px solid rgba({_rgb},0.25);'
    f'border-radius:20px;padding:5px 12px;">'
    f'<div style="width:7px;height:7px;border-radius:50%;background:{_sc};{_pulse}flex-shrink:0;"></div>'
    f'<span style="color:{_sc};font-size:0.72rem;font-weight:700;">{status["status_label"].split("(")[0].strip()}</span>'
    f'</div>'
    f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);'
    f'border-radius:20px;padding:5px 12px;font-size:0.72rem;color:#475569;">{_now}</div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── TABS ────────────────────────────────────────────────────────────────────────
t_home, t_signals, t_news, t_screener, t_tools = st.tabs([
    "🏠 Home", "💹 Signals", "📰 News", "🔍 Screener", "🛠️ Tools"
])

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — HOME                                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with t_home:

    # ── HERO BANNER ────────────────────────────────────────────────────────────
    @st.cache_data(ttl=120)
    def _hero_indices():
        from data.fetcher import fetch_index_data
        from config.settings import INDICES
        import yfinance as yf
        results = {}
        for name in ["Nifty 50", "Bank Nifty", "Sensex"]:
            ticker = INDICES.get(name)
            if not ticker:
                continue
            df = fetch_index_data(ticker, period="5d", interval="1d")
            if df is None or len(df) < 2:
                continue
            try:
                if is_open:
                    fi    = yf.Ticker(ticker).fast_info
                    price = float(fi.last_price)
                    prev  = float(fi.previous_close)
                    chg   = (price - prev) / prev * 100
                else:
                    price = float(df["Close"].iloc[-1])
                    chg   = (price - float(df["Close"].iloc[-2])) / float(df["Close"].iloc[-2]) * 100
                results[name] = {"price": price, "chg": chg}
            except Exception:
                pass
        return results

    indices = _hero_indices()
    nifty   = indices.get("Nifty 50", {})
    sensex  = indices.get("Sensex", {})
    bnk     = indices.get("Bank Nifty", {})

    if nifty:
        n_price = nifty["price"]; n_chg = nifty["chg"]
        n_col   = "#00c896" if n_chg >= 0 else "#ff4d6d"
        n_arrow = "▲" if n_chg >= 0 else "▼"
        n_bg    = "0,200,150" if n_chg >= 0 else "255,77,109"

        st.markdown(
            f'<div style="background:linear-gradient(145deg,#0d1117 0%,#111827 60%,#0d1117 100%);'
            f'border:1px solid rgba({n_bg},0.18);border-radius:20px;'
            f'padding:28px 28px 24px;margin-bottom:16px;position:relative;overflow:hidden;">'
            f'<div style="position:absolute;top:-50px;right:-50px;width:220px;height:220px;'
            f'background:radial-gradient(circle,rgba({n_bg},0.1),transparent 65%);pointer-events:none;"></div>'
            f'<div style="position:relative;z-index:1;">'
            f'<div style="font-size:0.65rem;font-weight:700;color:#475569;'
            f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">NIFTY 50 · NSE</div>'
            f'<div style="font-size:2.6rem;font-weight:900;color:#f1f5f9;'
            f'letter-spacing:-0.04em;line-height:1;">{n_price:,.2f}</div>'
            f'<div style="display:flex;align-items:center;gap:14px;margin-top:10px;">'
            f'<span style="font-size:1.1rem;font-weight:700;color:{n_col};">'
            f'{n_arrow} {abs(n_chg):.2f}% today</span>'
            + (f'<span style="font-size:0.82rem;color:#475569;">Sensex {sensex["price"]:,.0f} '
               f'{"▲" if sensex["chg"]>=0 else "▼"} {abs(sensex["chg"]):.2f}%</span>'
               if sensex else "")
            + f'</div></div></div>',
            unsafe_allow_html=True,
        )

    # ── QUICK STAT CARDS (horizontal scroll) ───────────────────────────────────
    @st.cache_data(ttl=300)
    def _quick_stats():
        try:
            log     = get_signal_logger()
            perf    = log.get_performance_summary(days_back=30)
            today   = _dt.date.today().isoformat()
            today_s = log.get_signals(days_back=1)
            today_count = sum(1 for s in today_s if s.get("signal_date") == today)
            return {
                "today": today_count,
                "open":  perf.get("open", 0),
                "wr":    perf.get("win_rate", 0),
                "total": perf.get("total", 0),
            }
        except Exception:
            return {"today": 0, "open": 0, "wr": 0, "total": 0}

    qs = _quick_stats()

    _cards = [
        ("Today's Signals", str(qs["today"]),  "new",       "#f0b429", "240,180,41"),
        ("Open Positions",  str(qs["open"]),   "tracking",  "#7c83fd", "124,131,253"),
        ("Win Rate (30d)",  f'{qs["wr"]}%',    "closed",    "#00c896", "0,200,150"),
        ("Total Signals",   str(qs["total"]),  "all time",  "#06b6d4", "6,182,212"),
    ]
    if bnk:
        b_col = "#00c896" if bnk["chg"] >= 0 else "#ff4d6d"
        b_rgb = "0,200,150" if bnk["chg"] >= 0 else "255,77,109"
        _cards.append((
            "Bank Nifty",
            f'{bnk["price"]:,.0f}',
            f'{"▲" if bnk["chg"]>=0 else "▼"} {abs(bnk["chg"]):.2f}%',
            b_col, b_rgb,
        ))

    cards_html = "".join([
        f'<div style="flex-shrink:0;width:140px;background:linear-gradient(145deg,#131929,#0f1420);'
        f'border:1px solid rgba({rgb},0.2);border-top:3px solid {col};'
        f'border-radius:14px;padding:14px 16px;">'
        f'<div style="font-size:0.62rem;font-weight:700;color:#475569;'
        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">{label}</div>'
        f'<div style="font-size:1.35rem;font-weight:800;color:{col};letter-spacing:-0.02em;">{val}</div>'
        f'<div style="font-size:0.65rem;color:#374151;margin-top:3px;">{sub}</div>'
        f'</div>'
        for label, val, sub, col, rgb in _cards
    ])
    st.markdown(f'<div class="h-scroll">{cards_html}</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom:20px;"></div>', unsafe_allow_html=True)

    # ── TODAY'S SIGNALS FEED ───────────────────────────────────────────────────
    @st.cache_data(ttl=180)
    def _today_signals():
        try:
            log   = get_signal_logger()
            today = _dt.date.today().isoformat()
            return [s for s in log.get_signals(days_back=1) if s.get("signal_date") == today]
        except Exception:
            return []

    today_sigs = _today_signals()
    _STRAT_COLORS = {
        "Trend Pullback": "#7c83fd", "Volume Breakout": "#f0b429",
        "Oversold Reversal": "#a855f7", "Bullish Setup": "#00c896",
        "Golden Cross": "#fbbf24", "Supertrend Reversal": "#06b6d4",
        "Opening Range Breakout": "#10b981", "VWAP Bounce": "#f472b6",
        "EMA Crossover": "#60a5fa", "Supertrend Signal": "#8b5cf6",
    }

    st.markdown(
        f'<div style="font-size:0.68rem;font-weight:700;color:#475569;'
        f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;">'
        f'{"Today\'s Signals — " + str(len(today_sigs)) + " ideas" if today_sigs else "No signals logged today"}</div>',
        unsafe_allow_html=True,
    )

    if today_sigs:
        sig_cards_html = "".join([
            f'<div style="flex-shrink:0;width:190px;background:linear-gradient(145deg,#131929,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.06);'
            f'border-left:3px solid {"#00c896" if s.get("direction")=="LONG" else "#ff4d6d"};'
            f'border-radius:14px;padding:14px 16px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span style="font-size:0.95rem;font-weight:800;color:#f1f5f9;">'
            f'{s["ticker"].replace(".NS","")}</span>'
            f'<span style="font-size:0.6rem;font-weight:700;'
            f'color:{"#00c896" if s.get("direction")=="LONG" else "#ff4d6d"};">'
            f'{"↑ LONG" if s.get("direction")=="LONG" else "↓ SHORT"}</span>'
            f'</div>'
            f'<div style="font-size:0.65rem;color:{_STRAT_COLORS.get(s.get("strategy",""),"#6b7a99")};'
            f'font-weight:600;margin-bottom:8px;">{s.get("strategy","")}</div>'
            f'<div style="display:flex;justify-content:space-between;">'
            f'<div><div style="font-size:0.58rem;color:#374151;">Entry</div>'
            f'<div style="font-size:0.78rem;font-weight:700;color:#e2e8f0;">₹{s.get("entry_price",0):,.0f}</div></div>'
            f'<div><div style="font-size:0.58rem;color:#374151;">T1</div>'
            f'<div style="font-size:0.78rem;font-weight:700;color:#00c896;">₹{s.get("target_1",0):,.0f}</div></div>'
            f'<div><div style="font-size:0.58rem;color:#374151;">SL</div>'
            f'<div style="font-size:0.78rem;font-weight:700;color:#ff4d6d;">₹{s.get("stop_loss",0):,.0f}</div></div>'
            f'</div></div>'
            for s in today_sigs[:8]
        ])
        st.markdown(f'<div class="h-scroll">{sig_cards_html}</div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-bottom:4px;"></div>', unsafe_allow_html=True)
        st.page_link("pages/7_Signal_Log.py", label="View full journal →")
    else:
        st.markdown(
            '<div class="feed-card" style="text-align:center;padding:24px;">'
            '<div style="font-size:1.4rem;margin-bottom:6px;">📭</div>'
            '<div style="color:#475569;font-size:0.85rem;">No signals yet today</div>'
            '<div style="color:#374151;font-size:0.75rem;margin-top:4px;">Run a scan from the Signals tab</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── MARKET MOVERS ──────────────────────────────────────────────────────────
    @st.cache_data(ttl=300)
    def _movers():
        try:
            from data.fetcher import fetch_stock_data
            from config.stock_universe import NIFTY_50
            tickers = list(NIFTY_50.values())
            price_data = fetch_stock_data(tickers, period="5d", interval="1d")
            changes = []
            for t, df in price_data.items():
                if df is None or len(df) < 2:
                    continue
                curr = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                changes.append({"ticker": t.replace(".NS",""), "price": curr,
                                 "chg": (curr - prev) / prev * 100})
            changes.sort(key=lambda x: x["chg"], reverse=True)
            return changes[:4], changes[-4:][::-1]
        except Exception:
            return [], []

    gainers, losers = _movers()

    if gainers or losers:
        st.markdown(
            '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
            'text-transform:uppercase;letter-spacing:0.1em;margin:20px 0 12px;">Market Movers</div>',
            unsafe_allow_html=True,
        )
        g_col, l_col = st.columns(2)
        def _mover_card(items, is_gain):
            color = "#00c896" if is_gain else "#ff4d6d"
            rgb   = "0,200,150" if is_gain else "255,77,109"
            arrow = "▲" if is_gain else "▼"
            html  = (
                f'<div style="font-size:0.62rem;font-weight:700;color:{color};'
                f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
                f'{arrow} {"Gainers" if is_gain else "Losers"}</div>'
            )
            for item in items:
                html += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'background:rgba({rgb},0.05);border-radius:8px;padding:8px 12px;margin-bottom:5px;">'
                    f'<span style="font-weight:700;color:#e2e8f0;font-size:0.85rem;">{item["ticker"]}</span>'
                    f'<div style="text-align:right;">'
                    f'<div style="color:#64748b;font-size:0.72rem;">₹{item["price"]:,.1f}</div>'
                    f'<div style="color:{color};font-size:0.78rem;font-weight:700;">{arrow} {abs(item["chg"]):.2f}%</div>'
                    f'</div></div>'
                )
            return html

        with g_col:
            st.markdown(_mover_card(gainers, True), unsafe_allow_html=True)
        with l_col:
            st.markdown(_mover_card(losers, False), unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — SIGNALS                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with t_signals:
    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:16px;">Trade Signal Tools</div>',
        unsafe_allow_html=True,
    )
    _sig_tools = [
        ("💹", "Swing Trades", "2–5 day setups · 6 strategies · entry/SL/targets",
         "#00c896", "0,200,150", "pages/5_Swing_Trades.py"),
        ("⚡", "Intraday Ideas", "ORB · VWAP · EMA · Supertrend · live during market hours",
         "#60a5fa", "96,165,250", "pages/6_Intraday_Ideas.py"),
        ("📋", "Signal Journal", "Full trade log · win rate · P&L · strategy performance",
         "#7c83fd", "124,131,253", "pages/7_Signal_Log.py"),
    ]
    for icon, title, desc, col, rgb, page in _sig_tools:
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#141828,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.07);border-radius:14px;'
            f'display:flex;align-items:center;gap:14px;padding:14px 18px;margin-bottom:2px;">'
            f'<div style="width:42px;height:42px;min-width:42px;border-radius:12px;'
            f'background:rgba({rgb},0.12);display:flex;align-items:center;'
            f'justify-content:center;font-size:1.3rem;">{icon}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:700;color:#f1f5f9;font-size:0.88rem;">{title}</div>'
            f'<div style="color:#475569;font-size:0.72rem;margin-top:2px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{desc}</div>'
            f'</div>'
            f'<div style="color:#374151;font-size:1.1rem;flex-shrink:0;">›</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"Open {title} →")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 3 — NEWS                                                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with t_news:
    @st.cache_data(ttl=1800)
    def _home_news():
        try:
            from data.news_fetcher import fetch_market_news
            return fetch_market_news()[:12]
        except Exception:
            return []

    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px;">Latest Market News</div>',
        unsafe_allow_html=True,
    )
    headlines = _home_news()
    if headlines:
        for item in headlines:
            title = item.get("title", "")
            source = item.get("source", "")
            pub    = item.get("published_str", "")
            url    = item.get("url", "#")
            summary = item.get("summary", "")
            st.markdown(
                f'<div class="feed-card">'
                f'<a href="{url}" target="_blank" style="color:#93c5fd;text-decoration:none;'
                f'font-weight:600;font-size:0.875rem;line-height:1.45;">{title}</a>'
                f'<div style="display:flex;gap:8px;align-items:center;margin-top:6px;">'
                f'<span style="background:rgba(255,255,255,0.05);color:#475569;'
                f'border-radius:4px;padding:2px 8px;font-size:0.62rem;font-weight:600;">{source}</span>'
                f'<span style="color:#374151;font-size:0.68rem;">{pub}</span>'
                f'</div>'
                f'<div style="color:#374151;font-size:0.77rem;line-height:1.5;margin-top:6px;">'
                f'{summary[:160]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("News unavailable — check connection.")
    st.markdown('<div style="margin-top:4px;"></div>', unsafe_allow_html=True)
    st.page_link("pages/2_News_Sentiment.py", label="Full AI Sentiment Analysis →")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 4 — SCREENER                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with t_screener:
    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:16px;">Stock Screeners</div>',
        unsafe_allow_html=True,
    )
    _screeners = [
        ("🔍", "Fundamental Screener",
         "PE · ROE · Debt/Equity · Dividend Yield · Margin across Nifty 200",
         "#f0b429", "pages/3_Fundamental_Screener.py",
         ["Value Picks", "Quality Compounders", "Dividend Stars"]),
        ("📈", "Technical Screener",
         "RSI · MACD · Golden Cross · Volume Breakout · Trend analysis",
         "#60a5fa", "pages/4_Technical_Screener.py",
         ["Oversold", "Breakout", "Golden Cross", "Momentum"]),
        ("📊", "Market Overview",
         "Live indices · Sector heatmap · Market breadth · Top gainers/losers",
         "#00c896", "pages/1_Market_Overview.py",
         ["Nifty 50", "Bank Nifty", "Sensex"]),
    ]
    _screener_rgb = {"#f0b429": "240,180,41", "#60a5fa": "96,165,250", "#00c896": "0,200,150"}
    for icon, title, desc, col, page, tags in _screeners:
        rgb = _screener_rgb.get(col, "255,255,255")
        tags_html = " ".join([
            f'<span style="background:rgba({rgb},0.08);color:{col};'
            f'border-radius:10px;padding:1px 8px;font-size:0.6rem;font-weight:700;">{t}</span>'
            for t in tags
        ])
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#141828,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.07);border-radius:14px;'
            f'display:flex;align-items:center;gap:14px;padding:14px 18px;margin-bottom:2px;">'
            f'<div style="width:42px;height:42px;min-width:42px;border-radius:12px;'
            f'background:rgba({rgb},0.12);display:flex;align-items:center;'
            f'justify-content:center;font-size:1.3rem;">{icon}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:700;color:#f1f5f9;font-size:0.88rem;margin-bottom:3px;">{title}</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;">{tags_html}</div>'
            f'</div>'
            f'<div style="color:#374151;font-size:1.1rem;flex-shrink:0;">›</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"Open {title} →")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 5 — TOOLS                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with t_tools:
    st.markdown(
        '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
        'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:16px;">Utility Tools</div>',
        unsafe_allow_html=True,
    )
    _tools = [
        ("🛡️", "Tip Analyzer",
         "Paste any WhatsApp/Telegram stock tip — AI scores it for pump-and-dump risk",
         "#ff4d6d", "255,77,109", "pages/8_Tip_Analyzer.py"),
        ("📋", "Signal Journal",
         "Full trade log with P&L, win rate, strategy breakdown and CSV export",
         "#7c83fd", "124,131,253", "pages/7_Signal_Log.py"),
        ("📰", "News & Sentiment",
         "Claude AI analyses market news — summary, sector outlook, catalysts & risks",
         "#60a5fa", "96,165,250", "pages/2_News_Sentiment.py"),
    ]
    for icon, title, desc, col, rgb, page in _tools:
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#141828,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.07);border-radius:14px;'
            f'display:flex;align-items:center;gap:14px;padding:14px 18px;margin-bottom:2px;">'
            f'<div style="width:42px;height:42px;min-width:42px;border-radius:12px;'
            f'background:rgba({rgb},0.12);display:flex;align-items:center;'
            f'justify-content:center;font-size:1.3rem;">{icon}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:700;color:#f1f5f9;font-size:0.88rem;">{title}</div>'
            f'<div style="color:#475569;font-size:0.72rem;margin-top:2px;'
            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{desc}</div>'
            f'</div>'
            f'<div style="color:#374151;font-size:1.1rem;flex-shrink:0;">›</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"Open {title} →")

# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="margin-top:32px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.05);">'
    '<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
    '<span style="color:#374151;font-size:0.72rem;">⚠️ Educational purposes only · Not financial advice</span>'
    '<span style="color:#1e2535;font-size:0.7rem;">ShareSaathi · yfinance · Claude AI · Streamlit</span>'
    '</div></div>',
    unsafe_allow_html=True,
)
