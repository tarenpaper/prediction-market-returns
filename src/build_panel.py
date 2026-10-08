"""Build the analysis panel exactly as specified in PREREGISTRATION.md (sections 4-6). No hypothesis tests here.

Outputs (data/processed/):
  snapshots.csv  one row per event x window x venue: prices at the window's two snapshots and dP
  panel.csv      one row per event x window x firm: returns, beta, AR, dP (Kalshi and Polymarket), exposure
  qa_panel.txt   quality-check printout
"""
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; P = ROOT / "data" / "processed"
NY = "America/New_York"
MAX_FFILL, MAX_SPREAD, LOOKBACK_DAYS = pd.Timedelta(hours=12), 0.10, 30
EST_N, EST_GAP = 250, 30                      # beta window: 250 trading days ending 30 trading days before first window
EARLY_CLOSE = pd.to_datetime(["2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03", "2024-11-29", "2024-12-24",
                              "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27"])
CLUSTER = {e: "C2024" for e in ["E03", "E04", "E05", "E06", "E07"]}

ev = pd.read_csv(P / "events.csv", dtype=str)
mk = pd.read_csv(P / "markets_hourly.csv", dtype={"contract_id": str}); mk["ts"] = pd.to_datetime(mk["ts"], utc=True)
st = pd.read_csv(P / "stocks_daily.csv"); st["Date"] = pd.to_datetime(st["Date"], format="%m/%d/%Y")
ex = pd.read_csv(P / "exposure_updated.csv")
TICK = ["CACI", "SAIC", "LDOS", "BAH", "PSN", "ACN", "EPAM", "CTSH"]


def at(d, hm):
    return pd.Timestamp(f"{pd.Timestamp(d):%Y-%m-%d} {hm}", tz=NY).tz_convert("UTC")


# ---- trading calendar and windows ----
days = pd.DatetimeIndex(sorted(st.loc[st.ticker == "SPY", "Date"].unique()))
rows = []
for i, d in enumerate(days):
    if i:
        rows.append(dict(day=d, wtype="overnight", start=at(days[i - 1], "16:00"), end=at(d, "09:30"), i=i))
    rows.append(dict(day=d, wtype="intraday", start=at(d, "09:30"), end=at(d, "16:00"), i=i))
win = pd.DataFrame(rows)

# ---- stock returns (raw per prereg; dividend-adjusted kept as an extra column) ----
px = {c: st.pivot(index="Date", columns="ticker", values=c).reindex(days) for c in ["Open", "Close", "Adj Close"]}
f = px["Adj Close"] / px["Close"]
ret = {"overnight": px["Open"] / px["Close"].shift(1) - 1, "intraday": px["Close"] / px["Open"] - 1}
ret_adj = {"overnight": (px["Open"] * f) / (px["Close"] * f).shift(1) - 1,
           "intraday": (px["Close"] * f) / (px["Open"] * f) - 1}

# ---- prediction-market snapshots ----
snap_times = pd.DataFrame({"snap": pd.concat([win.start, win.end]).drop_duplicates().sort_values()})


def snapshots(cid, venue):
    o = mk[mk.contract_id == cid].sort_values("ts")[["ts", "price", "spread"]]
    if venue == "kalshi":
        o = o.assign(price=np.where(o.spread > MAX_SPREAD, np.nan, o.price))
    m = pd.merge_asof(snap_times, o.rename(columns={"ts": "obs_ts"}), left_on="snap", right_on="obs_ts",
                      direction="backward", tolerance=MAX_FFILL)
    m["stale_h"] = (m.snap - m.obs_ts).dt.total_seconds() / 3600
    return m.set_index("snap"), o.ts.min(), o.ts.max()


evwin = []
for r in ev.itertuples():
    if r.role != "primary":
        continue
    s, first_obs, last_obs = snapshots(r.contract_id, r.venue)
    lapse = at(r.lapse_start, "00:00")
    lo = max(first_obs, lapse - pd.Timedelta(days=LOOKBACK_DAYS))
    w = win.copy()
    w["p_start"] = s.loc[w.start, "price"].values
    w["p_end"] = s.loc[w.end, "price"].values
    w["stale_start"] = s.loc[w.start, "stale_h"].values
    w["stale_end"] = s.loc[w.end, "stale_h"].values
    w["dP"] = w.p_end - w.p_start
    pre = (w.end <= lapse) & (w.start >= lo)
    res = (w.wtype == "overnight") & (w.start < lapse) & (w.end > lapse)
    w["phase"] = np.where(pre, "pre", np.where(res, "resolution", ""))
    w = w[w.phase != ""].assign(event_id=r.event_id, venue=r.venue, contract_id=r.contract_id,
                                lapse_start=r.lapse_start, first_obs=first_obs,
                                contract_result=r.contract_result, outcome=r.outcome)
    evwin.append(w)
sn = pd.concat(evwin, ignore_index=True)
sn["cluster"] = sn.event_id.map(lambda e: CLUSTER.get(e, e))
sn["primary_sample"] = sn.event_id != "E08"
sn["early_close_day"] = sn.day.isin(EARLY_CLOSE)
sn.to_csv(P / "snapshots.csv", index=False)

