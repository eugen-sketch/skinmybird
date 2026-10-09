#!/usr/bin/env python3
"""Scalping: tinta fixa in % (≈5-10$ pe o pozitie de ~400$), iesire rapida. Antrenare/test separate."""
import itertools

import numpy as np
import pandas as pd

import oilbot
from research import COST_PCT, pf, strategies


def run_pct(ind, sig, sl_p, tp_p, max_bars, lo_i, hi_i):
    hi, lo, cl = (ind[k].to_numpy() for k in ("high", "low", "close"))
    out, i = [], max(lo_i, 210)
    while i < hi_i - 1:
        side = int(sig[i])
        if side == 0:
            i += 1
            continue
        e = cl[i]
        sl, tp = e * (1 - side * sl_p / 100), e * (1 + side * tp_p / 100)
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


def main():
    data = {n: oilbot.build(oilbot.fetch_ohlc(s, "1h", "730d")) for n, s in {"WTI": "CL=F", "Brent": "BZ=F"}.items()}
    sigs = {n: strategies(d) for n, d in data.items()}
    rows = []
    for sname in sigs["WTI"]:
        for sl_p, tp_p, mb in itertools.product((0.8, 1.2, 2.0), (1.0, 1.5, 2.2), (12, 24, 48)):
            tr, te, per = [], [], {}
            for nm, ind in data.items():
                s = sigs[nm][sname].to_numpy()
                h = len(ind) // 2
                a, b = run_pct(ind, s, sl_p, tp_p, mb, 0, h), run_pct(ind, s, sl_p, tp_p, mb, h, len(ind))
                tr.append(a), te.append(b)
                per[nm] = round(pf(np.concatenate([a, b])), 2)
            tr, te = np.concatenate(tr), np.concatenate(te)
            if len(tr) + len(te) < 80:
                continue
            allp = np.concatenate([tr, te])
            rows.append((min(pf(tr), pf(te)), sname, sl_p, tp_p, mb, len(allp), (allp > 0).mean() * 100,
                         pf(tr), pf(te), te.sum(), per))
    rows.sort(key=lambda r: -r[0])
    print("minPF strategie SL% TP% maxh | n | castig% | PF antrenare | PF test | total test % | PF/simbol")
    for r in rows[:25]:
        print(f"{r[0]:.2f} {r[1]} SL{r[2]} TP{r[3]} {r[4]}h | {r[5]} | {r[6]:.0f}% | {r[7]:.2f} | {r[8]:.2f} | {r[9]:+.1f}% | {r[10]}")
    print(f"\nTotal combinatii: {len(rows)}; cu minPF>1.15: {sum(r[0] > 1.15 for r in rows)}")
    # referinta: cat de bine ar iesi prin noroc (semnale la momente aleatoare)
    rng = np.random.default_rng(0)
    best = []
    for _ in range(30):
        pfs = []
        for sl_p, tp_p, mb in itertools.product((0.8, 1.2, 2.0), (1.0, 1.5, 2.2), (12, 24, 48)):
            tr, te = [], []
            for nm, ind in data.items():
                s = (rng.random(len(ind)) < 0.01) * rng.choice([-1, 1], len(ind))
                h = len(ind) // 2
                tr.append(run_pct(ind, s, sl_p, tp_p, mb, 0, h)), te.append(run_pct(ind, s, sl_p, tp_p, mb, h, len(ind)))
            pfs.append(min(pf(np.concatenate(tr)), pf(np.concatenate(te))))
        best.append(max(pfs))
    print(f"Semnale ALEATOARE: cel mai bun minPF din 27 setari = {np.mean(best):.2f} (medie), {np.max(best):.2f} (max) -> ce se obtine din pur noroc")


if __name__ == "__main__":
    main()
