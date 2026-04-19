"""
Persistent OHLCV price store backed by SQLite.

Stores daily candles as rows — not pickled blobs — so updates are
incremental: only the days missing from the DB are fetched from yfinance.

After the first bootstrap (~15s for 50 tickers), every subsequent load
is a pure SQLite read (~30ms) and every daily refresh only downloads the
last 10 days per ticker instead of 2 years.
"""
import sqlite3
import pandas as pd
import yfinance as yf
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB = "data_store/prices.db"
_BOOTSTRAP_PERIOD = "2y"
_INCREMENTAL_PERIOD = "10d"   # covers weekends + bank holidays gaps


# ── helpers ────────────────────────────────────────────────────────────────────

def _conn():
    Path("data_store").mkdir(exist_ok=True)
    c = sqlite3.connect(_DB, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
    return c


def _f(v):
    try:
        x = float(v)
        return None if x != x else x      # NaN → None
    except Exception:
        return None


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


# ── schema ─────────────────────────────────────────────────────────────────────

def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                ticker TEXT    NOT NULL,
                date   TEXT    NOT NULL,
                open   REAL,
                high   REAL,
                low    REAL,
                close  REAL,
                volume REAL,
                PRIMARY KEY (ticker, date)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_ticker_date ON ohlcv(ticker, date)")


_init()


# ── read / write ───────────────────────────────────────────────────────────────

def latest_date(ticker: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            "SELECT MAX(date) FROM ohlcv WHERE ticker = ?", (ticker,)
        ).fetchone()
    return row[0] if row and row[0] else None


def _store(ticker: str, df: pd.DataFrame):
    if df is None or df.empty:
        return
    rows = [
        (
            ticker,
            str(idx.date()) if hasattr(idx, "date") else str(idx)[:10],
            _f(row.get("Open")), _f(row.get("High")),
            _f(row.get("Low")),  _f(row.get("Close")),
            _f(row.get("Volume")),
        )
        for idx, row in df.iterrows()
    ]
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?)", rows
        )


def load(ticker: str, days: int = 504) -> Optional[pd.DataFrame]:
    """
    Return last `days` of daily OHLCV from the store.
    Pure SQLite read — no network call.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT date,open,high,low,close,volume FROM ohlcv "
            "WHERE ticker=? AND date>=? ORDER BY date",
            (ticker, cutoff),
        ).fetchall()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")
    return df if not df.empty else None


def ticker_count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv").fetchone()[0]


# ── refresh logic ──────────────────────────────────────────────────────────────

def _needs_refresh(ticker: str) -> bool:
    latest = latest_date(ticker)
    if latest is None:
        return True
    # Need refresh if we don't have at least yesterday's close
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return latest < yesterday


def refresh(tickers: list[str], force: bool = False) -> int:
    """
    Incrementally refresh prices for the given tickers.

    - Tickers with no data → full 2-year bootstrap via bulk yf.download
    - Tickers with stale data → fetch last 10 days only (covers gaps)
    - Tickers already up to date → skipped

    Returns total number of new rows written.
    """
    bootstrap, incremental = [], []

    for t in tickers:
        if force or not _needs_refresh.__wrapped__(t) if hasattr(_needs_refresh, '__wrapped__') else (force or latest_date(t) is None):
            bootstrap.append(t)
        elif _needs_refresh(t):
            incremental.append(t)

    # Re-check cleanly (avoid closure issues above)
    bootstrap, incremental = [], []
    for t in tickers:
        lt = latest_date(t)
        if force or lt is None:
            bootstrap.append(t)
        elif lt < (date.today() - timedelta(days=1)).isoformat():
            incremental.append(t)

    total_written = 0

    # ── Bootstrap new tickers ──────────────────────────────────────────────────
    if bootstrap:
        logger.info(f"price_store: bootstrapping {len(bootstrap)} tickers (2y)…")
        try:
            raw = yf.download(
                bootstrap, period=_BOOTSTRAP_PERIOD, interval="1d",
                group_by="ticker", auto_adjust=True, progress=False, threads=True,
            )
            for ticker in bootstrap:
                try:
                    df = _flatten(raw[ticker].copy() if len(bootstrap) > 1 else raw.copy())
                    df = df.dropna(how="all")
                    df.index = pd.to_datetime(df.index)
                    _store(ticker, df)
                    total_written += len(df)
                except Exception as e:
                    logger.warning(f"price_store bootstrap failed {ticker}: {e}")
        except Exception as e:
            logger.error(f"price_store bulk bootstrap error: {e}")

    # ── Incremental update ─────────────────────────────────────────────────────
    if incremental:
        logger.info(f"price_store: incrementally updating {len(incremental)} tickers (10d)…")
        try:
            raw = yf.download(
                incremental, period=_INCREMENTAL_PERIOD, interval="1d",
                group_by="ticker", auto_adjust=True, progress=False, threads=True,
            )
            for ticker in incremental:
                try:
                    df = _flatten(raw[ticker].copy() if len(incremental) > 1 else raw.copy())
                    df = df.dropna(how="all")
                    df.index = pd.to_datetime(df.index)
                    # Only write rows newer than what's stored
                    lt = latest_date(ticker)
                    if lt:
                        cutoff_dt = pd.Timestamp(lt) + pd.Timedelta(days=1)
                        df = df[df.index >= cutoff_dt]
                    _store(ticker, df)
                    total_written += len(df)
                except Exception as e:
                    logger.warning(f"price_store incremental failed {ticker}: {e}")
        except Exception as e:
            logger.error(f"price_store incremental update error: {e}")

    if total_written:
        logger.info(f"price_store: {total_written} new rows written.")
    return total_written


def warm(tickers: list[str]) -> int:
    """
    Pre-warm the price store for all given tickers.
    Called by the scheduler at 8:30 AM IST before market opens.
    """
    logger.info(f"price_store: warming {len(tickers)} tickers…")
    written = refresh(tickers)
    logger.info(f"price_store: warm-up complete — {written} new rows, "
                f"{ticker_count()} distinct tickers in store.")
    return written
