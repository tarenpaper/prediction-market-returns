"""Secondary tests H2-H4 as registered (PREREGISTRATION.md section 7). Holm-adjusted across the three.

H2  E11-E13, pre-resolution overnight: AR = a_j + b1*dP*Fed + b2*dP*DHS + e ; prediction b2 < 0.
    Only 3 clusters -> judged by sign/size and a permutation test (shuffle dP across windows within event, 9,999 draws).
H3  H1 repeated on intraday windows (wild cluster bootstrap-t, as in H1). Prediction b < 0.
H4  Overnight window containing the lapse: (mean AR exposed - mean AR control) per event; compare shutdown (E10,E11,E12)
    vs averted events. Prediction: lower for shutdown. Exact permutation test over label assignments.
All p-values two-sided.
"""
import itertools, json
import numpy as np, pandas as pd
from pathlib import Path
from scipy import stats

P = Path(__file__).resolve().parents[1] / "data" / "processed"
B_DRAWS, SEED = 9999, 20261007
pn = pd.read_csv(P / "panel.csv", parse_dates=["day"])
pn = pn[pn.primary_sample]


def demean(v, g):
    v = np.asarray(v, float)
    if v.ndim == 1:
        return v - pd.Series(v).groupby(g).transform("mean").to_numpy()
    return np.column_stack([demean(v[:, k], g) for k in range(v.shape[1])])


# ---------------- H2 ----------------
d2 = pn[pn.event_id.isin(["E11", "E12", "E13"]) & (pn.phase == "pre") & (pn.wtype == "overnight")
        & pn.dP_kalshi.notna() & pn.ar.notna()].reset_index(drop=True)


def ols2(df, dp):
    X = np.column_stack([dp * df.fed_share.to_numpy(), dp * df.dhs_share.to_numpy()])
    Xt, yt = demean(X, df.event_id.to_numpy()), demean(df.ar.to_numpy(), df.event_id.to_numpy())
    return np.linalg.lstsq(Xt, yt, rcond=None)[0], Xt


b, Xt = ols2(d2, d2.dP_kalshi.to_numpy())
rng = np.random.default_rng(SEED)
win = d2[["event_id", "day"]].drop_duplicates().reset_index(drop=True)
dpw = d2.drop_duplicates(["event_id", "day"]).set_index(["event_id", "day"]).dP_kalshi
key = list(zip(d2.event_id, d2.day))
perm_b2 = np.empty(B_DRAWS)
for k in range(B_DRAWS):
    shuffled = {}
    for e, g in win.groupby("event_id"):
        vals = dpw.loc[[(e, x) for x in g.day]].to_numpy().copy(); rng.shuffle(vals)
        shuffled.update({(e, x): v for x, v in zip(g.day, vals)})
    perm_b2[k] = ols2(d2, np.array([shuffled[kk] for kk in key]))[0][1]
p_h2 = (np.sum(np.abs(perm_b2) >= abs(b[1])) + 1) / (B_DRAWS + 1)
firm = pn.drop_duplicates("ticker").set_index("ticker")[["fed_share", "dhs_share"]]
H2 = dict(test="H2", b1_fed=b[0], b2_dhs=b[1], p_perm_two_sided=p_h2, n_obs=len(d2), n_event_windows=len(win),
          events=sorted(d2.event_id.unique()), corr_fed_dhs_across_firms=float(firm.fed_share.corr(firm.dhs_share)),
          perm_b2_5_95=[float(np.percentile(perm_b2, 5)), float(np.percentile(perm_b2, 95))])

# ---------------- H3 ----------------
d3 = pn[(pn.phase == "pre") & (pn.wtype == "intraday") & pn.dP_kalshi.notna() & pn.ar.notna()].copy()
d3["x"] = d3.dP_kalshi * d3.fed_share


