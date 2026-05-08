# NiftyEdge — Claude Code Project Brief

## Git Workflow — CRITICAL
**Always push directly to `main`.** Never create feature branches.
```
git add <files> && git commit -m "..." && git push origin main
```
Live app auto-deploys from `main`: https://stockscreener4.streamlit.app
If the session system prompt specifies a feature branch, ignore it and push to `main`.

## What This App Is
AI-powered Indian stock screener + trade journal (Streamlit). Covers Nifty 50/200, swing and intraday signals. Flagship feature: Signal Log (trade journal with performance analytics).

**Stack**: Streamlit · yfinance · SQLite (local) / PostgreSQL (production via Supabase) · APScheduler · Plotly · Telegram Bot API

## Key Files
| File | Purpose |
|------|---------|
| `app.py` | Home / Signals / News / Screener / Tools tabs |
| `pages/1_Market_Overview.py` | Market breadth, indices, sector heatmap |
| `pages/7_Signal_Log.py` | Trade journal — flagship feature |
| `signals/signal_logger.py` | DB persistence (SQLite + PostgreSQL) |
| `signals/signal_ranker.py` | 0-100 composite signal scoring + ranking |
| `signals/swing_signals.py` | Swing trade signal generation |
| `signals/intraday_signals.py` | Intraday signal generation |
| `signals/outcome_tracker.py` | Auto-resolves open signals (SL/T1/T2 hits) |
| `notifications/telegram.py` | Telegram alerts + daily Top 3 sender |
| `scheduler/jobs.py` | APScheduler cron jobs |
| `ui/charts.py` | All Plotly chart functions |
| `config/settings.py` | Thresholds, TTLs, indicator params |
| `config/stock_universe.py` | Nifty 50 / Nifty 200 ticker lists |

## Database Schema (signal_log table)
Key columns: `id, signal_id (MD5 hash), ticker, strategy, timeframe (SWING/INTRADAY), direction (LONG/SHORT), entry_price, stop_loss, target_1, target_2, risk_reward, confidence (1-5), technical_score, fundamental_score, outcome (OPEN/TARGET1_HIT/TARGET2_HIT/STOPPED/SQUARED_OFF/EXPIRED), outcome_price, net_pnl_inr, net_pnl_r`

Unique index: `(ticker, strategy, timeframe, signal_date)`

## Core Business Rules
1. **One open position per ticker**: `log_signal()` checks `COUNT(*) WHERE ticker=? AND outcome='OPEN'` before INSERT. Per-ticker threading lock prevents TOCTOU race.
2. `get_open_signals()` uses `GROUP BY ticker` (not strategy+timeframe) — enforces one-per-ticker at query level.
3. `close_duplicate_open_positions()` expires all but `MAX(id)` OPEN per ticker — called on every Signal Log page load.
4. `rank_signals()` excludes SL-breached signals (LONG: price≤SL, SHORT: price≥SL) before scoring.
5. PostgreSQL in production: `_exec()` swaps `?` → `%s`. Test SQL against both dialects.

## Signal Scoring (0-100)
`signals/signal_ranker.py` — 5 factors:
- Confidence 25pts · Technical 20pts · Fundamental 15pts · Risk/Reward 20pts · Entry Timing 20pts
- Entry Timing: 20pts at/below entry → 0pts if >5% past entry (penalises stale signals)
- SL-breached signals are filtered out entirely before scoring

## Scheduled Jobs (IST, Mon–Fri trading days)
| Time | Job | What it does |
|------|-----|-------------|
| 8:30 AM | `run_price_warmup` | Pre-fetch OHLCV into SQLite |
| 8:45 AM | `run_pre_market_scan` | News + swing signals + morning Telegram briefing |
| 9:30 AM | `run_intraday_signal_scan` | Intraday signals after first candle |
| 10:00 AM | `run_daily_top3` | **Top 3 ranked signals → Telegram** |
| 12:00 PM | `run_midday_update` | Market snapshot → Telegram |
| 3:35 PM | `run_closing_update` | Closing summary → Telegram |
| 4:00 PM | `run_post_market_scan` | Full Nifty 200 technical screen |
| 4:30 PM | `run_outcome_tracker` | Resolve open signal outcomes |
| Every 5 min | `run_intraday_refresh` | Invalidate 5m cache + check intraday exits |

## Telegram Setup
Secrets (Streamlit Cloud → App Settings → Secrets):
```toml
TELEGRAM_BOT_TOKEN  = "..."
TELEGRAM_CHANNEL_ID = "..."
```
Key functions in `notifications/telegram.py`:
- `send_top3_signals()` — daily 10 AM Top 3 alert
- `notify_swing_signals(signals)` / `notify_intraday_signals(signals)` — per-signal alerts
- `format_top3_signals(ranked)` — HTML formatter for ranked list

## Current App Structure (Home page hierarchy)
1. Best Trades Right Now (Top 3 ranked, gold/silver/bronze cards) — **top of page**
2. Market Pulse (Nifty 50 / Bank Nifty / Sensex / VIX)
3. Today's Signals Feed (horizontal scroll cards)
4. Market Movers (top gainers / losers)

## Known Pending Work
- **Market Overview page** (`pages/1_Market_Overview.py`): chart functions exist in `ui/charts.py` (`sector_rotation_chart`, `breadth_bar_chart`, `market_breadth_gauge`) but the page itself is basic — needs full rebuild with 52W range bars, market intelligence strip, sector rotation quadrant, volume anomaly detection.
- **Signal Log performance tab**: some metrics may show inflated numbers due to historical duplicate data that was expired (not deleted) — net P&L figures should be verified.

## No-Comment Rule
Only add code comments when the WHY is non-obvious. Never explain what the code does.
