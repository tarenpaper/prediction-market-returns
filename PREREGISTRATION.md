# Pre-registration: shutdown-risk prediction markets and federal-contractor returns

Written 2026-10-05, before any stock return, abnormal return, or market-price-vs-return relationship was computed.
Frozen by git commit (hash recorded in the commit message of this file). Later changes go in **Deviations** at the bottom,
dated, never by editing the text above.

## 0. What I had seen before writing this (disclosure)
- Contract metadata, resolutions and venue disagreements (`data/processed/events.csv`).
- Hourly market data: row counts, date ranges, median Kalshi spread, a single candle's schema. No price paths plotted.
- Stock data: downloaded, row counts and NaN counts only. **No returns computed.**
- Exposure: 10-K federal shares and USAspending DHS shares (`data/processed/exposure_updated.csv`).
- Known from outside the data: which deadlines ended in shutdowns (E10, E11, E12), and the broad direction one would expect.

## 1. Research question
Do overnight changes in prediction-market shutdown probability predict overnight returns of federal contractors, and
is the sensitivity larger for firms with more federal (H1) and more DHS (H2) exposure?

## 2. Universe
- Exposed: CACI, SAIC, LDOS, BAH, PSN. Controls: ACN, EPAM, CTSH. Market: SPY. (Earlier draft names in config.yaml
  - PLTR, GEO, CXW, AXON, BWXT - are dropped; no data was pulled for them.)
- Data: `stocks_daily.csv` (raw, unadjusted Open/Close). The 2026-10-05 row is partial and is excluded everywhere.

## 3. Events
- 13 deadlines E01-E13 in `events.csv`. `lapse_start` (first calendar day, 00:00 ET, on which funding would lapse) is the
  event clock. The `deadline` column mixes conventions and is not used in analysis.
- **Shutdown outcome** = Kalshi's OPM-based resolution: shutdown for E10, E11, E12; averted for all others. Polymarket's
  broader "funding lapse" wording disagrees on E06, E07, E08, E09 (Yes) and E12 (No); those disagreements are reported, not used to relabel.
- **E08 is excluded from primary tests** (no deadline-specific contract on either venue, only annual contracts).
- **Cluster rule:** E03-E07 (Jan-Mar 2024 staggered CRs) form one cluster; every other event is its own cluster. 8 clusters in total (E01, E02, [E03-E07], E09, E10, E11, E12, E13 = 8; E08 excluded).

## 4. Prediction-market series
- Primary: Kalshi primary-role contract per event, price = mean of yes bid close and yes ask close from hourly candles.
  Polymarket yes-token price is a robustness series only (never averaged in).
- **Snapshots (America/New_York, DST-aware):** 16:00 and 09:30 each trading day. Value = last hourly observation at or before the
  snapshot time, carried forward at most 12 hours; otherwise missing. Drop a snapshot if Kalshi yes spread > 0.10.
  (The 09:30 snapshot is therefore effectively the 09:00 hourly observation.)
- Windows: **overnight** = 16:00(t-1) to 09:30(t), with Friday close to Monday open and holidays handled the same way;
  **intraday** = 09:30(t) to 16:00(t). dP_w = P(end) - P(start) in probability points (0-1).
- **Pre-resolution rule:** a window enters the dP regressions only if its end time is at or before `lapse_start` 00:00 ET, and
  its start is on or after max(contract open, lapse_start - 30 calendar days). Windows ending after `lapse_start` are the
  "resolution windows" (section 7).

## 5. Returns
- Overnight return = Open(t)/Close(t-1) - 1; intraday = Close(t)/Open(t) - 1; same for SPY.
- Abnormal return AR = r_i - beta_i * r_SPY with beta_i estimated by OLS on the same window type (overnight or intraday) over the
  250 trading days ending 30 trading days before the event's first window; no intercept adjustment beyond that.
  Betas are fixed per event, never re-fit on the event window.
- Raw (unadjusted) return versions are reported alongside.

