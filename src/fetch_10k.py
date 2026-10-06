"""Download the latest 10-K primary document for each ticker from EDGAR; save HTML and stripped text."""
import requests, re, json, time
from pathlib import Path
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "10k"
H = {"User-Agent": "MLP-Project taran.venkatesh@gmail.com"}
T = ["CACI","SAIC","LDOS","BAH","PSN","ACN","EPAM","CTSH"]
ciks = dict(CACI=16058, SAIC=1571123, LDOS=1336920, BAH=1443646, PSN=275880, ACN=1467373, EPAM=1352010, CTSH=1058290)
import sys
for t in (sys.argv[1:] or T):
    s = requests.get(f"https://data.sec.gov/submissions/CIK{ciks[t]:010d}.json", headers=H).json()["filings"]["recent"]
    i = next(i for i, f in enumerate(s["form"]) if f == "10-K")
    acc, doc = s["accessionNumber"][i], s["primaryDocument"][i]
    url = f"https://www.sec.gov/Archives/edgar/data/{ciks[t]}/{acc.replace('-','')}/{doc}"
    html = requests.get(url, headers=H).text
    (RAW / f"{t}_10K_{s['reportDate'][i]}.html").write_text(html, encoding="utf-8")
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style).*?</\1>", " ", html)))
    txt = re.sub(r"&#160;|&nbsp;", " ", txt).replace("&amp;", "&").replace("&#8217;", "'")
    (RAW / f"{t}_10K.txt").write_text(txt, encoding="utf-8")
    print(t, s["reportDate"][i], s["filingDate"][i], url, len(txt), flush=True); time.sleep(0.3)
