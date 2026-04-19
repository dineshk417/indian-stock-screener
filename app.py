"""
Indian Stock Market Screener — Main Entry Point
Run with: streamlit run app.py
"""
import logging
import threading
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


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
    import pytz
    from datetime import datetime

    ist = pytz.timezone("Asia/Kolkata")
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
            # Intraday signals only make sense on live trading days
            if is_trading_day() and (now.hour > 9 or (now.hour == 9 and now.minute >= 30)):
                if now.hour < 15 or (now.hour == 15 and now.minute < 30):
                    from signals.intraday_signals import generate_intraday_signals
                    generate_intraday_signals(tickers)
        except Exception as e:
            logger.error(f"Catch-up signal generation failed: {e}")

    threading.Thread(target=_generate, daemon=True).start()


_start_scheduler()

try:
    from signals.signal_logger import get_signal_logger
    get_signal_logger().purge_non_trading_day_signals()
except Exception:
    pass

_catchup_signals()

st.set_page_config(
    page_title="ShareSaathi — AI Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "ShareSaathi — AI-powered stock analysis for Indian retail investors.",
    },
)

from ui.styles import inject_global_css
inject_global_css()

from data.market_status import market_status
status       = market_status()
is_open      = status["is_market_open"]
is_pre       = status["is_pre_market"]
status_color = "#00c896" if is_open else ("#f0b429" if is_pre else "#ff4d6d")
status_label = status["status_label"]
status_time  = status["datetime_ist"]

pill_rgb   = "0,200,150" if is_open else ("240,180,41" if is_pre else "255,77,109")
pulse_anim = "animation:pulse 1.5s infinite;" if (is_open or is_pre) else ""

# ── Hero ─────────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="background:linear-gradient(145deg,#0d1117 0%,#111827 60%,#0d1117 100%);'
    f'border:1px solid rgba(255,255,255,0.07);border-radius:24px;'
    f'padding:44px 48px 40px;margin-bottom:24px;position:relative;overflow:hidden;">'

    # Decorative glows
    f'<div style="position:absolute;top:-80px;right:-80px;width:360px;height:360px;'
    f'background:radial-gradient(circle,rgba(240,180,41,0.09),transparent 65%);pointer-events:none;"></div>'
    f'<div style="position:absolute;bottom:-60px;left:160px;width:280px;height:280px;'
    f'background:radial-gradient(circle,rgba(0,200,150,0.06),transparent 65%);pointer-events:none;"></div>'
    f'<div style="position:absolute;top:40px;right:200px;width:180px;height:180px;'
    f'background:radial-gradient(circle,rgba(124,131,253,0.06),transparent 65%);pointer-events:none;"></div>'

    f'<div style="position:relative;z-index:1;">'

    # Status pill
    f'<div style="display:inline-flex;align-items:center;gap:7px;'
    f'background:rgba({pill_rgb},0.12);border:1px solid rgba({pill_rgb},0.3);'
    f'border-radius:20px;padding:5px 14px;font-size:0.7rem;font-weight:700;'
    f'color:{status_color};letter-spacing:0.08em;text-transform:uppercase;margin-bottom:22px;">'
    f'<span style="width:7px;height:7px;border-radius:50%;background:{status_color};{pulse_anim}display:inline-block;flex-shrink:0;"></span>'
    f'&nbsp;{status_label}&nbsp;&middot;&nbsp;{status_time}</div>'

    # Title
    f'<div style="font-size:2.8rem;font-weight:900;margin:0 0 14px;letter-spacing:-0.04em;'
    f'line-height:1.1;color:#f1f5f9;">Share<span style="background:linear-gradient(135deg,#f0b429,#f97316);'
    f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Saathi</span></div>'

    # Tagline
    f'<p style="color:#64748b;font-size:1rem;margin:0 0 28px;line-height:1.7;max-width:520px;">'
    f'AI-powered stock analysis for Indian retail investors — technical &amp; fundamental '
    f'screening, live signals, swing trades and a WhatsApp tip detector, all in one place.</p>'

    # Stats row
    f'<div style="display:flex;gap:20px;flex-wrap:wrap;">'
    f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
    f'border-radius:12px;padding:10px 18px;min-width:90px;">'
    f'<div style="font-size:1.3rem;font-weight:800;color:#f1f5f9;">200+</div>'
    f'<div style="font-size:0.65rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Stocks</div>'
    f'</div>'
    f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
    f'border-radius:12px;padding:10px 18px;min-width:90px;">'
    f'<div style="font-size:1.3rem;font-weight:800;color:#f0b429;">10</div>'
    f'<div style="font-size:0.65rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Strategies</div>'
    f'</div>'
    f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
    f'border-radius:12px;padding:10px 18px;min-width:90px;">'
    f'<div style="font-size:1.3rem;font-weight:800;color:#7c83fd;">8</div>'
    f'<div style="font-size:0.65rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Tools</div>'
    f'</div>'
    f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
    f'border-radius:12px;padding:10px 18px;min-width:90px;">'
    f'<div style="font-size:1.3rem;font-weight:800;color:#00c896;">AI</div>'
    f'<div style="font-size:0.65rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Powered</div>'
    f'</div>'
    f'</div>'

    f'</div></div>',
    unsafe_allow_html=True,
)