## 6. Exposure measures (fixed now)
- FedShare_i = `federal_share` in `exposure_updated.csv` (EPAM, CTSH set to 0; PSN's 51% is a segment proxy and is kept as is).
- DHSShare_i = `dhs_share_fy22_25` (USAspending DHS / all-agency prime contract obligations, FY2022-25 pooled; FY2026 not
  used because it overlaps the DHS shutdown). EPAM = 0.
- Known limits: prime awards only; PSN's near-zero DHS share may understate subcontract exposure. No robustness
  alternative is pre-registered for exposure.

## 7. Hypotheses and tests
**Primary (H1), overnight windows, pre-resolution:**
AR_ijt = a_j + b * dP_jt * FedShare_i + e_ijt, pooled over firms i (8), events j (E01-E07, E09-E13), windows t.
Prediction: **b < 0** (rising shutdown probability lowers returns more for more federal firms). Two-sided test at 5%.
Standard errors: wild cluster bootstrap-t (Rademacher, 9,999 draws), clusters per section 3; also report CR1 cluster-robust SE.

**Secondary (Holm-adjusted across these three):**
- H2 (DHS): in E11-E13 pre-resolution overnight windows, AR_ijt = a_j + b1*dP*FedShare + b2*dP*DHSShare + e; prediction b2 < 0. Only 3 clusters, so bootstrap p-values are not meaningful: H2 is judged by the sign and size of b2 with
  a permutation test (shuffle dP across windows within event, 9,999 draws) and is described as low-power.
- H3 (intraday): H1 repeated on intraday windows. No directional claim beyond b < 0.
- H4 (resolution day): for the overnight window containing `lapse_start`, mean AR of exposed minus controls, split by
  Kalshi outcome (shutdown vs averted). Prediction: exposed-minus-control is lower for shutdown events. Descriptive, n = 3 vs 9.

**Exploratory (labelled as such, not tested for significance):** Polymarket-based version of H1; drop-the-2024-cluster version;
cumulative abnormal return of the 8 firms from `2026-02-13` to `2026-04-30` plotted against DHSShare (n = 8, descriptive only);
duration-contract analysis (`contracts_duration.csv`; many opened after the shutdown began, so lead-up use is limited).

## 8. Placebos
- Same regression using next-window dP (lead) in place of contemporaneous dP.
- Same regression on dates outside all event windows with the nearest event's contract, to check for mechanical correlation.

## 9. What would count as a negative result
H1's b is not significantly below zero on the primary specification. I will report that as the result and will not
change windows, snapshots, exposure measures or the control group to recover it.

## 10. Rules for deviations
Any change to data handling after this commit (including bug fixes that change the sample) is logged below with date, reason,
and the number of observations affected. Results are reported for the pre-registered specification first.

## Deviations
No deviations from the registered design. Implementation clarifications made on 2026-10-07 while writing `src/build_panel.py`,
before any dP-return relationship was examined (only window counts, dP distributions, return sanity and betas were inspected):
1. Betas are estimated with an intercept; AR = r - beta * r_SPY does not subtract the intercept (section 5, "no intercept adjustment").
2. "Contract open" in the 30-day rule is the timestamp of the contract's first hourly observation, not the metadata date.
3. Only `role == primary` contracts enter the panel. This means E08 (annual proxies) is absent from the panel altogether, and
   Polymarket `secondary` / `related` contracts are not used.
4. The 12-hour carry-forward limit is applied to each snapshot independently; a window needs both snapshots non-missing.
5. Resolution windows (the overnight window containing `lapse_start`) are generated for every event regardless of whether dP is
   available there, since H4 uses returns only.
6. The 2024 cluster's overlapping contracts pair the same stock window with several events' dP; event fixed effects and the
   cluster rule in section 3 handle this, and it is flagged here so the effective sample is not overstated.
7. Returns follow section 5 literally: raw (unadjusted) Open/Close. A dividend-adjusted column (`ret_adj`) is stored for robustness only.

## Results log (appended 2026-10-07; nothing above this line was changed)
Registered tests, run as specified (`src/h1.py`, `src/secondary.py`; outputs `h1_results.json`, `secondary_results.json`):
- H1 (overnight, Fed share): b = -0.0035, CR1 se 0.0046, wild-cluster-bootstrap p = 0.47. Not supported.
- H2 (DHS, E11-E13): b2 = +0.120 (wrong sign), permutation p = 0.24, Holm p = 0.71. Not supported.
- H3 (intraday, Fed share): b = +0.0104 (wrong sign), bootstrap p = 0.76, Holm p = 1.00. Not supported.
- H4 (resolution window, exposed minus control, shutdown n = 3 vs averted n = 9): difference in means = +0.0014 (wrong sign),
  exact permutation p = 1.00. Not supported.

Observed after the registered H4 result, then examined: the two largest per-event differences are E13 (2026-10-01; ACN +17.8%,
EPAM +8.4%, CTSH +7.8% overnight on heavy volume) and E09 (2025-03-17; SAIC +12.5%). Neither coincides with a funding outcome.
**Post-hoc and exploratory, not part of the registered inference, not Holm-adjusted:** excluding E09 and E13 gives
shutdown-minus-averted = -0.0052, exact permutation p = 0.008 (n = 3 vs 7); medians on all 12 events give -0.0059, p = 0.082.
The exclusion was chosen after seeing the registered result, so these figures are hypothesis-generating only.
