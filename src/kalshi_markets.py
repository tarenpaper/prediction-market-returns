"""Pull every market in the shutdown-related Kalshi series (live + historical) to data/raw."""
import json, time, requests
from pathlib import Path
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
K = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ["GOVSHUT","KXGOVSHUT","GOVSHUTLENGTH","KXGOVSHUTLENGTH","SHUTLENGTH","KXSHUTLENGTH",
          "KXGOVTSHUTDOWN","KXGOVTSHUTLENGTH","SHUTDOWNBY","KXSHUTDOWNBY","KXSHUTDOWNBYDATE","KXNUMSHUTDOWNS"]

def paged(path, key, params):
    out, cur = [], None
    while True:
        p = dict(params, limit=1000)
        if cur: p["cursor"] = cur
        r = requests.get(f"{K}{path}", params=p, timeout=30)
        if r.status_code != 200: return out, r.status_code
        d = r.json(); out += d.get(key, []); cur = d.get("cursor")
        if not cur or not d.get(key): return out, 200
        time.sleep(0.15)

if __name__ == "__main__":
    allm = {}
    for s in SERIES:
        m, c = paged("/markets", "markets", {"series_ticker": s})
        h, hc = paged("/historical/markets", "markets", {"series_ticker": s})
        print(f"{s:20s} live={len(m)}({c}) hist={len(h)}({hc})")
        for x in m + h: allm[x["ticker"]] = x
    (RAW / "kalshi_shutdown_markets.json").write_text(json.dumps(list(allm.values()), indent=1))
    print("total markets", len(allm))
