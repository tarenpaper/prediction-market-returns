"""H1 as registered (PREREGISTRATION.md section 7).

AR_ijt = a_j + b * dP_jt * FedShare_i + e_ijt   (overnight, pre-resolution, primary sample, Kalshi dP)
Prediction: b < 0. Two-sided test at 5%.
Inference: wild cluster bootstrap-t (restricted, Rademacher, 9,999 draws, seed 20261007) with clusters per section 3,
plus CR1 cluster-robust SE. The same regression on raw returns is reported alongside.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
from scipy import stats

P = Path(__file__).resolve().parents[1] / "data" / "processed"
B_DRAWS, SEED = 9999, 20261007

pn = pd.read_csv(P / "panel.csv", parse_dates=["day"])
d = pn[(pn.phase == "pre") & (pn.wtype == "overnight") & pn.primary_sample & pn.dP_kalshi.notna() & pn.ar.notna()].copy()
d["x"] = d.dP_kalshi * d.fed_share


def demean(v, g):
    return v - pd.Series(v).groupby(g).transform("mean").to_numpy()


def fit(y, x, ev, cl):
    """FWL: event fixed effects absorbed by demeaning. Returns b, CR1 se, residuals (unrestricted)."""
    yt, xt = demean(y, ev), demean(x, ev)
    sxx = xt @ xt
    b = (xt @ yt) / sxx
    u = yt - b * xt
    G, N, K = len(np.unique(cl)), len(y), 1 + len(np.unique(ev))
    scores = pd.Series(xt * u).groupby(cl).sum().to_numpy()
    v = (G / (G - 1)) * ((N - 1) / (N - K)) * (scores @ scores) / sxx**2
    return b, np.sqrt(v), xt, yt


def run(ycol):
    y, x = d[ycol].to_numpy(float), d.x.to_numpy(float)
    ev, cl = d.event_id.to_numpy(), d.cluster.to_numpy()
    b, se, xt, yt = fit(y, x, ev, cl)
    t = b / se
    G = len(np.unique(cl))
    p_cr1 = 2 * stats.t.sf(abs(t), G - 1)
    # restricted (b = 0) model: event means only; bootstrap y* = fitted + w_g * restricted residual
    u0 = yt                                    # residual after removing event means (demeaned y)
    fitted0 = y - u0
    rng = np.random.default_rng(SEED)
    cls = np.unique(cl); idx = {c: np.where(cl == c)[0] for c in cls}
    ts = np.empty(B_DRAWS)
    for k in range(B_DRAWS):
        w = np.empty(len(y))
        for c in cls:
            w[idx[c]] = rng.choice([-1.0, 1.0])
        ystar = fitted0 + w * u0
        bs, ses, _, _ = fit(ystar, x, ev, cl)
        ts[k] = bs / ses
    p_wcb = (np.sum(np.abs(ts) >= abs(t)) + 1) / (B_DRAWS + 1)
    return dict(dep=ycol, b=b, se_cr1=se, t=t, p_cr1_t_Gm1=p_cr1, p_wild_cluster_bootstrap=p_wcb,
                n_obs=len(y), n_clusters=G, n_events=len(np.unique(ev)), n_event_windows=int(d.drop_duplicates(["event_id", "day"]).shape[0]),
                effect_per_10pt_dP_at_fed_share_1=b * 0.10,
                ci95_cr1_low=b - stats.t.ppf(0.975, G - 1) * se, ci95_cr1_high=b + stats.t.ppf(0.975, G - 1) * se)


res = [run("ar"), run("ret")]
for r in res:
    r["registered_primary"] = r["dep"] == "ar"
(P / "h1_results.json").write_text(json.dumps(res, indent=1, default=float))
for r in res:
    print(f"\n[{'PRIMARY' if r['registered_primary'] else 'alongside'}] dep = {r['dep']}")
    for k, v in r.items():
        if k not in ("dep", "registered_primary"):
            print(f"  {k:38s} {v:.5f}" if isinstance(v, float) else f"  {k:38s} {v}")
print("\nobs by cluster:", d.groupby("cluster").size().to_dict())
