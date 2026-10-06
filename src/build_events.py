"""Build data/processed/events.csv (one row per deadline x contract) and contracts_duration.csv
from the raw discovery dumps. No price or return data is touched here."""
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"

kal = {m["ticker"]: m for m in json.load(open(RAW / "kalshi_shutdown_markets.json"))}
kal_by_event = {}
for m in kal.values():
    kal_by_event.setdefault(m["event_ticker"], []).append(m)
poly = {e["id"]: e for e in json.load(open(RAW / "polymarket_shutdown_events.json"))}

# event_id, deadline, outcome (from the plan; contract_result below is the venue's own resolution), notes
EVENTS = [
 ("E01", "2023-09-30", "averted", ""),
 ("E02", "2023-11-17", "averted", "CR passed"),
 ("E03", "2024-01-19", "averted", "staggered CR deadline"),
 ("E04", "2024-02-02", "averted", "staggered CR deadline; not in original list"),
 ("E05", "2024-03-01", "averted", "staggered CR deadline; not in original list"),
 ("E06", "2024-03-08", "averted", "staggered CR deadline"),
 ("E07", "2024-03-22", "averted", "staggered CR deadline"),
 ("E08", "2024-12-20", "averted", "no deadline-specific contract on either venue; annual proxies only"),
 ("E09", "2025-03-14", "averted", ""),
 ("E10", "2025-10-01", "shutdown_43d", ""),
 ("E11", "2026-01-30", "brief_lapse", "VERIFY: Kalshi resolved yes for Jan 31; >4-day length contract resolved no"),
 ("E12", "2026-02-14", "shutdown_dhs_partial_75d", "partial DHS shutdown"),
 ("E13", "2026-10-01", "averted", "stopgap into December"),
]
# (event_id, venue, id, role, note)
PRIMARY = [
 ("E01","kalshi","GOVSHUT-23OCT02","primary",""),
 ("E01","polymarket","902273","primary",""),
 ("E02","kalshi","GOVSHUT-23NOV17","primary",""),
 ("E02","polymarket","902620","primary","window ends Nov 19"),
 ("E03","kalshi","GOVSHUT-24JAN20","primary",""),
 ("E03","polymarket","903225","primary",""),
 ("E04","kalshi","GOVSHUT-24FEB03","primary",""),
 ("E05","kalshi","GOVSHUT-24MAR04","primary",""),
 ("E06","kalshi","GOVSHUT-24MAR11","primary",""),
 ("E06","polymarket","903336","primary","window Jan 24-Mar 9, also spans E05"),
 ("E07","kalshi","GOVSHUT-24MAR23","primary",""),
 ("E07","polymarket","903687","primary","window Mar 1-Mar 23, also spans E06"),
 ("E08","kalshi","SHUTDOWNBY-24","annual_proxy","whole-year contract, not deadline-specific"),
 ("E08","polymarket","12327","annual_proxy","window Aug 30-Dec 31 2024, not deadline-specific"),
 ("E08","polymarket","15706","related","'pass funding bill by midnight' - different question"),
 ("E09","kalshi","KXSHUTDOWNBYDATE-25MAR18","primary",""),
 ("E09","polymarket","16547","primary","funding-lapse definition (differs from OPM-based Kalshi)"),
 ("E10","kalshi","KXGOVSHUT-25OCT01","primary",""),
 ("E10","polymarket","41136","primary",""),
 ("E10","polymarket","21634","secondary","funding-lapse definition"),
 ("E11","kalshi","KXGOVSHUT-26JAN31","primary",""),
 ("E11","polymarket","80505","primary",""),
 ("E11","polymarket","118074","secondary","funding-lapse definition"),
 ("E12","kalshi","KXGOVTSHUTDOWN-26FEB14","primary",""),
 ("E12","polymarket","194637","primary","resolved NO although DHS lapse began Feb 14; wording requires an OPM-announced shutdown, Kalshi resolved YES"),
 ("E13","kalshi","KXGOVTSHUTDOWN-26OCT01","primary",""),
 ("E13","polymarket","580520","primary",""),
 ("E13","polymarket","801502","secondary","funding-lapse definition"),
]
# duration contracts: (event ids they cover, venue, kalshi event ticker | polymarket event id)
DURATION = [
 (["E01","E02"],"kalshi","GOVSHUTLENGTH-23DEC31"),
 (["E03","E04","E05","E06","E07"],"kalshi","GOVSHUTLENGTH-24JUN30"),
 (["E08","E09"],"kalshi","KXGOVSHUTLENGTH-25JUL01"),
 (["E10"],"kalshi","KXGOVSHUTLENGTH-26JAN01"),
 (["E11"],"kalshi","KXGOVSHUTLENGTH-26FEB28"),
 (["E12"],"kalshi","KXGOVTSHUTLENGTH-26FEB07"),
 (["E10"],"polymarket","52169"), (["E10"],"polymarket","55056"),
 (["E10"],"polymarket","61075"), (["E10"],"polymarket","77322"), (["E10"],"polymarket","45599"),
 (["E11"],"polymarket","186375"),
 (["E12"],"polymarket","200659"), (["E12"],"polymarket","209521"), (["E12"],"polymarket","209528"),
 (["E12"],"polymarket","308583"), (["E12"],"polymarket","386210"),
]

