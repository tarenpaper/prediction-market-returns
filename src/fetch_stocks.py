"""Daily OHLC (auto_adjust=False so Open/Close are raw and consistent; Adj Close kept) from 2022-01-01."""
import yfinance as yf, yaml, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
T = ["CACI","SAIC","LDOS","BAH","PSN","ACN","EPAM","CTSH","SPY"]
raw = yf.download(T, start="2022-01-01", auto_adjust=False, progress=False, group_by="ticker", threads=False)
long = pd.concat({t: raw[t] for t in T}, names=["ticker","Date"]).reset_index()
long.to_csv(ROOT/"data"/"raw"/"stocks_daily_raw.csv", index=False)
long.dropna(subset=["Open","Close"]).to_csv(ROOT/"data"/"processed"/"stocks_daily.csv", index=False)
print(long.groupby("ticker").agg(rows=("Close","size"), first=("Date","min"), last=("Date","max"), nan_open=("Open", lambda s: s.isna().sum())))