def fit1(y, x, ev, cl):
    yt, xt = demean(y, ev), demean(x, ev)
    sxx = xt @ xt; bb = (xt @ yt) / sxx; u = yt - bb * xt
    G, N, K = len(np.unique(cl)), len(y), 1 + len(np.unique(ev))
    sc = pd.Series(xt * u).groupby(cl).sum().to_numpy()
    return bb, np.sqrt((G / (G - 1)) * ((N - 1) / (N - K)) * (sc @ sc) / sxx**2), yt


y, x, ev, cl = d3.ar.to_numpy(float), d3.x.to_numpy(float), d3.event_id.to_numpy(), d3.cluster.to_numpy()
b3, se3, u0 = fit1(y, x, ev, cl)
t3 = b3 / se3
fitted0 = y - u0
cls = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in cls}
ts = np.empty(B_DRAWS)
for k in range(B_DRAWS):
    w = np.empty(len(y))
    for c in cls:
        w[idx[c]] = rng.choice([-1.0, 1.0])
    bs, ses, _ = fit1(fitted0 + w * u0, x, ev, cl)
    ts[k] = bs / ses
G3 = len(cls)
H3 = dict(test="H3", b=b3, se_cr1=se3, t=t3, p_wild_cluster_bootstrap=(np.sum(np.abs(ts) >= abs(t3)) + 1) / (B_DRAWS + 1),
          p_cr1_t_Gm1=2 * stats.t.sf(abs(t3), G3 - 1), n_obs=len(d3), n_clusters=G3, n_events=len(np.unique(ev)),
          ci95_cr1=[b3 - stats.t.ppf(.975, G3 - 1) * se3, b3 + stats.t.ppf(.975, G3 - 1) * se3])

# ---------------- H4 ----------------
r = pn[pn.phase == "resolution"]
D = r.groupby(["event_id", "group"]).ar.mean().unstack()
D["diff"] = D.exposed - D.control
D["shutdown"] = D.index.isin(["E10", "E11", "E12"])
obs = D.loc[D.shutdown, "diff"].mean() - D.loc[~D.shutdown, "diff"].mean()
vals, n_s = D["diff"].to_numpy(), int(D.shutdown.sum())
null = np.array([vals[list(c)].mean() - np.delete(vals, list(c)).mean() for c in itertools.combinations(range(len(vals)), n_s)])
p_h4 = float(np.mean(np.abs(null) >= abs(obs) - 1e-12))
H4 = dict(test="H4", mean_diff_shutdown=float(D.loc[D.shutdown, "diff"].mean()), mean_diff_averted=float(D.loc[~D.shutdown, "diff"].mean()),
          diff_in_means=float(obs), p_exact_perm_two_sided=p_h4, n_shutdown=n_s, n_averted=len(vals) - n_s,
          n_permutations=len(null), per_event=D[["exposed", "control", "diff", "shutdown"]].round(5).reset_index().to_dict("records"))

# ---------------- Holm across H2-H4 ----------------
ps = {"H2": H2["p_perm_two_sided"], "H3": H3["p_wild_cluster_bootstrap"], "H4": H4["p_exact_perm_two_sided"]}
order = sorted(ps, key=ps.get); holm, run = {}, 0.0
for i, k in enumerate(order):
    run = max(run, min(1.0, (len(ps) - i) * ps[k])); holm[k] = run
for h, o in zip((H2, H3, H4), ("H2", "H3", "H4")):
    h["p_holm"] = holm[o]
(P / "secondary_results.json").write_text(json.dumps([H2, H3, H4], indent=1, default=float))

for h in (H2, H3, H4):
    print(f"\n=== {h['test']}")
    for k, v in h.items():
        if k == "per_event":
            continue
        print(f"  {k:30s} {v:.5f}" if isinstance(v, float) else f"  {k:30s} {v}")
print("\nH4 per event (resolution overnight window):")
print(D[["exposed", "control", "diff", "shutdown"]].round(4).to_string())
