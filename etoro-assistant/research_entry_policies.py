#!/usr/bin/env python3
"""Cercetare: politici de intrare pentru val / pullback, cu TP/SL reale (pe bare orare, SL primul daca ambele in aceeasi bara) si costuri.
Politici: acum (la inchiderea barii semnalului), retragere (asteapta sa se intoarca r*ATR spre noi, max 2 bare), confirmare (urmatoarea bara in sens),
invers (contra valului). Rezultat in ATR dupa costuri. Date publice de piata, fara date de cont."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import signals
import strategies
import ta

cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
RNG = sys.argv[1] if len(sys.argv) > 1 else "365d"
HOLD = 6                         # ore maxim cat tinem o pozitie in simulare
PROFILES = {"normal": (0.75, 4.0), "agresiv": (1.1, 3.5)}


def sim(d, entry, a, hi, lo, tp_k, sl_k, start):
    """Rezultat in ATR (inainte de costuri) pentru o intrare la `entry` incepand cu bara `start`."""
    tp, sl = entry + d * tp_k * a, entry - d * sl_k * a
    for j in range(start, min(start + HOLD, len(hi))):
        hit_sl = (lo[j] <= sl) if d == 1 else (hi[j] >= sl)
        hit_tp = (hi[j] >= tp) if d == 1 else (lo[j] <= tp)
        if hit_sl:
            return -sl_k
        if hit_tp:
            return tp_k
    return None


def run():
    out = []
    for inst in cfg["instruments"]:
        try:
            df = signals.completed(ta.fetch_ohlc(inst["yahoo"], "1h", RNG))
        except Exception as ex:  # noqa: BLE001
            print("skip", inst["name"], type(ex).__name__)
            continue
        c, h, l = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
        atr = ta.atr(df).to_numpy()
        e50, e200 = ta.ema(df["close"], 50).to_numpy(), ta.ema(df["close"], 200).to_numpy()
        rsi = ta.rsi(df["close"], 14).to_numpy()
        S = strategies.all_signals(df)
        pb = S["pullback50"].to_numpy()
        n = len(df)
        cost_pct = inst["cost"] / 100.0
        last_wave = -99
        for t in range(250, n - HOLD - 3):
            a = atr[t]
            if not a > 0:
                continue
            cost = cost_pct * c[t] / a                              # cost dus-intors in ATR
            ev = []
            mv = (c[t] - c[t - 3]) / a
            trend = "sus" if (e50[t] > e200[t] and c[t] > e50[t]) else "jos" if (e50[t] < e200[t] and c[t] < e50[t]) else "lateral"
            if abs(mv) >= 1.3 and t - last_wave >= 3:
                d = 1 if mv > 0 else -1
                last_wave = t
                ok = not ((trend == "jos" and d == 1) or (trend == "sus" and d == -1)) and (d * (c[t] - c[t - 1]) > -0.3 * a)
                ok = ok and not ((d == 1 and rsi[t] > 90) or (d == -1 and rsi[t] < 10))
                if ok:
                    ev.append(("val", d))
            if pb[t] != 0 and pb[t] != pb[t - 1]:
                ev.append(("pullback50", int(pb[t])))
            for name, d in ev:
                for prof, (tpk, slk) in PROFILES.items():
                    res = {}
                    r = sim(d, c[t], a, h, l, tpk, slk, t + 1)
                    res["acum"] = None if r is None else r - cost
                    if r is None:                                      # nicio atingere in HOLD ore: inchidem la piata
                        res["acum"] = d * (c[min(t + HOLD, n - 1)] - c[t]) / a - cost
                    for rr in (0.25, 0.5, 0.75):                       # retragere spre noi, max 2 bare
                        lvl = c[t] - d * rr * a
                        filled = None
                        for j in (t + 1, t + 2):
                            if (l[j] <= lvl) if d == 1 else (h[j] >= lvl):
                                filled = j
                                break
                        if filled is None:
                            res[f"retragere {rr}"] = None
                            continue
                        r2 = sim(d, lvl, a, h, l, tpk, slk, filled + 1)
                        if r2 is None:
                            r2 = d * (c[min(filled + HOLD, n - 1)] - lvl) / a
                        res[f"retragere {rr}"] = r2 - cost
                    # confirmare: urmatoarea bara inchide in sens (>0.2 ATR); intrare la inchiderea ei
                    if d * (c[t + 1] - c[t]) > 0.2 * a:
                        r3 = sim(d, c[t + 1], a, h, l, tpk, slk, t + 2)
                        if r3 is None:
                            r3 = d * (c[min(t + 1 + HOLD, n - 1)] - c[t + 1]) / a
                        res["confirmare"] = r3 - cost
                    else:
                        res["confirmare"] = None
                    r4 = sim(-d, c[t], a, h, l, tpk, slk, t + 1)       # contra valului, aceleasi TP/SL
                    if r4 is None:
                        r4 = -d * (c[min(t + HOLD, n - 1)] - c[t]) / a
                    res["invers"] = r4 - cost
                    for pol, v in res.items():
                        out.append({"sig": name, "prof": prof, "pol": pol, "r": v, "inst": inst["name"], "cost": cost})
    return pd.DataFrame(out)


R = run()
print("rânduri:", len(R))
print("\nRezultat mediu pe tranzactie, in ATR, DUPA costuri (n = tranzactii efectuate; 'umplere' = cat din semnale se executa)\n")
for (sig, prof), d in R.groupby(["sig", "prof"]):
    base_n = len(d[d.pol == "acum"])
    print(f"--- {sig} / profil {prof}  (semnale: {base_n}, cost mediu dus-intors: {d[d.pol == 'acum'].cost.mean():.2f} ATR)")
    for pol in ["acum", "retragere 0.25", "retragere 0.5", "retragere 0.75", "confirmare", "invers"]:
        x = d[d.pol == pol]["r"].dropna()
        if len(x) < 20:
            print(f"   {pol:16s} n={len(x)}")
            continue
        print(f"   {pol:16s} n={len(x):5d} umplere={100 * len(x) / base_n:3.0f}%  mediu={x.mean():+.3f} ATR  castiguri={100 * (x > 0).mean():3.0f}%  "
              f"total={x.sum():+8.1f} ATR  pierdere medie={x[x < 0].mean():+.2f}")
print("\n--- val / profil agresiv, pe instrument (politica acum vs retragere 0.5)")
d = R[(R.sig == "val") & (R.prof == "agresiv")]
for inst, g in d.groupby("inst"):
    a1 = g[g.pol == "acum"]["r"].dropna()
    a2 = g[g.pol == "retragere 0.5"]["r"].dropna()
    print(f"   {inst:8s} acum n={len(a1):4d} {a1.mean():+.3f}   retragere0.5 n={len(a2):4d} {a2.mean() if len(a2) else float('nan'):+.3f}")
