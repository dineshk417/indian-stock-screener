"""
Page 5: Swing Trade Recommendations (2-5 days)
"""
import streamlit as st
from collections import Counter
from data.fetcher import fetch_single_stock
from data.news_fetcher import fetch_market_news, format_news_for_claude
from analysis.technical import compute_indicators
from analysis.sentiment import analyze_market_sentiment
from signals.swing_signals import generate_swing_signals
from ui.components import signal_card

_STRATEGY_COLORS = {
    "Trend Pullback":         "#7c83fd",
    "Volume Breakout":        "#f0b429",
    "Oversold Reversal":      "#a855f7",
    "Bullish Setup":          "#00c896",
    "Golden Cross":           "#fbbf24",
    "Supertrend Reversal":    "#06b6d4",
    "Opening Range Breakout": "#10b981",
    "VWAP Bounce":            "#f472b6",
    "EMA Crossover":          "#60a5fa",
    "Supertrend Signal":      "#8b5cf6",
}
from ui.charts import candlestick_chart, rsi_macd_chart
from config.stock_universe import NIFTY_50, NIFTY_200

st.set_page_config(page_title="Swing Trades · ShareSaathi", layout="wide", page_icon="💹")
from ui.styles import inject_global_css; inject_global_css()

# ── PAGE HEADER ────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="margin-bottom:4px;">'
    '<span style="font-size:0.72rem;font-weight:700;color:#64748b;'
    'text-transform:uppercase;letter-spacing:0.1em;">NSE · Equity · 2–5 Day Hold</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.title("💹 Swing Trade Ideas")

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    universe_choice = st.selectbox("Universe", ["Nifty 50", "Nifty 200"])
    universe = NIFTY_50 if universe_choice == "Nifty 50" else NIFTY_200
    tickers  = list(universe.values())

    st.subheader("Filters")
    min_confidence = st.slider("Min Confidence", 1, 5, 2)

    all_strategies = [
        "Trend Pullback", "Volume Breakout", "Oversold Reversal",
        "Bullish Setup", "Golden Cross", "Supertrend Reversal",
    ]
    selected_strategies = st.multiselect("Strategy", all_strategies, default=all_strategies)
    run_btn = st.button("🔄 Generate Signals", type="primary", width="stretch")

    st.divider()
    with st.expander("📋 Strategy Criteria", expanded=False):
        st.markdown("""
**Trend Pullback** — Close > SMA50 > SMA200, price within 5% of EMA21, RSI 35–65

**Volume Breakout** — Above SMA200, RSI 50–75, volume ≥ 1.5× avg

**Oversold Reversal** — RSI < 40, fundamental score > 0.35

**Bullish Setup** — Above SMA200, MACD bullish, RSI < 70

**Golden Cross** — SMA50 crossed above SMA200 within 20 bars

**Supertrend Reversal** — Supertrend flipped bull within 5 bars, MACD bullish
""")

# ── SENTIMENT ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_sentiment_score():
    news   = fetch_market_news()
    result = analyze_market_sentiment(
        format_news_for_claude(news, max_items=25),
        news_items=news,
    )
    return result.get("overall_sentiment", 5) / 10

# ── SCAN FACTS (shown during scan) ─────────────────────────────────────────────
_SCAN_FACTS = [
    ("📊 RSI & Momentum",      "RSI between 35–65 is the sweet spot for swing entries — not oversold, not overbought. We look for momentum without exhaustion."),
    ("📈 Trend Pullback",      "Best swing trades enter during a pullback within an uptrend. Price above SMA50 and SMA200 confirms the trend; EMA21 is our pullback target."),
    ("🕯️ Volume Confirmation", "Volume 1.5× average during a breakout signals institutional participation — not just retail noise. We require it for Volume Breakout signals."),
    ("✨ Golden Cross",        "SMA50 crossing above SMA200 is one of the most historically reliable long-term bullish signals in Indian equity markets."),
    ("🛡️ ATR-Based Stops",    "Stop-losses are set at 1.5× ATR from entry. ATR adapts to each stock's volatility so stops are neither too tight nor too wide."),
    ("⚡ Supertrend Reversal", "When Supertrend flips from bearish to bullish and MACD confirms, it often marks the start of a new swing leg — we catch it within 5 bars."),
]