# ── Quick access strip ────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
    'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:12px;">Quick Access</div>',
    unsafe_allow_html=True,
)

qa_cols = st.columns([1, 1, 1, 1])
quick = [
    ("pages/1_Market_Overview.py", "📊 Market Overview", is_open),
    ("pages/5_Swing_Trades.py",    "💹 Swing Trades",    True),
    ("pages/6_Intraday_Ideas.py",  "⚡ Intraday Ideas",  is_open),
    ("pages/8_Tip_Analyzer.py",    "🛡️ Tip Analyzer",   True),
]
for col, (page, label, active) in zip(qa_cols, quick):
    with col:
        st.page_link(page, label=label)

st.markdown('<div style="margin-bottom:24px;"></div>', unsafe_allow_html=True)

# ── Feature cards ─────────────────────────────────────────────────────────────────
FEATURES = [
    {
        "icon": "📊",
        "title": "Market Overview",
        "desc": "Live Nifty 50, Bank Nifty & Sensex with YTD chart, sector heatmap, and top movers.",
        "page": "pages/1_Market_Overview.py",
        "tag": "LIVE" if is_open else "EOD",
        "tag_color": "#00c896" if is_open else "#f0b429",
        "accent": "#00c896",
    },
    {
        "icon": "📰",
        "title": "News & Sentiment",
        "desc": "Claude AI reads overnight news and delivers a market summary with sector outlook.",
        "page": "pages/2_News_Sentiment.py",
        "tag": "AI",
        "tag_color": "#7c83fd",
        "accent": "#7c83fd",
    },
    {
        "icon": "🔍",
        "title": "Fundamental Screener",
        "desc": "Filter by PE, ROE, market cap, debt-to-equity, revenue growth across Nifty 200.",
        "page": "pages/3_Fundamental_Screener.py",
        "tag": "VALUE",
        "tag_color": "#f0b429",
        "accent": "#f0b429",
    },
    {
        "icon": "📈",
        "title": "Technical Screener",
        "desc": "Scan for RSI, MACD, Golden Cross, volume breakouts. Presets: Oversold · Breakout · Momentum.",
        "page": "pages/4_Technical_Screener.py",
        "tag": "SCAN",
        "tag_color": "#f97316",
        "accent": "#f97316",
    },
    {
        "icon": "💹",
        "title": "Swing Trades",
        "desc": "2–5 day trade ideas with entry, stop-loss and two profit targets. 6 active strategies.",
        "page": "pages/5_Swing_Trades.py",
        "tag": "SIGNALS",
        "tag_color": "#00c896",
        "accent": "#00c896",
    },
    {
        "icon": "⚡",
        "title": "Intraday Ideas",
        "desc": "ORB, VWAP Bounce, EMA Crossover, Supertrend signals — live during market hours.",
        "page": "pages/6_Intraday_Ideas.py",
        "tag": "LIVE" if is_open else "9:15–15:30",
        "tag_color": "#00c896" if is_open else "#475569",
        "accent": "#60a5fa",
    },
    {
        "icon": "📋",
        "title": "Signal Log",
        "desc": "Every signal tracked with outcome — win rate, P&L, and exportable trade history.",
        "page": "pages/7_Signal_Log.py",
        "tag": "JOURNAL",
        "tag_color": "#7c83fd",
        "accent": "#7c83fd",
    },
    {
        "icon": "🛡️",
        "title": "Tip Analyzer",
        "desc": "Paste any WhatsApp or Telegram stock tip — AI scores it for pump-and-dump risk.",
        "page": "pages/8_Tip_Analyzer.py",
        "tag": "AI",
        "tag_color": "#ff4d6d",
        "accent": "#ff4d6d",
    },
]

st.markdown(
    '<div style="font-size:0.68rem;font-weight:700;color:#475569;'
    'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px;">All Tools</div>',
    unsafe_allow_html=True,
)

cols = st.columns(2)
for i, feat in enumerate(FEATURES):
    with cols[i % 2]:
        tag_html = (
            f'<span style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;'
            f'color:{feat["tag_color"]};background:{feat["tag_color"]}20;'
            f'border:1px solid {feat["tag_color"]}40;'
            f'border-radius:4px;padding:2px 8px;">{feat["tag"]}</span>'
        )
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#131929,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.06);border-top:3px solid {feat["accent"]};'
            f'border-radius:16px;padding:20px 22px;margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">'
            f'<span style="font-size:1.8rem;line-height:1;">{feat["icon"]}</span>'
            f'{tag_html}</div>'
            f'<div style="font-size:0.95rem;font-weight:700;color:#e2e8f0;margin-bottom:6px;">{feat["title"]}</div>'
            f'<div style="font-size:0.78rem;color:#475569;line-height:1.6;">{feat["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.page_link(feat["page"], label=f"Open →")

# ── Footer ────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="margin-top:32px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06);'
    'display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">'
    '<span style="color:#374151;font-size:0.73rem;">'
    '⚠️ Educational purposes only — not financial advice. Do your own research.'
    '</span>'
    '<span style="color:#1e2535;font-size:0.7rem;">ShareSaathi · yfinance · Claude AI · Streamlit</span>'
    '</div>',
    unsafe_allow_html=True,
)
