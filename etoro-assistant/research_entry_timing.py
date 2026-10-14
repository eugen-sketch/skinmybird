#!/usr/bin/env python3
"""Cercetare: cat de 'tarziu' intra botul. Pentru fiecare tip de semnal (val, pullback, donchian, RSI extrem) masoara ce face pretul in urmatoarele 1-3 ore
(in unitati de ATR orar, in directia semnalului) si cum depinde de cat de intinsa e deja miscarea. Date publice de piata, fara date de cont."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import signals
import strategies
import ta

cfg = json.loads((Path(__file__).parent / "config.json").read_text())
RNG = sys.argv[1] if len(sys.argv) > 1 else "365d"


def events(df, inst_name):
    c, h, l = df["close"], df["high"], df["low"]
    atr = ta.atr(df)
    e20 = ta.ema(c, 20)
    rsi = ta.rsi(c, 14)
    S = strategies.all_signals(df)
    rows = []
    n = len(df)
    # semnale clasice (edge) + val
    sig = {k: S[k] for k in ("pullback45", "pullback50", "donchian24_trend", "rsi_rev30", "rsi_rev36", "rsi_rev25", "london_breakout") if k in S}
    last_wave = -99
    for t in range(250, n - 4):
        a = float(atr.iloc[t])
        if a <= 0:
            continue
        px = float(c.iloc[t])
        cand = []
        for k, s in sig.items():
            v, p = int(s.iloc[t]), int(s.iloc[t - 1])
            if v != 0 and v != p:
                cand.append((k, v))
        mv = (px - float(c.iloc[t - 3])) / a
        if abs(mv) >= 1.0 and t - last_wave >= 3:
            cand.append(("wave", 1 if mv > 0 else -1))
            last_wave = t
        for k, d in cand:
            fw = [d * (float(c.iloc[t + j]) - px) / a for j in (1, 2, 3)]
            hi = max(float(h.iloc[t + j]) for j in (1, 2, 3))
            lo = min(float(l.iloc[t + j]) for j in (1, 2, 3))
            mfe = (hi - px) / a if d == 1 else (px - lo) / a
            mae = (px - lo) / a if d == 1 else (hi - px) / a
            rows.append({"inst": inst_name, "sig": k, "dir": d, "fwd1": fw[0], "fwd2": fw[1], "fwd3": fw[2], "mfe": mfe, "mae": mae,
                         "last1": d * (px - float(c.iloc[t - 1])) / a, "move3": d * mv, "ext": d * (px - float(e20.iloc[t])) / a,
                         "rsi_dir": (float(rsi.iloc[t]) if d == 1 else 100 - float(rsi.iloc[t]))})
    return rows


allrows = []
for inst in cfg["instruments"]:
    try:
        df = ta.fetch_ohlc(inst["yahoo"], "1h", RNG)
        df = signals.completed(df)
        allrows += events(df, inst["name"])
    except Exception as ex:  # noqa: BLE001
        print("skip", inst["name"], type(ex).__name__)
R = pd.DataFrame(allrows)
print("evenimente:", len(R), "instrumente:", R["inst"].nunique() if len(R) else 0)


def line(name, d):
    if len(d) < 15:
        return f"{name:34s} n={len(d):4d}"
    adverse_first = float(((d["mae"] >= 0.5) & (d["mfe"] < 0.5)).mean() * 100)
    return (f"{name:34s} n={len(d):4d}  fwd1={d.fwd1.mean():+.2f} fwd2={d.fwd2.mean():+.2f} fwd3={d.fwd3.mean():+.2f} ATR  "
            f"urcat>0 la 2h: {100 * (d.fwd2 > 0).mean():3.0f}%  doar-impotriva(>=.5ATR,fara favor): {adverse_first:3.0f}%  mfe={d.mfe.mean():.2f} mae={d.mae.mean():.2f}")


print("\n== pe tip de semnal (toate) ==")
for k, d in R.groupby("sig"):
    print(line(k, d))
print("\n== VAL: dupa cat de intinsa era deja miscarea (move3 in ATR) ==")
W = R[R.sig == "wave"]
for lo, hi in ((1.0, 1.3), (1.3, 1.6), (1.6, 2.0), (2.0, 2.6), (2.6, 99)):
    print(line(f"val move3 {lo}-{hi}", W[(W.move3 >= lo) & (W.move3 < hi)]))
print("\n== VAL: dupa ultima ora (last1, in ATR) = cat de 'grabit' e urcusul ==")
for lo, hi in ((-9, 0.3), (0.3, 0.7), (0.7, 1.1), (1.1, 99)):
    print(line(f"val last1 {lo}..{hi}", W[(W.last1 >= lo) & (W.last1 < hi)]))
print("\n== VAL: dupa distanta fata de media EMA20 (ext, in ATR) ==")
for lo, hi in ((-9, 0.8), (0.8, 1.5), (1.5, 2.2), (2.2, 99)):
    print(line(f"val ext {lo}..{hi}", W[(W.ext >= lo) & (W.ext < hi)]))
print("\n== VAL: dupa RSI in directia valului ==")
for lo, hi in ((0, 60), (60, 70), (70, 80), (80, 101)):
    print(line(f"val rsi {lo}-{hi}", W[(W.rsi_dir >= lo) & (W.rsi_dir < hi)]))
print("\n== Combinatii de filtre pe VAL ==")
for nm, m in (("fara filtru", W.move3 > 0), ("ext<1.5", W.ext < 1.5), ("ext<1.5 si last1<0.8", (W.ext < 1.5) & (W.last1 < 0.8)),
              ("rsi<75", W.rsi_dir < 75), ("ext<1.5 si rsi<75", (W.ext < 1.5) & (W.rsi_dir < 75)), ("last1<0.5", W.last1 < 0.5),
              ("ext<1.0", W.ext < 1.0), ("ext<2.0 si last1<0.7 si rsi<75", (W.ext < 2.0) & (W.last1 < 0.7) & (W.rsi_dir < 75))):
    print(line("val " + nm, W[m]))
print("\n== Semnale clasice: dupa distanta fata de EMA20 (ext) ==")
C = R[R.sig.isin(["pullback45", "pullback50", "donchian24_trend", "rsi_rev30", "rsi_rev36"])]
for k, d in C.groupby("sig"):
    for nm, m in (("ext<0.8", d.ext < 0.8), ("ext>=0.8", d.ext >= 0.8), ("ext>=1.5", d.ext >= 1.5)):
        print(line(f"{k} {nm}", d[m]))
print("\n== Pe instrument (val, toate) ==")
for k, d in W.groupby("inst"):
    print(line(k, d))
