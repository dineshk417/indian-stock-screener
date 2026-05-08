"""
Smart Money data layer — reads from the daily JSON cache.

The cache is populated by scripts/fetch_smart_money.py, which runs from
GitHub Actions (unblocked IPs) every morning at 8:30 AM IST.

Streamlit Cloud never calls NSE directly.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent / "smart_money_cache.json"


# ── Cache reader ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def _load_cache() -> dict[str, Any]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH) as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("smart_money_cache.json read error: %s", exc)
        return {}


def cache_updated_at() -> datetime | None:
    data = _load_cache()
    ts = data.get("updated_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


# ── Public fetch functions ─────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_bulk_deals(days: int = 30) -> pd.DataFrame:
    data = _load_cache()
    rows = [r for r in data.get("bulk_block_deals", []) if r.get("category") == "BULK"]
    df = _to_df(rows, days, date_col="date")
    return _rename_deal_cols(df)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_block_deals(days: int = 30) -> pd.DataFrame:
    data = _load_cache()
    rows = [r for r in data.get("bulk_block_deals", []) if r.get("category") == "BLOCK"]
    df = _to_df(rows, days, date_col="date")
    return _rename_deal_cols(df)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_fii_dii_flow(days: int = 30) -> pd.DataFrame:
    data = _load_cache()
    rows = data.get("fii_dii_flow", [])
    df = _to_df(rows, days, date_col="date")
    if df.empty:
        return df
    df = df.rename(columns={
        "category":  "Category",
        "buy_cr":    "Buy ₹Cr",
        "sell_cr":   "Sell ₹Cr",
        "net_cr":    "Net ₹Cr",
        "date":      "Date",
        # fallback: raw NSE column names stored before normalisation
        "buyValue":  "Buy ₹Cr",
        "sellValue": "Sell ₹Cr",
        "netValue":  "Net ₹Cr",
    })
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_insider_trades(days: int = 30) -> pd.DataFrame:
    data = _load_cache()
    rows = data.get("insider_trades", [])
    df = _to_df(rows, days, date_col="disclosed")
    if df.empty:
        return df
    df = df.rename(columns={
        "company":    "Company",
        "symbol":     "Symbol",
        "person":     "Person",
        "category":   "Category",
        "txn":        "Txn",
        "shares":     "Shares",
        "value_cr":   "Value ₹ Cr",
        "before_pct": "Before %",
        "after_pct":  "After %",
        "disclosed":  "Disclosed",
        "from_date":  "From",
        "to_date":    "To",
    })
    return df


# ── Institutional Holders (yfinance — always live, already works) ──────────────

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_institutional_holders(tickers: tuple[str, ...]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        try:
            holders = yf.Ticker(ticker).institutional_holders
            if holders is not None and not holders.empty:
                h = holders.copy()
                h["Ticker"] = ticker.replace(".NS", "")
                frames.append(h)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.rename(columns={
        "Holder":        "Institution",
        "Date Reported": "Date",
        "% Out":         "% Held",
        "Value":         "Value $",
    })


# ── Internal ───────────────────────────────────────────────────────────────────

def _to_df(rows: list[dict], days: int, date_col: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df[date_col] >= cutoff]
    return df.reset_index(drop=True)


def _rename_deal_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.rename(columns={
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
    # Normalise deal type to Title Case so the style check (v == "Block") works
    if "Deal" in df.columns:
        df["Deal"] = df["Deal"].str.title()
    return df
