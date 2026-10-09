#!/usr/bin/env python3
"""Compara mai multe familii de strategii pe date reale, cu cost si impartire antrenare/test."""
import itertools
import sys

import numpy as np
import pandas as pd

import oilbot

COST_PCT = 0.06  # spread + comision estimat pe tranzactie (% din pret)


def run(ind, sig, sl_m, tp_m, max_bars, lo_i, hi_i):
    hi, lo, cl, at = (ind[k].to_numpy() for k in ("high", "low", "close", "atr"))
    out, i = [], max(lo_i, 210)
    while i < hi_i - 1:
        side = int(sig[i])
        if side == 0:
            i += 1
            continue
        e = cl[i]
        sl, tp = e - side * sl_m * at[i], e + side * tp_m * at[i]
        end = min(i + max_bars, hi_i - 1)
        px, j = cl[end], end
        for k in range(i + 1, end + 1):
            if (lo[k] <= sl) if side == 1 else (hi[k] >= sl):
                px, j = sl, k
                break
            if (hi[k] >= tp) if side == 1 else (lo[k] <= tp):
                px, j = tp, k
                break
        out.append(side * (px / e - 1) * 100 - COST_PCT)
        i = j + 1
    return np.array(out)


def pf(p):
    if len(p) == 0:
        return 0.0
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    return g / l if l else 9.9


def strategies(ind):
    c, h, l, r = ind["close"], ind["high"], ind["low"], ind["rsi"]
    e50, e200 = oilbot.ema(c, 50), ind["ema200"]
    up, dn = e50 > e200, e50 < e200
    S = {}
    for n in (24, 48, 96):  # breakout Donchian in directia trendului
        hh, ll = h.rolling(n).max().shift(), l.rolling(n).min().shift()
        S[f"breakout{n}+trend"] = pd.Series(np.where((c > hh) & up, 1, np.where((c < ll) & dn, -1, 0)), index=c.index)
        S[f"breakout{n}"] = pd.Series(np.where(c > hh, 1, np.where(c < ll, -1, 0)), index=c.index)
    for lo_, hi_ in ((30, 70), (25, 75), (20, 80)):  # mean reversion
        S[f"revert_rsi{lo_}"] = pd.Series(np.where(r < lo_, 1, np.where(r > hi_, -1, 0)), index=c.index)
    for lo_ in (35, 40, 45):  # pullback in trend
        S[f"pullback{lo_}"] = pd.Series(np.where(up & (r.shift() < lo_) & (r >= lo_), 1,
                                      np.where(dn & (r.shift() > 100 - lo_) & (r <= 100 - lo_), -1, 0)), index=c.index)
    macd = oilbot.ema(c, 12) - oilbot.ema(c, 26)
    hist = macd - oilbot.ema(macd, 9)
    S["macd_cross+trend"] = pd.Series(np.where(up & (hist > 0) & (hist.shift() <= 0), 1,
                                      np.where(dn & (hist < 0) & (hist.shift() >= 0), -1, 0)), index=c.index)
    return S


def main():
    data = {}
    for name, sym in {"WTI": "CL=F", "Brent": "BZ=F"}.items():
        data[name] = oilbot.build(oilbot.fetch_ohlc(sym, "1h", "730d"))
    rows = []
    for sname in strategies(next(iter(data.values()))):
        for sl_m, tp_m, mb in itertools.product((1.0, 1.5, 2.5), (1.5, 2.5, 4.0), (48, 120)):
            res, ok = [], True
            for nm, ind in data.items():
                sig = strategies(ind)[sname].to_numpy()
                half = len(ind) // 2
                a = run(ind, sig, sl_m, tp_m, mb, 0, half)
                b = run(ind, sig, sl_m, tp_m, mb, half, len(ind))
                res.append((nm, a, b))
            tr = np.concatenate([x[1] for x in res])
            te = np.concatenate([x[2] for x in res])
            n = len(tr) + len(te)
            if n < 60:
                continue
            rows.append((min(pf(tr), pf(te)), sname, sl_m, tp_m, mb, len(tr), pf(tr), len(te), pf(te),
                         te.sum() if len(te) else 0, {x[0]: round(pf(np.concatenate([x[1], x[2]])), 2) for x in res}))
    rows.sort(key=lambda x: -x[0])
    print("min(PF) strategie SL TP maxh | antrenare n/PF | test n/PF | total test % | PF pe simbol")
    for r in rows[:25]:
        print(f"{r[0]:.2f} {r[1]} SL{r[2]} TP{r[3]} {r[4]}h | {r[5]}/{r[6]:.2f} | {r[7]}/{r[8]:.2f} | {r[9]:+.1f}% | {r[10]}")
    print("\nMedie pe strategie (toate setarile):")
    df = pd.DataFrame([(r[1], r[0]) for r in rows], columns=["s", "minpf"])
    print(df.groupby("s")["minpf"].agg(["mean", "max"]).sort_values("mean", ascending=False).round(2).to_string())


if __name__ == "__main__":
    sys.exit(main())
