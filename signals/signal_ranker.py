"""
Signal ranking — composite 0-100 score for open trade signals.

Five factors (weights add to 100):
  Confidence   25 — user-visible 1-5 star confidence
  Technical    20 — RSI/MACD/SMA alignment score
  Fundamental  15 — valuation/profitability composite
  Risk/Reward  20 — R:R ratio normalised (cap at 5×)
  Entry Timing 20 — how close current price is to the ideal entry

Entry Timing is the key differentiator: full 20 pts when price is still at/below
entry, drops to 0 once price has moved >5% past entry (too late to enter safely).
"""
from __future__ import annotations
from typing import Optional
import yfinance as yf


def score_signal(sig: dict, curr_price: Optional[float]) -> tuple[float, dict]:
    """
    Returns (total_score, breakdown_dict).
    breakdown keys: Confidence, Technical, Fundamental, Risk/Reward, Entry Timing, _prox_label
    """
    bd: dict = {}

    # 1. Confidence  (0–25 pts)
    conf = sig.get("confidence") or 1
    bd["Confidence"] = round((conf / 5) * 25, 1)

    # 2. Technical score  (0–20 pts)
    tech = float(sig.get("technical_score") or 0.5)
    bd["Technical"] = round(tech * 20, 1)

    # 3. Fundamental score  (0–15 pts)
    fund = float(sig.get("fundamental_score") or 0.5)
    bd["Fundamental"] = round(fund * 15, 1)

    # 4. Risk / Reward  (0–20 pts) — RR 2× = 5 pts, RR 5× = 20 pts
    rr = min(float(sig.get("risk_reward") or 2.0), 5.0)
    bd["Risk/Reward"] = round(max(0.0, ((rr - 1.0) / 4.0) * 20), 1)

    # 5. Entry proximity  (0–20 pts)
    pts_prox, prox_label = 10.0, "Price unavailable"
    if curr_price is not None:
        entry   = float(sig.get("entry_price") or 0)
        is_long = (sig.get("direction") or "LONG") == "LONG"
        if entry > 0:
            moved_pct = ((curr_price - entry) / entry * 100) if is_long \
                        else ((entry - curr_price) / entry * 100)
            if moved_pct <= 0:
                pts_prox, prox_label = 20, "At / below entry ✓"
            elif moved_pct <= 1:
                pts_prox, prox_label = 17, f"+{moved_pct:.1f}% from entry"
            elif moved_pct <= 2:
                pts_prox, prox_label = 13, f"+{moved_pct:.1f}% from entry"
            elif moved_pct <= 3:
                pts_prox, prox_label = 8,  f"+{moved_pct:.1f}% from entry"
            elif moved_pct <= 5:
                pts_prox, prox_label = 3,  f"+{moved_pct:.1f}% — entry missed"
            else:
                pts_prox, prox_label = 0,  f"+{moved_pct:.1f}% — too late"
    bd["Entry Timing"]  = round(pts_prox, 1)
    bd["_prox_label"]   = prox_label

    total = sum(bd[k] for k in ("Confidence", "Technical", "Fundamental", "Risk/Reward", "Entry Timing"))
    return round(total, 1), bd


def fetch_prices(sigs: list[dict]) -> dict[str, Optional[float]]:
    """Fetch latest close price for each unique ticker in one pass."""
    prices: dict[str, Optional[float]] = {}
    for sig in sigs:
        ticker = sig["ticker"]
        if ticker in prices:
            continue
        try:
            df = yf.Ticker(ticker).history(period="2d", interval="1d", auto_adjust=True)
            prices[ticker] = float(df["Close"].iloc[-1]) if df is not None and not df.empty else None
        except Exception:
            prices[ticker] = None
    return prices


def rank_signals(open_sigs: list[dict]) -> list[tuple[float, dict, dict, Optional[float]]]:
    """
    Score and rank all open signals.
    Returns list of (score, breakdown, signal_dict, curr_price) sorted descending.
    Each ticker appears at most once (highest-scored entry wins).
    """
    if not open_sigs:
        return []
    prices = fetch_prices(open_sigs)
    scored = []
    for sig in open_sigs:
        cp = prices.get(sig["ticker"])
        sc, bd = score_signal(sig, cp)
        scored.append((sc, bd, sig, cp))
    scored.sort(key=lambda x: x[0], reverse=True)

    # One entry per ticker — highest score already at the front after sort.
    seen: set[str] = set()
    deduped = []
    for item in scored:
        ticker = item[2]["ticker"]
        if ticker not in seen:
            seen.add(ticker)
            deduped.append(item)
    return deduped
