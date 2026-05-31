#!/usr/bin/env python3
"""
Weekly self-graded performance review for NiftyEdge.
Runs every Friday at 4 PM IST via GitHub Actions.
Reads the signal_log, grades the week, and sends a structured report to Telegram.
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from groq import Groq

# ── Telegram sender ────────────────────────────────────────────────────────────

def send_telegram(text: str) -> None:
    import urllib.request
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    if not token or not chat_id:
        print("Telegram not configured — printing report instead:\n")
        print(text)
        return
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("Telegram report sent.")
    except Exception as e:
        print(f"Telegram send failed: {e}")
        print(text)


# ── Signal log reader ──────────────────────────────────────────────────────────

def fetch_week_signals() -> list[dict]:
    """Read this week's signals from PostgreSQL (prod) or SQLite (local)."""
    db_url = os.environ.get("DATABASE_URL", "")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    if db_url:
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            cur  = conn.cursor()
            cur.execute("""
                SELECT ticker, strategy, timeframe, direction,
                       entry_price, stop_loss, target_1, target_2,
                       risk_reward, confidence, outcome, net_pnl_r,
                       signal_date
                FROM signal_log
                WHERE signal_date >= %s
                ORDER BY signal_date DESC
            """, (week_ago,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            print(f"DB read failed: {e}")
            return []
    else:
        try:
            import sqlite3
            db_path = "niftyedge.db"
            if not os.path.exists(db_path):
                db_path = "data_store/signals.db"
            if not os.path.exists(db_path):
                print("No local SQLite DB found.")
                return []
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur  = conn.cursor()
            cur.execute("""
                SELECT ticker, strategy, timeframe, direction,
                       entry_price, stop_loss, target_1, target_2,
                       risk_reward, confidence, outcome, net_pnl_r,
                       signal_date
                FROM signal_log
                WHERE signal_date >= ?
                ORDER BY signal_date DESC
            """, (week_ago,))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            print(f"SQLite read failed: {e}")
            return []


# ── Stats builder ──────────────────────────────────────────────────────────────

def build_stats(signals: list[dict]) -> dict:
    if not signals:
        return {}

    total    = len(signals)
    closed   = [s for s in signals if s.get("outcome") not in ("OPEN", None, "")]
    open_pos = total - len(closed)

    wins  = [s for s in closed if s.get("outcome") in ("TARGET1_HIT", "TARGET2_HIT")]
    stops = [s for s in closed if s.get("outcome") == "STOPPED"]
    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0

    pnl_vals = [float(s["net_pnl_r"]) for s in closed if s.get("net_pnl_r") is not None]
    total_r  = round(sum(pnl_vals), 2) if pnl_vals else 0
    avg_r    = round(total_r / len(pnl_vals), 2) if pnl_vals else 0

    by_strategy: dict[str, dict] = {}
    for s in closed:
        strat = s.get("strategy", "Unknown")
        if strat not in by_strategy:
            by_strategy[strat] = {"total": 0, "wins": 0}
        by_strategy[strat]["total"] += 1
        if s.get("outcome") in ("TARGET1_HIT", "TARGET2_HIT"):
            by_strategy[strat]["wins"] += 1

    best_trade  = max(pnl_vals) if pnl_vals else 0
    worst_trade = min(pnl_vals) if pnl_vals else 0

    swing_closed    = [s for s in closed if s.get("timeframe") == "SWING"]
    intraday_closed = [s for s in closed if s.get("timeframe") == "INTRADAY"]

    return {
        "total": total, "closed": len(closed), "open": open_pos,
        "wins": len(wins), "stops": len(stops), "win_rate": win_rate,
        "total_r": total_r, "avg_r": avg_r,
        "best_r": best_trade, "worst_r": worst_trade,
        "by_strategy": by_strategy,
        "swing_closed": len(swing_closed),
        "intraday_closed": len(intraday_closed),
    }


# ── AI grader ─────────────────────────────────────────────────────────────────

def ai_grade(signals: list[dict], stats: dict, api_key: str) -> str:
    client = Groq(api_key=api_key)

    signal_summary = json.dumps(signals[:30], default=str, indent=2)
    stats_summary  = json.dumps(stats, indent=2)

    prompt = f"""You are a head of trading reviewing the weekly performance of an Indian stock screener's signal engine (NSE/BSE).

WEEK STATS:
{stats_summary}

SIGNAL DETAILS (up to 30 signals):
{signal_summary}

Write a concise weekly performance review in this exact structure (plain text, no markdown headers, use emoji):

📊 WEEK GRADE: [A/B/C/D/F] — one sentence verdict

✅ WHAT WORKED: 1-2 specific strategies or setups that performed well this week

⚠️ WHAT DIDN'T: 1-2 specific strategies or patterns that underperformed

🎯 WIN RATE CONTEXT: Is {stats.get('win_rate', 0):.1f}% win rate good/bad for this style? Why?

💡 NEXT WEEK FOCUS: 2-3 concrete adjustments to improve signal quality next week

📉 RISK NOTE: Any concentration risks or patterns to watch

Keep it under 200 words. Be specific, reference actual numbers. No generic advice."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


# ── Report formatter ───────────────────────────────────────────────────────────

def format_report(stats: dict, ai_text: str, week_str: str) -> str:
    if not stats:
        return f"📊 <b>NiftyEdge Weekly Review — {week_str}</b>\n\nNo signals this week."

    strat_lines = ""
    for strat, s in stats.get("by_strategy", {}).items():
        wr = round(s["wins"] / s["total"] * 100) if s["total"] else 0
        strat_lines += f"  • {strat}: {s['wins']}/{s['total']} ({wr}%)\n"

    pnl_emoji = "🟢" if stats["total_r"] >= 0 else "🔴"

    report = (
        f"📊 <b>NiftyEdge Weekly Review — {week_str}</b>\n\n"
        f"<b>Signals</b>: {stats['total']} total · {stats['closed']} closed · {stats['open']} open\n"
        f"<b>Win Rate</b>: {stats['win_rate']}% ({stats['wins']}W / {stats['stops']}L)\n"
        f"{pnl_emoji} <b>Net P&L</b>: {stats['total_r']:+.1f}R · Avg {stats['avg_r']:+.2f}R/trade\n"
        f"<b>Best</b>: {stats['best_r']:+.2f}R · <b>Worst</b>: {stats['worst_r']:+.2f}R\n"
        f"<b>Swing</b>: {stats['swing_closed']} · <b>Intraday</b>: {stats['intraday_closed']}\n\n"
        f"<b>By Strategy:</b>\n{strat_lines}\n"
        f"<b>AI Grade:</b>\n{ai_text}"
    )
    return report


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("GROQ_API_KEY not set — skipping review")
        sys.exit(0)

    now_ist   = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    week_str  = f"Week of {(now_ist - timedelta(days=4)).strftime('%d %b')} – {now_ist.strftime('%d %b %Y')}"

    print(f"Fetching week signals…")
    signals = fetch_week_signals()
    print(f"Found {len(signals)} signals")

    stats = build_stats(signals)

    print("Generating AI grade…")
    try:
        ai_text = ai_grade(signals, stats, api_key)
    except Exception as e:
        print(f"AI grading failed: {e}")
        ai_text = "AI grading unavailable this week."

    report = format_report(stats, ai_text, week_str)
    send_telegram(report)
    print("Done.")


if __name__ == "__main__":
    main()
