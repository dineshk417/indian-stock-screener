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


def _nse_warm(page_path: str) -> None:
    """Visit a specific NSE page so its endpoint-specific cookies are set."""
    sess = _get_nse_session()
    try:
        sess.get(f"https://www.nseindia.com/{page_path}", timeout=12)
        time.sleep(0.8)
    except Exception as exc:
        log.debug("NSE warm %s: %s", page_path, exc)


def _nse_api(path: str, params: dict | None = None, warm: str | None = None) -> dict | list | None:
    if warm:
        _nse_warm(warm)
    sess = _get_nse_session()
    url  = f"https://www.nseindia.com/api/{path}"
    try:
        r = sess.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("NSE API %s: %s", path, exc)
        return None


_BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin":          "https://www.bseindia.com",
    "Referer":         "https://www.bseindia.com/",
}


def _plain_get(url: str, timeout: int = 15) -> requests.Response | None:
    try:
        r = requests.get(url, headers=_NSE_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as exc:
        log.warning("GET %s: %s", url, exc)
        return None


def _bse_get(url: str, timeout: int = 15) -> requests.Response | None:
    try:
        r = requests.get(url, headers=_BSE_HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as exc:
        log.warning("BSE GET %s: %s", url, exc)
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
    # NSE fiidiiTradeReact — observed column variants
    "buyValue":            "buy_cr",
    "sellValue":           "sell_cr",
    "netValue":            "net_cr",
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

    # 1. NSE API — warm with the FII/DII reports page first (sets endpoint cookies)
    data = _nse_api("fiidiiTradeReact", warm="reports/fii-dii")
    if data:
        raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(raw, list) and raw:
            df = pd.DataFrame(raw)
            rows = _parse_fii_df(df)
            if rows:
                log.info("  fii: %d rows from NSE API", len(rows))
                return rows

    # 2. SEBI FPI statistics HTML page (pd.read_html — needs lxml)
    try:
        tables = pd.read_html(
            "https://www.sebi.gov.in/statistics/fpi-investment/latest.html",
            flavor="lxml",
        )
        for t in tables:
            # Look for a table that has numeric-ish buy/sell/net columns
            cols_lower = [str(c).lower() for c in t.columns]
            if any("buy" in c or "purchas" in c or "net" in c for c in cols_lower) and len(t) >= 2:
                t.columns = [str(c) for c in t.columns]
                rows = _parse_fii_df(t)
                if rows:
                    log.info("  fii: %d rows from SEBI page", len(rows))
                    return rows
    except Exception as exc:
        log.warning("  fii SEBI fallback: %s", exc)

    # 3. NSE FII/DII archive CSV (some dates exist at a different path)
    for d in _trading_days(min(DAYS_BACK, 10)):
        for url_pat in [
            f"https://nsearchives.nseindia.com/content/fii/fii{d.strftime('%d%m%Y')}.csv",
            f"https://archives.nseindia.com/content/fii/fii{d.strftime('%d%m%Y')}.xls",
        ]:
            r = _plain_get(url_pat, timeout=8)
            if r and len(r.content) > 100:
                try:
                    df = pd.read_csv(io.StringIO(r.text)) if url_pat.endswith(".csv") else pd.read_excel(io.BytesIO(r.content))
                    rows = _parse_fii_df(df, trade_date=d)
                    if rows:
                        log.info("  fii: %d rows from archive %s", len(rows), d.isoformat())
                        return rows
                except Exception:
                    pass

    log.warning("  fii: no data from any source")
    return []


# ── Insider Trades ─────────────────────────────────────────────────────────────

_BSE_INSIDER_COLS = {
    # SAST (Reg 29) column names
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
    # BSE PIT insider trading column name variants
    "ScripName":           "company",
    "ScripCode":           "symbol",
    "PersonName":          "person",
    "Category":            "category",
    "TransType":           "txn",
    "NoOfSecurities":      "shares",
    "ValueOfSecurities":   "value",
    "AcqBeforeMode":       "before_pct",
    "AcqAfterMode":        "after_pct",
    "IntimDate":           "disclosed",
    "FromDate":            "from_date",
    "ToDate":              "to_date",
    # Additional lowercase variants
    "companyname":         "company",
    "scripcode":           "symbol",
    "personname":          "person",
    "categoryofperson":    "category",
    "typeoftransaction":   "txn",
    "noofsecurities":      "shares",
    "valueofsecurities":   "value",
    "intimdate":           "disclosed",
    "fromdate":            "from_date",
    "todate":              "to_date",
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


def _try_bse_insider(endpoint: str, from_dt: date, to_dt: date) -> list[dict]:
    """Try one BSE API endpoint for insider/SAST data. Returns rows or []."""
    base = f"https://api.bseindia.com/BseIndiaAPI/api/{endpoint}/w"
    for date_fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        from_bse = from_dt.strftime(date_fmt)
        to_bse   = to_dt.strftime(date_fmt)
        url = f"{base}?pageno=1&strSearch=&DateFrom={from_bse}&DateTo={to_bse}&ScripCode=&Category=&Type="
        r = _bse_get(url)
        if not r:
            log.info("  insider BSE %s (%s): no response (HTTP error or timeout)", endpoint, date_fmt)
            continue
        try:
            j = r.json()
            log.info("  insider BSE %s (%s): status=%s keys=%s",
                     endpoint, date_fmt, r.status_code,
                     list(j.keys()) if isinstance(j, dict) else type(j).__name__)
            rows_raw = (
                j.get("Table", j.get("Table1", j.get("data", j)))
                if isinstance(j, dict) else j
            )
            if isinstance(rows_raw, list) and rows_raw:
                log.info("  insider BSE %s: %d rows, sample keys=%s",
                         endpoint, len(rows_raw), list(rows_raw[0].keys())[:12])
                df = pd.DataFrame(rows_raw)
                rows = _normalise_insider(df, _BSE_INSIDER_COLS)
                if rows:
                    log.info("  insider: %d rows from BSE %s", len(rows), endpoint)
                    return rows
                log.info("  insider BSE %s: normalise returned 0 rows", endpoint)
            else:
                log.info("  insider BSE %s (%s): rows_raw empty/wrong type: %s",
                         endpoint, date_fmt, repr(rows_raw)[:120])
            break  # got a JSON response — don't retry other date formats
        except Exception as exc:
            log.debug("  insider BSE %s (%s): %s", endpoint, date_fmt, exc)
    return []


def fetch_insider_trades() -> list[dict]:
    log.info("Fetching insider trades…")
    today   = date.today()
    from_dt = today - timedelta(days=DAYS_BACK)
    from_nse = from_dt.strftime("%d-%m-%Y")
    to_nse   = today.strftime("%d-%m-%Y")

    # 1. NSE PIT API (Prohibition of Insider Trading disclosures)
    _nse_warm("companies-listing/corporate-filings-insider-trading")
    time.sleep(1.5)   # give cookies more time to settle
    data = _nse_api("corporates-pit",
                    params={"symbol": "", "issuer": "", "from": from_nse, "to": to_nse, "type": ""})
    if data is not None:
        log.info("  insider NSE response type=%s keys=%s",
                 type(data).__name__,
                 list(data.keys()) if isinstance(data, dict) else "—")
        rows_raw = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(rows_raw, list) and rows_raw:
            log.info("  insider NSE: %d rows, sample keys=%s",
                     len(rows_raw), list(rows_raw[0].keys())[:12])
            df = pd.DataFrame(rows_raw)
            rows = _normalise_insider(df, _NSE_INSIDER_COLS)
            if rows:
                log.info("  insider: %d rows from NSE API", len(rows))
                return rows
        else:
            log.warning("  insider NSE: rows_raw=%s", repr(rows_raw)[:200])
    else:
        log.warning("  insider NSE: API returned None (blocked or timeout)")

    # 2. BSE PIT insider trading (SEBI PIT Regulations — the actual insider trades)
    for endpoint in ("InsiderTrading", "Insider_Trading"):
        rows = _try_bse_insider(endpoint, from_dt, today)
        if rows:
            return rows

    # 3. BSE SAST (Substantial Acquisition disclosures — related but not insider trades)
    rows = _try_bse_insider("SAST_Regs_Disclosures", from_dt, today)
    if rows:
        return rows

    # 4. NSE archive CSV (no cookies needed — static file)
    for csv_url in [
        "https://nsearchives.nseindia.com/corporates/insiderTrading.csv",
        "https://nsearchives.nseindia.com/corporates/pit/pitDisclosures.csv",
    ]:
        r = _plain_get(csv_url, timeout=12)
        if r and len(r.content) > 200:
            try:
                df = pd.read_csv(io.StringIO(r.text))
                log.info("  insider archive CSV cols: %s", list(df.columns)[:12])
                rows = _normalise_insider(df, _NSE_INSIDER_COLS)
                if rows:
                    log.info("  insider: %d rows from NSE archive %s", len(rows), csv_url)
                    return rows
            except Exception as exc:
                log.debug("  insider archive CSV %s: %s", csv_url, exc)

    log.warning("  insider: no data from any source")
    return []


# ── Cache merge helpers ────────────────────────────────────────────────────────

def _load_existing() -> dict:
    out = os.path.realpath(CACHE_PATH)
    if not os.path.exists(out):
        return {}
    try:
        with open(out) as f:
            return json.load(f)
    except Exception:
        return {}


def _merge_fii(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """
    Accumulate FII/DII rows across daily runs.
    fiidiiTradeReact returns only the latest day — we merge with historical
    rows from prior runs so we build up a 30-day series over time.
    """
    seen: set[tuple] = set()
    merged: list[dict] = []
    cutoff = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    for row in existing + fresh:
        d   = str(row.get("date", ""))
        cat = str(row.get("category", ""))
        if d < cutoff:
            continue
        key = (d, cat)
        if key not in seen:
            seen.add(key)
            merged.append(row)
    return sorted(merged, key=lambda r: r.get("date", ""), reverse=True)


def _merge_insider(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """Deduplicate insider rows by (symbol, disclosed, person)."""
    seen: set[tuple] = set()
    merged: list[dict] = []
    cutoff = (date.today() - timedelta(days=DAYS_BACK)).isoformat()
    for row in fresh + existing:   # fresh first → prefer newer data
        disc   = str(row.get("disclosed", ""))
        sym    = str(row.get("symbol", ""))
        person = str(row.get("person", ""))
        if disc and disc < cutoff:
            continue
        key = (disc, sym, person)
        if key not in seen:
            seen.add(key)
            merged.append(row)
    return merged


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    existing = _load_existing()

    bulk   = fetch_bulk_deals()
    block  = fetch_block_deals()
    fii    = fetch_fii_dii_flow()
    inside = fetch_insider_trades()

    # FII/DII: accumulate across daily runs (API returns only current-day data)
    fii_merged    = _merge_fii(existing.get("fii_dii_flow", []), fii)
    # Insider: merge fresh + historical, dedup by key
    insider_merged = _merge_insider(existing.get("insider_trades", []), inside)

    cache = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "bulk_block_deals": bulk + block,
        "fii_dii_flow":     fii_merged,
        "insider_trades":   insider_merged,
        "summary": {
            "bulk_count":    len(bulk),
            "block_count":   len(block),
            "fii_rows":      len(fii_merged),
            "insider_count": len(insider_merged),
        },
    }

    out = os.path.realpath(CACHE_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(cache, f, indent=2, default=str)

    log.info(
        "Cache written → %s  (bulk=%d block=%d fii=%d insider=%d)",
        out, len(bulk), len(block), len(fii_merged), len(insider_merged),
    )


if __name__ == "__main__":
    main()
