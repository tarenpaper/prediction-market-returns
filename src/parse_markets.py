"""Parse raw hourly JSON into data/processed/markets_hourly.csv (UTC). Kalshi price = mid of yes bid/ask close;
candles ending after the contract's close_time are dropped (post-settlement bid=0/ask=1 artefacts)."""
import json, glob, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; RAW, PROC = ROOT/"data"/"raw", ROOT/"data"/"processed"
ev = pd.read_csv(PROC/"events.csv", dtype=str).drop_duplicates("contract_id").set_index("contract_id")
rows = []
for f in glob.glob(str(RAW/"kalshi_candles"/"*.json")):
    d = json.load(open(f)); t = d["ticker"]
    close = pd.Timestamp(ev.loc[t, "contract_close"], tz="UTC") + pd.Timedelta(days=1) if t in ev.index else None
    for c in d.get("candlesticks", []):
        bid = c["yes_bid"].get("close", c["yes_bid"].get("close_dollars"))   # historical vs live schema
        ask = c["yes_ask"].get("close", c["yes_ask"].get("close_dollars"))
        if bid is None or ask is None: continue
        bid, ask = float(bid), float(ask); tt = pd.to_datetime(c["end_period_ts"], unit="s", utc=True)
        if close is not None and tt > close: continue
        rows.append(dict(venue="kalshi", contract_id=t, ts=tt, price=(bid+ask)/2, spread=ask-bid, volume=float(c.get("volume") or c.get("volume_fp") or 0)))
for f in glob.glob(str(RAW/"poly_history"/"*.json")):
    d = json.load(open(f))
    for h in d.get("history", []):
        rows.append(dict(venue="polymarket", contract_id=d["token"], ts=pd.to_datetime(h["t"], unit="s", utc=True), price=float(h["p"]), spread=None, volume=None))
df = pd.DataFrame(rows).drop_duplicates(["contract_id","ts"]).sort_values(["contract_id","ts"])
df.to_csv(PROC/"markets_hourly.csv", index=False)
g = df.groupby(["venue","contract_id"]).agg(n=("ts","size"), first=("ts","min"), last=("ts","max"), med_spread=("spread","median"))
print(g.reset_index().assign(contract_id=lambda x: x.contract_id.str[:24]).to_string(index=False))
