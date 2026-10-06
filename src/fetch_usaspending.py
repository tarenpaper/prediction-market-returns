"""DHS vs all-agency prime contract obligations by company (USAspending, award types A-D), gov FY2022-FY2026.
Raw JSON saved first to data/raw/usaspending/. Prime awards only: subcontract dollars are NOT captured."""
import json, re, time, requests, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT/"data"/"raw"/"usaspending"; OUT = ROOT/"data"/"processed"
U = "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient"
DHS = [{"type":"awarding","tier":"toptier","name":"Department of Homeland Security"}]
# search text -> regex on recipient name (legal entities / acquired subsidiaries)
CO = {"CACI": ("CACI", r"^CACI"),
      "SAIC": ("SCIENCE APPLICATIONS", r"^(SCIENCE APPLICATIONS INTERNATIONAL|ENGILITY|DYNAMICS RESEARCH)"),
      "LDOS": ("LEIDOS", r"^LEIDOS"), "BAH": ("BOOZ ALLEN", r"^BOOZ ALLEN"),
      "PSN": ("PARSONS", r"^PARSONS"), "ACN": ("ACCENTURE FEDERAL", r"^ACCENTURE FEDERAL"),
      "EPAM": ("EPAM", r"^EPAM"), "CTSH": ("COGNIZANT", r"^COGNIZANT")}
EXTRA = {"SAIC": ["ENGILITY", "DYNAMICS RESEARCH"]}

def pull(text, fy, dhs):
    tag = f"{text.replace(' ','_')}_FY{fy}_{'dhs' if dhs else 'all'}"; f = RAW/f"{tag}.json"
    if f.exists(): return json.load(open(f))
    flt = {"time_period":[{"start_date":f"{fy-1}-10-01","end_date":f"{fy}-09-30"}], "award_type_codes":["A","B","C","D"], "recipient_search_text":[text]}
    if dhs: flt["agencies"] = DHS
    res, page = [], 1
    while True:
        for i in range(4):
            r = requests.post(U, json={"filters":flt,"limit":100,"page":page}, timeout=90)
            if r.status_code == 200: break
            time.sleep(2**i)
        d = r.json(); res += d["results"]
        if not d.get("page_metadata", {}).get("hasNext"): break
        page += 1; time.sleep(0.2)
    f.write_text(json.dumps(res)); return res

rows = []
for t, (text, rx) in CO.items():
    for fy in range(2022, 2027):
        for dhs in (True, False):
            res = []
            for s in [text] + EXTRA.get(t, []): res += pull(s, fy, dhs)
            seen = {}
            for x in res:
                if re.search(rx, x["name"] or "", re.I): seen[(x["name"], x["code"])] = x["amount"]
            rows.append(dict(ticker=t, gov_fy=fy, scope="dhs" if dhs else "all", obligations=sum(seen.values()), n_entities=len(seen)))
        print(t, fy, flush=True)
df = pd.DataFrame(rows)
p = df.pivot_table(index=["ticker","gov_fy"], columns="scope", values="obligations").reset_index()
p["dhs_share_of_federal_obl"] = p["dhs"] / p["all"]
p.to_csv(OUT/"usaspending_dhs.csv", index=False)
print(p.assign(dhs=lambda d: (d.dhs/1e6).round(1), all=lambda d: (d["all"]/1e6).round(1), dhs_share_of_federal_obl=lambda d: d.dhs_share_of_federal_obl.round(3)).to_string(index=False))
