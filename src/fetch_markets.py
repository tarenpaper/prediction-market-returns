"""Pull hourly Kalshi candles and Polymarket price history for every contract in events.csv
(and optionally contracts_duration.csv). Raw JSON is written to data/raw/ BEFORE any parsing; existing files are skipped."""
import json, sys, time, requests, pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
K = "https://api.elections.kalshi.com/trade-api/v2"
CLOB = "https://clob.polymarket.com/prices-history"
DAY = 86400

def ts(d, plus=0): return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()) + plus * DAY

def get(url, params, tries=4):
    for i in range(tries):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(2 ** i); continue
        return r
    return r

def kalshi(ticker, open_d, close_d):
    start, end = ts(open_d, -1), min(ts(close_d, 2), int(time.time()))
    for a in range(start, end, 50 * DAY):          # hourly candles: stay well under the per-call cap
        b = min(a + 50 * DAY, end); f = RAW / "kalshi_candles" / f"{ticker}_{a}.json"
        if f.exists(): continue
        for path in (f"/historical/markets/{ticker}/candlesticks", f"/series/{ticker.split('-')[0]}/markets/{ticker}/candlesticks"):
            r = get(K + path, {"start_ts": a, "end_ts": b, "period_interval": 60})
            if r.status_code == 200 and r.json().get("candlesticks"): break
        f.write_text(json.dumps({"ticker": ticker, "status": r.status_code, "path": path, "start": a, "end": b, **(r.json() if r.status_code == 200 else {"error": r.text})}))
        time.sleep(0.12)

def poly(token, open_d, close_d):
    start, end = ts(open_d, -1), min(ts(close_d, 2), int(time.time()))
    for a in range(start, end, 10 * DAY):          # CLOB rejects long windows at fine fidelity
        b = min(a + 10 * DAY, end); f = RAW / "poly_history" / f"{token}_{a}.json"
        if f.exists(): continue
        r = get(CLOB, {"market": token, "startTs": a, "endTs": b, "fidelity": 60})
        f.write_text(json.dumps({"token": token, "status": r.status_code, "start": a, "end": b, **(r.json() if r.status_code == 200 else {"error": r.text})}))
        time.sleep(0.12)

if __name__ == "__main__":
    ev = pd.read_csv(PROC / "events.csv", dtype=str)
    rows = ev[["venue", "contract_id", "contract_open", "contract_close"]]
    if "--duration" in sys.argv:
        d = pd.read_csv(PROC / "contracts_duration.csv", dtype=str)
        # duration contracts: close date unknown for some; fall back to a generous window
        d["contract_close"] = d["contract_open"].map(lambda x: (datetime.fromisoformat(x) + timedelta(days=180)).date().isoformat())
        rows = pd.concat([rows, d[["venue", "contract_id", "contract_open", "contract_close"]]])
    rows = rows.drop_duplicates().dropna(subset=["contract_open"])
    for i, r in enumerate(rows.itertuples(), 1):
        (kalshi if r.venue == "kalshi" else poly)(r.contract_id, r.contract_open, r.contract_close if isinstance(r.contract_close, str) and r.contract_close else datetime.now().date().isoformat())
        print(i, len(rows), r.venue, r.contract_id[:30], flush=True)
