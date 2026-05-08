#!/usr/bin/env python3
"""
Fetches NSE Smart Money data and writes data/smart_money_cache.json.

Designed to run from GitHub Actions where NSE is reachable.
Streamlit Cloud reads the JSON file — never hits NSE directly.

Sources (tried in order):
  Bulk/Block deals : NSE archive CDN CSV → NSE interactive API
  FII/DII flow     : NSE archive dated CSVs → NSE API
  Insider trades   : BSE API (SAST) → NSE API
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "smart_money_cache.json")
DAYS_BACK  = 30

# ── HTTP helpers ───────────────────────────────────────────────────────────────

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

_nse_session: requests.Session | None = None


def _get_nse_session() -> requests.Session:
    global _nse_session
    if _nse_session is None:
        s = requests.Session()
        s.headers.update(_NSE_HEADERS)
        try:
            r = s.get("https://www.nseindia.com", timeout=15)
            r.raise_for_status()
            log.info("NSE session established (cookies: %s)", list(s.cookies.keys()))
            time.sleep(1.0)
        except Exception as exc:
            log.warning("NSE homepage warmup failed: %s", exc)
        _nse_session = s
    return _nse_session


def _nse_api(path: str, params: dict | None = None) -> dict | list | None:
    sess = _get_nse_session()
    url  = f"https://www.nseindia.com/api/{path}"
    try:
        r = sess.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("NSE API %s: %s", path, exc)
        return None


def _plain_get(url: str, timeout: int = 15) -> requests.Response | None:
    try:
        r = requests.get(url, headers=_NSE_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as exc:
        log.warning("GET %s: %s", url, exc)
        return None


def _date_str(d: date, fmt: str) -> str:
    return d.strftime(fmt)


def _trading_days(n: int) -> list[date]:
    days, d = [], date.today() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


# ── Bulk & Block deals ─────────────────────────────────────────────────────────

_DEAL_COLS = {
    "Symbol":                            "symbol",
    "SYMBOL":                            "symbol",
    "Security Name":                     "name",
    "SECURITY_NAME":                     "name",
    "Client Name":                       "entity",
    "CLIENT_NAME":                       "entity",
    "Buy / Sell":                        "type",
    "BUY_SELL":                          "type",
    "Buy/Sell":                          "type",
    "Quantity Traded":                   "shares",
    "QUANTITY_TRADED":                   "shares",
    "Trade Price / Wght. Avg. Price":    "price",
    "Wght. Avg. Price":                  "price",
    "TRADE_PRICE":                       "price",
    "Date":                              "date",
    "DATE":                              "date",
    # NSE API JSON keys
    "symbol":                            "symbol",
    "clientName":                        "entity",
    "dealType":                          "type",
    "quantity":                          "shares",
    "tradePrice":                        "price",
    "date":                              "date",
}


def _parse_deal_csv(text: str, label: str) -> list[dict]:
    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception as exc:
        log.warning("CSV parse (%s): %s", label, exc)
        return []
    df = df.rename(columns={k: v for k, v in _DEAL_COLS.items() if k in df.columns})
    df["category"] = label
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    if "shares" in df.columns and "price" in df.columns:
        df["value_cr"] = (
            pd.to_numeric(df["shares"], errors="coerce")
            * pd.to_numeric(df["price"],  errors="coerce")
            / 1e7
        ).round(2)
    cutoff = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    if "date" in df.columns:
        df = df[df["date"] >= cutoff]
    return df.where(pd.notna(df), None).to_dict("records")


def fetch_bulk_deals() -> list[dict]:
    log.info("Fetching bulk deals…")
    # 1. Archive CDN CSV (no auth needed)
    r = _plain_get("https://nsearchives.nseindia.com/content/equities/bulk.csv")
    if r and len(r.content) > 200:
        rows = _parse_deal_csv(r.text, "BULK")
        if rows:
            log.info("  bulk: %d rows from archive CSV", len(rows))
            return rows
    # 2. NSE interactive API
    data = _nse_api("bulk-deals", {
        "from": _date_str(date.today() - timedelta(days=DAYS_BACK), "%d-%m-%Y"),
        "to":   _date_str(date.today(), "%d-%m-%Y"),
    })
    if data:
        rows_raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows_raw, list) and rows_raw:
            df = pd.DataFrame(rows_raw)
            df = df.rename(columns={k: v for k, v in _DEAL_COLS.items() if k in df.columns})
            df["category"] = "BULK"
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
            if "shares" in df.columns and "price" in df.columns:
                df["value_cr"] = (
                    pd.to_numeric(df["shares"], errors="coerce")
                    * pd.to_numeric(df["price"], errors="coerce") / 1e7
                ).round(2)
            log.info("  bulk: %d rows from NSE API", len(df))
            return df.where(pd.notna(df), None).to_dict("records")
    log.warning("  bulk: no data from any source")
    return []


def fetch_block_deals() -> list[dict]:
    log.info("Fetching block deals…")
    r = _plain_get("https://nsearchives.nseindia.com/content/equities/block.csv")
    if r and len(r.content) > 200:
        rows = _parse_deal_csv(r.text, "BLOCK")
        if rows:
            log.info("  block: %d rows from archive CSV", len(rows))
            return rows
    data = _nse_api("block-deals", {
        "from": _date_str(date.today() - timedelta(days=DAYS_BACK), "%d-%m-%Y"),
        "to":   _date_str(date.today(), "%d-%m-%Y"),
    })
    if data:
        rows_raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows_raw, list) and rows_raw:
            df = pd.DataFrame(rows_raw)
            df = df.rename(columns={k: v for k, v in _DEAL_COLS.items() if k in df.columns})
            df["category"] = "BLOCK"
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
            if "shares" in df.columns and "price" in df.columns:
                df["value_cr"] = (
                    pd.to_numeric(df["shares"], errors="coerce")
                    * pd.to_numeric(df["price"], errors="coerce") / 1e7
                ).round(2)
            log.info("  block: %d rows from NSE API", len(df))
            return df.where(pd.notna(df), None).to_dict("records")
    log.warning("  block: no data from any source")
    return []


# ── FII / DII ──────────────────────────────────────────────────────────────────

_FII_COL_MAP = {
    "Category":            "category",
    "category":            "category",
    "dtype":               "category",
    "Segment":             "category",
    "Buy Value (₹ Cr)":   "buy_cr",
    "purchasedValueNSE":  "buy_cr",
    "Purchase (Net)":     "buy_cr",
    "Sell Value (₹ Cr)":  "sell_cr",
    "soldValueNSE":       "sell_cr",
    "Sale (Net)":         "sell_cr",
    "Net Value (₹ Cr)":  "net_cr",
    "netValueNSE":        "net_cr",
    "Net":                "net_cr",
}


def _parse_fii_df(df: pd.DataFrame, trade_date: date | None = None) -> list[dict]:
    df = df.rename(columns={k: v for k, v in _FII_COL_MAP.items() if k in df.columns})
    for c in ("buy_cr", "sell_cr", "net_cr"):
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce"
            )
    if "date" not in df.columns and trade_date:
        df["date"] = trade_date.isoformat()
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    return df.where(pd.notna(df), None).to_dict("records")


def fetch_fii_dii_flow() -> list[dict]:
    log.info("Fetching FII/DII flow…")
    rows: list[dict] = []

    # 1. Per-day archive CSV files
    for d in _trading_days(min(DAYS_BACK, 20)):
        url = f"https://nsearchives.nseindia.com/content/fii/fii{d.strftime('%d%m%Y')}.csv"
        r = _plain_get(url, timeout=10)
        if r and len(r.content) > 100:
            try:
                df = pd.read_csv(io.StringIO(r.text))
                rows.extend(_parse_fii_df(df, trade_date=d))
                log.info("  fii: %s ✓", d.isoformat())
            except Exception as exc:
                log.debug("  fii: %s parse error: %s", d.isoformat(), exc)

    if rows:
        log.info("  fii: %d rows total from archive", len(rows))
        return rows

    # 2. NSE API
    data = _nse_api("fiidiiTradeReact")
    if data:
        raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(raw, list) and raw:
            df = pd.DataFrame(raw)
            rows = _parse_fii_df(df)
            log.info("  fii: %d rows from NSE API", len(rows))
            return rows

    log.warning("  fii: no data from any source")
    return []


# ── Insider Trades ─────────────────────────────────────────────────────────────

_BSE_INSIDER_COLS = {
    "COMPANY_NAME":        "company",
    "SCRIP_CD":            "symbol",
    "SC_NAME":             "name",
    "PERSONNAME":          "person",
    "CATEGORYOFPERSON":    "category",
    "TYPEOFTRANSACTION":   "txn",
    "NOOFSECURITIES":      "shares",
    "VALUEOFSECURITIES":   "value",
    "ACQBEFOREMODE":       "before_pct",
    "ACQAFTERMODE":        "after_pct",
    "INTIMDATE":           "disclosed",
    "FROMDATE":            "from_date",
    "TODATE":              "to_date",
}

_NSE_INSIDER_COLS = {
    "acqName":           "person",
    "company":           "company",
    "symbol":            "symbol",
    "personCategory":    "category",
    "tdpTransactionType": "txn",
    "secAcq":            "shares",
    "secVal":            "value",
    "befAcqSharesPer":   "before_pct",
    "afterAcqSharesPer": "after_pct",
    "intimDt":           "disclosed",
    "acqfromDt":         "from_date",
    "acqtoDt":           "to_date",
}


def _normalise_insider(df: pd.DataFrame, col_map: dict) -> list[dict]:
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    if "value" in df.columns:
        df["value_cr"] = (pd.to_numeric(df["value"], errors="coerce") / 1e7).round(2)
    if "disclosed" in df.columns:
        df["disclosed"] = pd.to_datetime(df["disclosed"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    cutoff = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    if "disclosed" in df.columns:
        df = df[df["disclosed"] >= cutoff]
    return df.where(pd.notna(df), None).to_dict("records")


def fetch_insider_trades() -> list[dict]:
    log.info("Fetching insider trades…")
    today   = date.today()
    from_dt = (today - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    to_dt   = today.strftime("%Y-%m-%d")

    # 1. BSE SAST disclosures API
    url = "https://api.bseindia.com/BseIndiaAPI/api/SAST_Regs_Disclosures/w"
    r = _plain_get(f"{url}?pageno=1&strSearch=&DateFrom={from_dt}&DateTo={to_dt}&ScripCode=&Category=&Type=")
    if r:
        try:
            data = r.json()
            rows_raw = data.get("Table", data) if isinstance(data, dict) else data
            if isinstance(rows_raw, list) and rows_raw:
                df = pd.DataFrame(rows_raw)
                rows = _normalise_insider(df, _BSE_INSIDER_COLS)
                log.info("  insider: %d rows from BSE API", len(rows))
                return rows
        except Exception as exc:
            log.warning("  insider BSE parse: %s", exc)

    # 2. NSE API
    data = _nse_api("corporates-pit", {
        "symbol": "", "issuer": "",
        "from":   (today - timedelta(days=DAYS_BACK)).strftime("%d-%m-%Y"),
        "to":     today.strftime("%d-%m-%Y"),
        "type":   "",
    })
    if data:
        rows_raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows_raw, list) and rows_raw:
            df = pd.DataFrame(rows_raw)
            rows = _normalise_insider(df, _NSE_INSIDER_COLS)
            log.info("  insider: %d rows from NSE API", len(rows))
            return rows

    log.warning("  insider: no data from any source")
    return []


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    bulk   = fetch_bulk_deals()
    block  = fetch_block_deals()
    fii    = fetch_fii_dii_flow()
    inside = fetch_insider_trades()

    cache = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "bulk_block_deals": bulk + block,
        "fii_dii_flow":     fii,
        "insider_trades":   inside,
        "summary": {
            "bulk_count":    len(bulk),
            "block_count":   len(block),
            "fii_rows":      len(fii),
            "insider_count": len(inside),
        },
    }

    out = os.path.realpath(CACHE_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cache, f, indent=2, default=str)

    log.info(
        "Cache written → %s  (bulk=%d block=%d fii=%d insider=%d)",
        out, len(bulk), len(block), len(fii), len(inside),
    )


if __name__ == "__main__":
    main()