def kalshi_row(t):
    m = kal[t] if t in kal else kal_by_event[t][0]
    return dict(contract_id=m["ticker"], series=m["event_ticker"].split("-")[0], contract_open=m["open_time"][:10],
                contract_close=m["close_time"][:10], contract_result=m.get("result"), question=m.get("title"))

def poly_row(eid):
    e = poly[eid]; m = e["markets"][0]
    toks = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"]); pr = json.loads(m["outcomePrices"])
    res = outs[pr.index("1")].lower() if "1" in pr else None
    return dict(contract_id=toks[outs.index("Yes")], series=e["slug"], contract_open=(m.get("startDate") or "")[:10],
                contract_close=(m.get("closedTime") or "")[:10], contract_result=res, question=m["question"],
                condition_id=m.get("conditionId"), gamma_event_id=eid)

# first calendar day (00:00 ET) on which a lapse would begin; the 'deadline' column mixes conventions
LAPSE_START = {"E01":"2023-10-01","E02":"2023-11-18","E03":"2024-01-20","E04":"2024-02-03","E05":"2024-03-02",
               "E06":"2024-03-09","E07":"2024-03-23","E08":"2024-12-21","E09":"2025-03-15","E10":"2025-10-01",
               "E11":"2026-01-31","E12":"2026-02-14","E13":"2026-10-01"}
ev = {e[0]: e for e in EVENTS}
rows = []
for eid, venue, cid, role, note in PRIMARY:
    r = kalshi_row(cid) if venue == "kalshi" else poly_row(cid)
    # Kalshi: the series ticker is what you search on; keep the market ticker in contract_id
    r.update(event_id=eid, deadline=ev[eid][1], lapse_start=LAPSE_START[eid], outcome=ev[eid][2], venue=venue, role=role,
             note="; ".join(x for x in (note, ev[eid][3]) if x))
    rows.append(r)
cols = ["event_id","deadline","lapse_start","outcome","venue","contract_id","contract_open","contract_close","contract_result",
        "role","series","question","condition_id","gamma_event_id","note"]
df = pd.DataFrame(rows).reindex(columns=cols)
OUT.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT / "events.csv", index=False)

drows = []
for eids, venue, ident in DURATION:
    if venue == "kalshi":
        for m in kal_by_event[ident]:
            drows.append(dict(event_ids=";".join(eids), venue=venue, contract_id=m["ticker"], group=ident,
                              contract_open=m["open_time"][:10], contract_result=m.get("result"),
                              question=m.get("title")))
    else:
        e = poly[ident]
        for m in e["markets"]:
            toks = json.loads(m["clobTokenIds"]); outs = json.loads(m["outcomes"]); pr = json.loads(m["outcomePrices"])
            drows.append(dict(event_ids=";".join(eids), venue=venue, contract_id=toks[outs.index("Yes")], group=e["slug"],
                              contract_open=(m.get("startDate") or "")[:10],
                              contract_result=outs[pr.index("1")].lower() if "1" in pr else None, question=m["question"]))
pd.DataFrame(drows).to_csv(OUT / "contracts_duration.csv", index=False)
print(df[["event_id","deadline","outcome","venue","contract_id","contract_open","contract_result","role"]].assign(
    contract_id=lambda d: d.contract_id.str[:26]).to_string(index=False))
print(len(df), "deadline contracts;", len(drows), "duration strikes")