# ── SCAN ───────────────────────────────────────────────────────────────────────
if run_btn or "swing_signals" not in st.session_state:
    try:
        sentiment_score = get_sentiment_score()
    except Exception:
        sentiment_score = 0.5

    scan_slot = st.empty()

    def _on_tick(ticker, strategies, done, total):
        label   = ticker.replace(".NS", "")
        pct     = max(4, done / total * 96)
        fact    = _SCAN_FACTS[(done - 1) % len(_SCAN_FACTS)]
        found   = f" · {len(strategies)} signal{'s' if len(strategies) != 1 else ''}" if strategies else ""
        scan_slot.markdown(
            f'<div style="background:linear-gradient(145deg,#131929,#0f1420);'
            f'border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:22px 26px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
            f'<span style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;'
            f'text-transform:uppercase;color:#475569;">Scanning {label}{found}</span>'
            f'<span style="font-size:0.72rem;color:#f0b429;font-weight:700;">{done} / {total}</span>'
            f'</div>'
            f'<div style="background:rgba(255,255,255,0.06);border-radius:99px;'
            f'height:4px;margin-bottom:18px;overflow:hidden;">'
            f'<div style="width:{pct:.1f}%;height:100%;'
            f'background:linear-gradient(90deg,#f0b429,#00c896);border-radius:99px;"></div></div>'
            f'<div style="font-size:0.88rem;font-weight:700;color:#e2e8f0;margin-bottom:5px;">{fact[0]}</div>'
            f'<div style="font-size:0.8rem;color:#64748b;line-height:1.6;">{fact[1]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    try:
        signals = generate_swing_signals(tickers, sentiment_score=sentiment_score, on_tick=_on_tick)
    except Exception as _e:
        st.error(f"Signal generation failed: {_e}. Please try again.")
        signals = []

    scan_slot.empty()
    st.session_state.swing_signals        = signals
    st.session_state.swing_sentiment_score = sentiment_score

    if signals:
        import datetime as _dt2
        st.markdown(
            f'<div style="background:rgba(0,200,150,0.06);border:1px solid rgba(0,200,150,0.2);'
            f'border-radius:10px;padding:10px 16px;display:flex;align-items:center;gap:10px;margin-bottom:4px;">'
            f'<span style="color:#00c896;font-size:1rem;">✓</span>'
            f'<span style="color:#00c896;font-weight:700;font-size:0.85rem;">'
            f'{len(signals)} signals logged to Trade Journal</span>'
            f'<span style="color:#475569;font-size:0.75rem;margin-left:auto;">'
            f'{_dt2.datetime.now().strftime("%H:%M:%S")}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

signals        = st.session_state.get("swing_signals", [])
sentiment_score = st.session_state.get("swing_sentiment_score", 0.5)

# ── STATS STRIP ────────────────────────────────────────────────────────────────
strategies_active = len(set(s.strategy for s in signals))
sentiment_label   = (
    "Very Bullish" if sentiment_score >= 0.8 else
    "Bullish"      if sentiment_score >= 0.6 else
    "Neutral"      if sentiment_score >= 0.4 else
    "Bearish"
)
sentiment_color = (
    "#00c896" if sentiment_score >= 0.6 else
    "#f0b429" if sentiment_score >= 0.4 else
    "#ff4d6d"
)

st.markdown(
    f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0;">'

    f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
    f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;">'
    f'<div style="color:#64748b;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.09em;margin-bottom:6px;">Signals Found</div>'
    f'<div style="color:#f1f5f9;font-size:1.6rem;font-weight:800;letter-spacing:-0.03em;">'
    f'{len(signals)}</div>'
    f'</div>'

    f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
    f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;">'
    f'<div style="color:#64748b;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.09em;margin-bottom:6px;">Sentiment</div>'
    f'<div style="color:{sentiment_color};font-size:1.6rem;font-weight:800;letter-spacing:-0.03em;">'
    f'{sentiment_score * 10:.1f}<span style="font-size:0.9rem;color:#475569;">/10</span></div>'
    f'<div style="color:{sentiment_color};font-size:0.7rem;font-weight:600;margin-top:2px;">'
    f'{sentiment_label}</div>'
    f'</div>'

    f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
    f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;">'
    f'<div style="color:#64748b;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.09em;margin-bottom:6px;">Universe</div>'
    f'<div style="color:#f1f5f9;font-size:1.6rem;font-weight:800;letter-spacing:-0.03em;">'
    f'{len(tickers)}<span style="font-size:0.9rem;color:#475569;"> stocks</span></div>'
    f'</div>'

    f'<div style="background:linear-gradient(145deg,#1a1f35,#141828);'
    f'border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:14px 16px;">'
    f'<div style="color:#64748b;font-size:0.65rem;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.09em;margin-bottom:6px;">Strategies Active</div>'
    f'<div style="color:#f1f5f9;font-size:1.6rem;font-weight:800;letter-spacing:-0.03em;">'
    f'{strategies_active}<span style="font-size:0.9rem;color:#475569;">/6</span></div>'
    f'</div>'

    f'</div>',
    unsafe_allow_html=True,
)

# ── STRATEGY BREAKDOWN CHIPS ───────────────────────────────────────────────────
if signals:
    strategy_counts = Counter(s.strategy for s in signals)
    chips = " ".join([
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{_STRATEGY_COLORS.get(k, "#6b7a99")}15;'
        f'color:{_STRATEGY_COLORS.get(k, "#6b7a99")};'
        f'border:1px solid {_STRATEGY_COLORS.get(k, "#6b7a99")}30;'
        f'border-radius:20px;padding:4px 12px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.03em;margin:3px 2px;">'
        f'{k} <span style="background:{_STRATEGY_COLORS.get(k,"#6b7a99")}25;'
        f'border-radius:10px;padding:0 6px;font-size:0.68rem;">{v}</span>'
        f'</span>'
        for k, v in sorted(strategy_counts.items(), key=lambda x: -x[1])
    ])
    st.markdown(
        f'<div style="margin:4px 0 20px;line-height:2;">{chips}</div>',
        unsafe_allow_html=True,
    )

# ── FILTERED SIGNALS ───────────────────────────────────────────────────────────
filtered = [
    s for s in signals
    if s.confidence >= min_confidence
    and (not selected_strategies or s.strategy in selected_strategies)
]

if not filtered:
    st.markdown(
        '<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        'border-radius:14px;padding:32px;text-align:center;margin:16px 0;">'
        '<div style="color:#475569;font-size:1rem;font-weight:600;margin-bottom:6px;">'
        'No signals match your filters</div>'
        '<div style="color:#374151;font-size:0.82rem;">'
        'Try lowering the confidence threshold or selecting more strategies</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

st.markdown(
    f'<div style="font-size:0.72rem;font-weight:700;color:#64748b;'
    f'text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">'
    f'Trade Signals — {len(filtered)} results</div>',
    unsafe_allow_html=True,
)

# ── SIGNAL CARDS ───────────────────────────────────────────────────────────────
for i, signal in enumerate(filtered):
    signal_card(signal.to_dict())
    strat_color = _STRATEGY_COLORS.get(signal.strategy, "#6b7a99")
    with st.expander(f"📊 {signal.ticker.replace('.NS','')} — Analysis & Chart", expanded=False):
        if signal.patterns:
            chips = " ".join([
                f'<span style="display:inline-block;background:{strat_color}12;color:{strat_color};'
                f'border:1px solid {strat_color}28;border-radius:4px;'
                f'padding:2px 8px;font-size:0.7rem;font-weight:600;margin:2px;">{p}</span>'
                for p in signal.patterns
            ])
            st.markdown(f'<div style="margin-bottom:10px;">{chips}</div>', unsafe_allow_html=True)
        if signal.reasoning:
            parts = [p.strip() for p in signal.reasoning.replace("Strategy:", "\nStrategy:").split(".") if len(p.strip()) > 6]
            for part in parts:
                st.caption(f"• {part.strip()}")
        df = fetch_single_stock(signal.ticker)
        if df is not None:
            df_ind = compute_indicators(df)
            fig = candlestick_chart(
                df_ind, signal.ticker,
                show_sma=True, show_volume=True,
                signal_lines={
                    "entry":     signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "target_1":  signal.target_1,
                    "target_2":  signal.target_2,
                },
            )
            st.plotly_chart(fig, use_container_width=True, key=f"candle_{i}_{signal.ticker}")
            st.plotly_chart(rsi_macd_chart(df_ind), use_container_width=True, key=f"rsi_{i}_{signal.ticker}")

st.divider()
st.caption(
    "⚠️ For educational purposes only. Do your own research. "
    "Past performance is not indicative of future results."
)
