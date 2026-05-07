"""
Smart Money data fetchers.

Sources:
  - NSE India unofficial API (session-based) for Bulk/Block Deals, FII/DII, Insider Trades
  - yfinance for institutional holders (shareholding snapshot)

NSE API requires cookie-based session authentication. On cloud deployments the
session may be refused due to IP restrictions; all functions return empty
DataFrames gracefully in that case.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_NSE_BASE = "https://www.nseindia.com"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

_session_lock = threading.Lock()
_nse_session: Optional[requests.Session] = None
_session_ts: float = 0
_SESSION_TTL = 300  # refresh session every 5 min


def _build_session() -> Optional[requests.Session]:
    s = requests.Session()
    s.headers.update(_HEADERS)
    try:
        r = s.get(_NSE_BASE, timeout=12)
        r.raise_for_status()
        time.sleep(0.3)
        return s
    except Exception as exc:
        logger.warning("NSE session init failed: %s", exc)
        return None


def _get_session() -> Optional[requests.Session]:
    global _nse_session, _session_ts
    with _session_lock:
        if _nse_session is None or time.time() - _session_ts > _SESSION_TTL:
            _nse_session = _build_session()
            _session_ts = time.time()
        return _nse_session


def _nse_get(path: str, params: dict | None = None) -> Optional[dict | list]:
    sess = _get_session()
    if sess is None:
        return None
    try:
        r = sess.get(f"{_NSE_BASE}/api/{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as exc:
        logger.warning("NSE API %s HTTP %s — invalidating session", path, exc.response.status_code)
        with _session_lock:
            global _nse_session
            _nse_session = None
        return None
    except Exception as exc:
        logger.warning("NSE API %s: %s", path, exc)
        return None


def _date_range(days: int) -> tuple[str, str]:
    """Return (from, to) strings in DD-MM-YYYY for NSE API params."""
    to_dt   = date.today()
    from_dt = to_dt - timedelta(days=days)
    return from_dt.strftime("%d-%m-%Y"), to_dt.strftime("%d-%m-%Y")


def _parse_date_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df


# ── Bulk Deals ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bulk_deals(days: int = 30) -> pd.DataFrame:
    from_s, to_s = _date_range(days)
    data = _nse_get("bulk-deals", {"from": from_s, "to": to_s})
    if not data:
        return pd.DataFrame()
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "symbol":      "Symbol",
        "scripCode":   "Code",
        "clientName":  "Entity",
        "dealType":    "Type",
        "quantity":    "Shares",
        "tradePrice":  "Price ₹",
        "mktType":     "Market",
        "date":        "Date",
    })
    df = _parse_date_col(df, "Date")
    if "Shares" in df.columns and "Price ₹" in df.columns:
        df["Value ₹ Cr"] = (
            pd.to_numeric(df["Shares"], errors="coerce")
            * pd.to_numeric(df["Price ₹"], errors="coerce")
            / 1e7
        ).round(2)
    df["Deal"] = "Bulk"
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


# ── Block Deals ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_block_deals(days: int = 30) -> pd.DataFrame:
    from_s, to_s = _date_range(days)
    data = _nse_get("block-deals", {"from": from_s, "to": to_s})
    if not data:
        return pd.DataFrame()
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "symbol":     "Symbol",
        "clientName": "Entity",
        "dealType":   "Type",
        "quantity":   "Shares",
        "tradePrice": "Price ₹",
        "date":       "Date",
    })
    df = _parse_date_col(df, "Date")
    if "Shares" in df.columns and "Price ₹" in df.columns:
        df["Value ₹ Cr"] = (
            pd.to_numeric(df["Shares"], errors="coerce")
            * pd.to_numeric(df["Price ₹"], errors="coerce")
            / 1e7
        ).round(2)
    df["Deal"] = "Block"
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


# ── FII / DII Daily Flow ───────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fii_dii_flow(days: int = 60) -> pd.DataFrame:
    """
    Returns a tidy DataFrame with columns:
      Date | Category (FII/DII) | Buy ₹Cr | Sell ₹Cr | Net ₹Cr
    """
    data = _nse_get("fiidiiTradeReact")
    if not data:
        return pd.DataFrame()
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "date":               "Date",
        "dtype":              "Category",
        "purchasedValueNSE":  "Buy ₹Cr",
        "soldValueNSE":       "Sell ₹Cr",
        "netValueNSE":        "Net ₹Cr",
    })
    # Also try alternate column names different NSE response versions use
    alt = {"purchasedValue": "Buy ₹Cr", "soldValue": "Sell ₹Cr", "netValue": "Net ₹Cr"}
    df = df.rename(columns={k: v for k, v in alt.items() if k in df.columns and v not in df.columns})

    df = _parse_date_col(df, "Date")
    for col in ("Buy ₹Cr", "Sell ₹Cr", "Net ₹Cr"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    if "Date" in df.columns:
        df = df[df["Date"] >= cutoff]

    return df.sort_values("Date", ascending=False).reset_index(drop=True)


# ── Insider / Promoter Trades (SEBI PIT disclosures) ──────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_insider_trades(days: int = 30) -> pd.DataFrame:
    from_s, to_s = _date_range(days)
    data = _nse_get("corporates-pit", {
        "symbol": "", "issuer": "", "from": from_s, "to": to_s, "type": "",
    })
    if not data:
        return pd.DataFrame()
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "company":           "Company",
        "symbol":            "Symbol",
        "acqName":           "Person",
        "personCategory":    "Category",
        "tdpTransactionType": "Txn",
        "secAcq":            "Shares",
        "secVal":            "Value ₹",
        "befAcqSharesPer":   "Before %",
        "afterAcqSharesPer": "After %",
        "acqMode":           "Mode",
        "acqfromDt":         "From",
        "acqtoDt":           "To",
        "intimDt":           "Disclosed",
    })
    if "Value ₹" in df.columns:
        df["Value ₹ Cr"] = (
            pd.to_numeric(df["Value ₹"], errors="coerce") / 1e7
        ).round(2)
    df = _parse_date_col(df, "Disclosed")
    return df.sort_values("Disclosed", ascending=False).reset_index(drop=True)


# ── Institutional Holders (yfinance) ──────────────────────────────────────────

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_institutional_holders(tickers: tuple[str, ...]) -> pd.DataFrame:
    """
    Fetch top institutional holders for each ticker via yfinance.
    Returns a combined DataFrame with a 'Ticker' column added.
    """
    frames = []
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
    # Normalize column names (yfinance column names have changed across versions)
    df = df.rename(columns={
        "Holder":        "Institution",
        "Shares":        "Shares",
        "Date Reported": "Date",
        "% Out":         "% Held",
        "Value":         "Value $",
    })
    return df
