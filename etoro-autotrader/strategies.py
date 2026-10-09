"""Familii de strategii. Fiecare returneaza serie +1 (BUY) / -1 (SELL) / 0, evaluata la inchiderea barei."""
from __future__ import annotations

import numpy as np
import pandas as pd

import ta


def _s(arr, idx):
    return pd.Series(np.asarray(arr, dtype=int), index=idx)


def all_signals(df: pd.DataFrame) -> dict[str, pd.Series]:
    c, h, l = df["close"], df["high"], df["low"]
    idx = df.index
    e50, e200 = ta.ema(c, 50), ta.ema(c, 200)
    up, dn = e50 > e200, e50 < e200
    r14, r2 = ta.rsi(c, 14), ta.rsi(c, 2)
    adx = ta.adx(df)
    S: dict[str, pd.Series] = {}

    for ext in (20, 25, 30):
        S[f"rsi_rev{ext}"] = _s(np.where(r14 < ext, 1, np.where(r14 > 100 - ext, -1, 0)), idx)
    for ext in (5, 10):
        S[f"rsi2_trend{ext}"] = _s(np.where((r2 < ext) & (c > e200), 1, np.where((r2 > 100 - ext) & (c < e200), -1, 0)), idx)
        S[f"rsi2_rev{ext}"] = _s(np.where(r2 < ext, 1, np.where(r2 > 100 - ext, -1, 0)), idx)
    for n in (24, 48, 96):
        hh, ll = h.rolling(n).max().shift(), l.rolling(n).min().shift()
        S[f"donchian{n}_trend"] = _s(np.where((c > hh) & up, 1, np.where((c < ll) & dn, -1, 0)), idx)
    for lo in (35, 40, 45):
        S[f"pullback{lo}"] = _s(np.where(up & (r14.shift() < lo) & (r14 >= lo), 1,
                                         np.where(dn & (r14.shift() > 100 - lo) & (r14 <= 100 - lo), -1, 0)), idx)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    for k in (2.0, 2.5):
        S[f"boll{k}_range"] = _s(np.where((c < mid - k * sd) & (adx < 25), 1, np.where((c > mid + k * sd) & (adx < 25), -1, 0)), idx)
    macd = ta.ema(c, 12) - ta.ema(c, 26)
    hist = macd - ta.ema(macd, 9)
    S["macd_trend"] = _s(np.where(up & (hist > 0) & (hist.shift() <= 0), 1, np.where(dn & (hist < 0) & (hist.shift() >= 0), -1, 0)), idx)

    # London breakout: spargerea intervalului asiatic (00-07 UTC) in orele 07-11, o data pe zi
    d = df.index.normalize()
    asia = df.between_time("00:00", "06:59")
    ah = asia["high"].groupby(asia.index.normalize()).max().reindex(d).to_numpy()
    al = asia["low"].groupby(asia.index.normalize()).min().reindex(d).to_numpy()
    hour = df.index.hour
    inwin = (hour >= 7) & (hour <= 10)
    raw = np.where(inwin & (c.to_numpy() > ah), 1, np.where(inwin & (c.to_numpy() < al), -1, 0))
    # pastram doar primul semnal al zilei
    seen = (pd.Series(raw != 0, index=idx).groupby(d).cumsum() == 1) & (raw != 0)
    S["london_breakout"] = _s(np.where(seen, raw, 0), idx)
    return S