# ---- betas (per event x window type x firm) and abnormal returns ----
first_pre = sn[(sn.venue == "kalshi") & (sn.phase == "pre")].groupby("event_id").i.min()


def beta(event, wtype, tk):
    i0 = first_pre.get(event)
    if i0 is None:
        return np.nan, 0
    sl = slice(max(i0 - EST_GAP - EST_N, 0), i0 - EST_GAP)
    y, x = ret[wtype][tk].iloc[sl], ret[wtype]["SPY"].iloc[sl]
    ok = y.notna() & x.notna()
    if ok.sum() < 100:
        return np.nan, int(ok.sum())
    return np.cov(y[ok], x[ok])[0, 1] / np.var(x[ok], ddof=1), int(ok.sum())


kal = sn[sn.venue == "kalshi"].rename(columns={"p_start": "pk_start", "p_end": "pk_end", "dP": "dP_kalshi"})
pol = sn[sn.venue == "polymarket"][["event_id", "wtype", "day", "dP"]].rename(columns={"dP": "dP_poly"})
base = kal.merge(pol, on=["event_id", "wtype", "day"], how="left")
bcache = {(e, w, t): beta(e, w, t) for e in base.event_id.unique() for w in ("overnight", "intraday") for t in TICK}
out = []
for b in base.itertuples():
    for tk in TICK:
        bt, nb = bcache[(b.event_id, b.wtype, tk)]
        r_raw, r_adj = ret[b.wtype][tk].loc[b.day], ret_adj[b.wtype][tk].loc[b.day]
        r_m = ret[b.wtype]["SPY"].loc[b.day]
        out.append(dict(event_id=b.event_id, cluster=b.cluster, day=b.day, wtype=b.wtype, phase=b.phase, ticker=tk,
                        ret=r_raw, ret_adj=r_adj, ret_spy=r_m, beta=bt, n_beta=nb, ar=r_raw - bt * r_m,
                        dP_kalshi=b.dP_kalshi, dP_poly=b.dP_poly, pk_start=b.pk_start, pk_end=b.pk_end,
                        primary_sample=b.primary_sample, outcome=b.outcome, early_close_day=b.early_close_day))
pn = pd.DataFrame(out)
e = ex.set_index("ticker")
pn["group"] = np.where(pn.ticker.isin(["ACN", "EPAM", "CTSH"]), "control", "exposed")
pn["fed_share"] = pn.ticker.map(e.federal_share).fillna(0)
pn["dhs_share"] = pn.ticker.map(e.dhs_share_fy22_25).fillna(0)
pn.to_csv(P / "panel.csv", index=False)

# ---- QA ----
L = []


def p(*a):
    L.append(" ".join(str(x) for x in a)); print(*a)


p("== kalshi windows with non-missing dP, by event / phase / window type")
k = sn[sn.venue == "kalshi"]
p(k.assign(ok=k.dP.notna()).pivot_table(index="event_id", columns=["phase", "wtype"], values="ok", aggfunc=["sum"]).fillna(0).astype(int).to_string())
p("\n== kalshi pre windows total per event (incl. missing)")
p(k[k.phase == "pre"].groupby("event_id").size().to_dict())
p("\n== polymarket pre windows with dP")
q = sn[(sn.venue == "polymarket") & (sn.phase == "pre")]
p(q.assign(ok=q.dP.notna()).groupby(["event_id", "wtype"]).ok.sum().unstack().to_string())
p("\n== dP distribution, kalshi pre windows (probability points)")
d = k[(k.phase == "pre") & k.dP.notna()]
p(d.groupby("wtype").dP.describe().round(4).to_string())
p("share of windows with dP == 0 exactly:", round((d.dP == 0).mean(), 3))
p("max staleness hours at either snapshot:", round(d[["stale_start", "stale_end"]].max().max(), 1))
p("early-close days in pre sample:", int(k[k.phase == "pre"].early_close_day.sum()))
p("\n== returns sanity (all event windows)")
p(pn.groupby(["wtype", "group"]).ret.agg(["count", "mean", "std", "min", "max"]).round(4).to_string())
p("NaN returns:", int(pn.ret.isna().sum()), "| NaN betas:", int(pn.beta.isna().sum()), "| min n_beta:", int(pn.n_beta.min()))
p("\n== mean beta across events")
p(pn.groupby(["ticker", "wtype"]).beta.mean().unstack().round(2).to_string())
p("\n== panel rows by phase / primary sample:", {str(k_): v for k_, v in pn.groupby(["phase", "primary_sample"]).size().items()})
ready = (pn.phase == "pre") & (pn.wtype == "overnight") & pn.dP_kalshi.notna() & pn.ar.notna() & pn.primary_sample
p("regression-ready rows (pre, overnight, primary sample):", int(ready.sum()), "| distinct firm-windows:", int(ready.sum() / 8))
(P / "qa_panel.txt").write_text("\n".join(L))
