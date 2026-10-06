"""Discover shutdown-related contracts on Kalshi and Polymarket; save raw JSON."""
import json, time, requests
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
KW = ("shutdown", "government funding", "continuing resolution")

def kalshi_events(status):
    out, cursor = [], None
    while True:
        p = {"limit": 200, "status": status, "with_nested_markets": "true"}
        if cursor: p["cursor"] = cursor
        r = requests.get(f"{KALSHI}/events", params=p, timeout=30)
        r.raise_for_status()
        d = r.json()
        out += d["events"]
        cursor = d.get("cursor")
        if not cursor or not d["events"]: break
        time.sleep(0.15)
    return out

def match(s): return any(k in (s or "").lower() for k in KW)

if __name__ == "__main__":
    k = []
    for st in ("open", "closed", "settled"):
        evs = kalshi_events(st)
        print("kalshi", st, len(evs), "events scanned")
        k += [e for e in evs if match(e.get("title")) or match(e.get("series_ticker")) or match(e.get("sub_title"))]
    (RAW / "kalshi_shutdown_events.json").write_text(json.dumps(k, indent=1))
    print("kalshi matches:", len(k))

    pm = {}
    for q in ("shutdown", "government shutdown", "continuing resolution", "DHS shutdown"):
        r = requests.get(f"{GAMMA}/public-search", params={"q": q, "limit_per_type": 50, "keep_closed_markets": 1}, timeout=30)
        r.raise_for_status()
        for e in r.json().get("events", []): pm[e["id"]] = e
    (RAW / "polymarket_shutdown_events.json").write_text(json.dumps(list(pm.values()), indent=1))
    print("polymarket matches:", len(pm))
