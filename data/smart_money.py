"""
Smart Money data fetchers — archive/CDN-first approach.

NSE's interactive JSON API requires session cookies and is blocked on cloud IPs.
These fetchers bypass that entirely by using:
  - NSE Archives (nsearchives.nseindia.com) — static CDN files, no auth
  - BSE India API (api.bseindia.com) — stateless, no cookie requirement
  - SEBI statistics page — HTML tables parseable with pd.read_html()
  - yfinance — institutional holders per ticker

All functions return an empty DataFrame (never raise) so the UI
can show a graceful message when a source is temporarily down.
"""
from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Utility ────────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 15, params: dict | None = None) -> Optional[requests.Response]:
    """Plain stateless GET — no session, no cookies."""
    try:
        r = requests.get(url, headers=_HEADERS, params=params, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as exc:
        logger.warning("GET %s → %s", url, exc)
        return None


def _read_csv(r: requests.Response) -> pd.DataFrame:
    try:
        return pd.read_csv(io.StringIO(r.text))
    except Exception as exc:
        logger.warning("CSV parse error: %s", exc)
        return pd.DataFrame()


def _coerce_date(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    return df


def _filter_days(df: pd.DataFrame, col: str, days: int) -> pd.DataFrame:
    if col in df.columns:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df[col] >= cutoff]
    return df


def _value_cr(df: pd.DataFrame, shares_col: str, price_col: str) -> pd.DataFrame:
    if shares_col in df.columns and price_col in df.columns:
        df["Value ₹ Cr"] = (
            pd.to_numeric(df[shares_col], errors="coerce")
            * pd.to_numeric(df[price_col], errors="coerce")
            / 1e7
        ).round(2)
    return df


def _trading_days_back(n: int) -> list[date]:
    """Return last n calendar dates that are Mon-Fri."""
    days, d = [], date.today()
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


# ── Bulk Deals ─────────────────────────────────────────────────────────────────
# Source: NSE Archive static CSV — no session/cookies needed.

_BULK_URL  = "https://nsearchives.nseindia.com/content/equities/bulk.csv"
_BLOCK_URL = "https://nsearchives.nseindia.com/content/equities/block.csv"

_DEAL_COL_MAP = {
    # Common NSE CSV header variants
    "Symbol":                            "Symbol",
    "SYMBOL":                            "Symbol",
    "Security Name":                     "Name",
    "SECURITY_NAME":                     "Name",
    "Client Name":                       "Entity",
    "CLIENT_NAME":                       "Entity",
    "Buy / Sell":                        "Type",
    "BUY_SELL":                          "Type",
    "Buy/Sell":                          "Type",
    "Quantity Traded":                   "Shares",
    "QUANTITY_TRADED":                   "Shares",
    "Trade Price / Wght. Avg. Price":    "Price ₹",
    "Wght. Avg. Price":                  "Price ₹",
    "TRADE_PRICE":                       "Price ₹",
    "Date":                              "Date",
    "DATE":                              "Date",
}


def _parse_deal_csv(r: requests.Response, label: str) -> pd.DataFrame:
    df = _read_csv(r)
    if df.empty:
        return df
    df = df.rename(columns={k: v for k, v in _DEAL_COL_MAP.items() if k in df.columns})
    df = _coerce_date(df, "Date")
    df = _value_cr(df, "Shares", "Price ₹")
    df["Deal"] = label
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_bulk_deals(days: int = 30) -> pd.DataFrame:
    r = _get(_BULK_URL)
    if r is None:
        return pd.DataFrame()
    df = _parse_deal_csv(r, "Bulk")
    df = _filter_days(df, "Date", days)
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_block_deals(days: int = 30) -> pd.DataFrame:
    r = _get(_BLOCK_URL)
    if r is None:
        return pd.DataFrame()
    df = _parse_deal_csv(r, "Block")
    df = _filter_days(df, "Date", days)
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


# ── FII / DII Daily Flow ───────────────────────────────────────────────────────
# Primary: NSE archive dated CSV files (one file per trading day).
# Fallback: SEBI FPI statistics page (pd.read_html).

_NSE_FII_URL = "https://nsearchives.nseindia.com/content/fii/fii{date}.csv"

_FII_COL_MAP = {
    "Category":              "Category",
    "category":              "Category",
    "Segment":               "Category",
    "Buy Value (₹ Cr)":     "Buy ₹Cr",
    "Purchase (Net)":        "Buy ₹Cr",
    "BUY":                   "Buy ₹Cr",
    "Sell Value (₹ Cr)":    "Sell ₹Cr",
    "Sale (Net)":            "Sell ₹Cr",
    "SELL":                  "Sell ₹Cr",
    "Net Value (₹ Cr)":     "Net ₹Cr",
    "Net":                   "Net ₹Cr",
    "NET":                   "Net ₹Cr",
}


def _normalise_fii(df: pd.DataFrame, trade_date: date | None = None) -> pd.DataFrame:
    df = df.rename(columns={k: v for k, v in _FII_COL_MAP.items() if k in df.columns})
    for col in ("Buy ₹Cr", "Sell ₹Cr", "Net ₹Cr"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    if trade_date and "Date" not in df.columns:
        df["Date"] = pd.Timestamp(trade_date)
    elif "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fii_dii_flow(days: int = 30) -> pd.DataFrame:
    """
    Returns daily FII/DII net flow.

    Probes NSE archive CSV per trading day (format: fiiDDMMYYYY.csv).
    Falls back to SEBI FPI statistics HTML table when no archive files found.
    Caps probing at 30 trading days to stay fast.
    """
    frames: list[pd.DataFrame] = []
    probe_days = _trading_days_back(min(days, 30))

    for d in probe_days:
        url = _NSE_FII_URL.format(date=d.strftime("%d%m%Y"))
        r = _get(url, timeout=8)
        if r is None or len(r.content) < 50:
            continue
        df = _read_csv(r)
        if df.empty:
            continue
        df = _normalise_fii(df, trade_date=d)
        frames.append(df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        if "Date" in combined.columns:
            combined = combined.sort_values("Date", ascending=False).reset_index(drop=True)
        return combined

    # Fallback: SEBI FPI statistics page
    return _sebi_fpi_fallback()


def _sebi_fpi_fallback() -> pd.DataFrame:
    """Parse the SEBI FPI statistics HTML page with pd.read_html."""
    try:
        tables = pd.read_html(
            "https://www.sebi.gov.in/statistics/fpi-investment/latest.html",
            flavor="html.parser",
        )
        for t in tables:
            if len(t.columns) >= 3 and len(t) >= 2:
                t = _normalise_fii(t)
                t["Source"] = "SEBI"
                return t
    except Exception as exc:
        logger.warning("SEBI FPI fallback: %s", exc)
    return pd.DataFrame()


# ── Insider / Promoter Trades (SEBI PIT) ──────────────────────────────────────
# Source: BSE India API — stateless, no cookie enforcement from cloud IPs.

_BSE_SAST_URL = "https://api.bseindia.com/BseIndiaAPI/api/SAST_Regs_Disclosures/w"

_BSE_COL_MAP = {
    "COMPANY_NAME":        "Company",
    "SCRIP_CD":            "Symbol",
    "SC_NAME":             "Name",
    "PERSONNAME":          "Person",
    "CATEGORYOFPERSON":    "Category",
    "TYPEOFTRANSACTION":   "Txn",
    "NOOFSECURITIES":      "Shares",
    "VALUEOFSECURITIES":   "Value ₹",
    "ACQBEFOREMODE":       "Before %",
    "ACQAFTERMODE":        "After %",
    "ACQAFTERNEWMODE":     "After %",
    "INTIMDATE":           "Disclosed",
    "FROMDATE":            "From",
    "TODATE":              "To",
    "MODE_OF_ACQ":         "Mode",
    "TYPEOFSECURITY":      "Security",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_insider_trades(days: int = 30) -> pd.DataFrame:
    """
    Fetches SEBI PIT/SAST insider disclosures from BSE India API.
    BSE's API is stateless and accessible from cloud IPs without session cookies.
    """
    today   = date.today()
    from_dt = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    to_dt   = today.strftime("%Y-%m-%d")

    r = _get(_BSE_SAST_URL, params={
        "pageno":   "1",
        "strSearch": "",
        "DateFrom": from_dt,
        "DateTo":   to_dt,
        "ScripCode": "",
        "Category": "",
        "Type":     "",
    })
    if r is None:
        return pd.DataFrame()

    try:
        data = r.json()
    except Exception as exc:
        logger.warning("BSE insider JSON parse: %s", exc)
        return pd.DataFrame()

    rows = data.get("Table", data) if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.rename(columns={k: v for k, v in _BSE_COL_MAP.items() if k in df.columns})

    if "Value ₹" in df.columns:
        df["Value ₹ Cr"] = (
            pd.to_numeric(df["Value ₹"], errors="coerce") / 1e7
        ).round(2)

    df = _coerce_date(df, "Disclosed")
    return df.sort_values("Disclosed", ascending=False).reset_index(drop=True)


# ── Institutional Holders (yfinance) ──────────────────────────────────────────

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
        "Shares":        "Shares",
        "Date Reported": "Date",
        "% Out":         "% Held",
        "Value":         "Value $",
    })
