#!/usr/bin/env python3
"""Autonomous improvement agent for NiftyEdge — runs via GitHub Actions 3× per day."""

import ast
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from groq import Groq

# Safe files to autonomously modify — ordered by complexity ascending
SAFE_FILES = [
    "pages/10_AI_Analyst.py",
    "pages/7_Fundamental_Screener.py",
    "pages/11_Portfolio_Health.py",
    "pages/5_Intraday_Ideas.py",
    "pages/8_News_Sentiment.py",
    "pages/6_Technical_Screener.py",
    "pages/9_Tip_Analyzer.py",
    "pages/4_Swing_Trades.py",
]

THEMES = [
    "Improve the AI/LLM prompt to produce richer, more specific, better-structured analysis",
    "Add a new metric card or data point that gives retail investors useful context (e.g. beta, ATR, delivery %, 52W position)",
    "Improve color coding — use green/red/amber more consistently to signal bullish/bearish/neutral states across the page",
    "Add a helpful empty state or user guidance message when data is unavailable or the user hasn't acted yet",
    "Improve the layout — better column proportions, spacing, and visual hierarchy to reduce clutter",
    "Add a new useful technical indicator or calculation (Bollinger Bands, ATR, volume surge %, sector relative strength)",
    "Improve data tables — better number formatting, conditional coloring for P&L, clearer column headers",
    "Add a plain-English interpretation panel that explains what the technical data means for a first-time investor",
    "Draw inspiration from Screener.in or Tickertape — identify a feature they offer that this page is missing and add it",
    "Improve the page header and subtitle to be more informative and descriptive for new users",
    "Add better error messages with actionable guidance (e.g. what to do when a stock fetch fails)",
    "Improve mobile responsiveness — stack columns on small screens, use compact number formats",
]

REQUIRED = ["st.set_page_config", "inject_global_css", "auth_guard"]

APP_CONTEXT = """\
NiftyEdge — AI-powered Indian stock screener for retail NSE/BSE investors.
Stack: Streamlit · yfinance · Plotly · Groq (llama-3.3-70b-versatile) · PostgreSQL/SQLite.

Design system (strictly follow):
- Page bg: #0d1117  |  Card bg: linear-gradient(145deg,#1a1f35,#141828)
- Card border: 1px solid rgba(255,255,255,0.07)  |  border-radius: 12px
- Accent: gold #f0b429, teal #00c896, red #ff4d6d, purple #8b5cf6, blue #3b82f6
- Page title: font-size:1.55rem; font-weight:900; color:#f1f5f9
- Subtitle: font-size:0.8rem; color:#64748b
- Label chip: font-size:0.58rem; color:#475569; font-weight:700; text-transform:uppercase; letter-spacing:0.07em
- Metric value: font-size:1.25rem; font-weight:800
- Metric sub: font-size:0.65rem; color:#374151

Competing apps to draw inspiration from: Screener.in (fundamentals, peer comparison),
Tickertape (portfolio analytics, goal planning), TradingView (charting, Pine indicators),
Zerodha Kite (clean UI, order flow), Moneycontrol (news, macro data), Smallcase (themes).

CRITICAL CONSTRAINTS:
- Every page must call inject_global_css() and auth_guard() near the top, in that order
- user_sidebar() must be called inside `with st.sidebar:`
- Never touch: signals/, scheduler/, notifications/, signals/signal_logger.py, auth logic, DB schema
- Cache fetched data with @st.cache_data(ttl=300, show_spinner=False)
- All st.markdown() calls with HTML need unsafe_allow_html=True\
"""


def pick_target(focus: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    slot = now.weekday() * 3 + now.hour // 8
    target = SAFE_FILES[slot % len(SAFE_FILES)]
    theme  = focus.strip() if focus.strip() else THEMES[slot % len(THEMES)]
    return target, theme


def strip_fences(text: str) -> str:
    text = text.strip()
    for prefix in ("```python", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def validate(new_code: str, original: str) -> str | None:
    if len(new_code) < len(original) * 0.6:
        return f"Output too short ({len(new_code)} chars vs {len(original)}) — likely truncated"
    try:
        ast.parse(new_code)
    except SyntaxError as e:
        return f"Syntax error: {e}"
    for elem in REQUIRED:
        if elem not in new_code:
            return f"Missing required element: {elem}"
    return None


def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("GROQ_API_KEY not set — skipping run")
        sys.exit(0)

    focus = os.environ.get("FOCUS", "")
    target_file, theme = pick_target(focus)
    current_code = Path(target_file).read_text()

    print(f"Target : {target_file}")
    print(f"Theme  : {theme}")

    client = Groq(api_key=api_key)

    system_prompt = f"""\
You are an expert Python/Streamlit developer making ONE focused improvement to a page of
the NiftyEdge Indian stock screener.

{APP_CONTEXT}

OUTPUT RULES — follow exactly:
1. Output ONLY raw Python — no prose, no markdown fences, no inline comments about your changes
2. Output the COMPLETE file from line 1 to the last line — never truncate or summarise
3. Make exactly ONE improvement matching the theme — do not refactor unrelated code
4. Preserve all imports, function names, and Streamlit page structure
5. The output must be runnable as `streamlit run <file>` with no modifications\
"""

    user_prompt = f"""\
Improve this Streamlit page with ONE focused change.

Theme: {theme}

Think about what a retail Indian investor would find most useful on this page.
Draw specific ideas from: Screener.in, Tickertape, TradingView, Zerodha Kite.

File to improve ({target_file}):
{current_code}

Output the complete improved file (raw Python only, no markdown):\
"""

    print("Calling Groq API…")
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=8192,
            temperature=0.3,
        )
    except Exception as e:
        print(f"Groq API error: {e} — skipping run")
        sys.exit(0)

    new_code = strip_fences(resp.choices[0].message.content)

    error = validate(new_code, current_code)
    if error:
        print(f"Validation failed: {error} — aborting")
        sys.exit(0)

    if new_code == current_code:
        print("No changes detected — nothing to commit")
        sys.exit(0)

    Path(target_file).write_text(new_code)

    fname      = Path(target_file).name
    short_desc = theme[:64].rstrip(",. ").lower()
    msg        = f"auto-improve: {short_desc} [{fname}]"
    Path("/tmp/improve_msg.txt").write_text(msg)

    print(f"Improvement applied to {target_file}")
    print(f"Commit message: {msg}")


if __name__ == "__main__":
    main()
