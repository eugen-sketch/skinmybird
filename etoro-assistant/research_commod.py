#!/usr/bin/env python3
"""Revenire din extreme (RSI) pe commodities/indici/forex, cu intrare la deschiderea barei urmatoare si costuri."""
import itertools

import numpy as np
import pandas as pd

import sim
import ta

INSTR = {  # nume: (simbol Yahoo, cost dus-intors %)
    "WTI": ("CL=F", 0.06), "BRENT": ("BZ=F", 0.06), "NATGAS": ("NG=F", 0.15), "GOLD": ("GC=F", 0.04),
    "SILVER": ("SI=F", 0.08), "COPPER": ("HG=F", 0.08), "SP500": ("ES=F", 0.03), "NASDAQ": ("NQ=F", 0.04),
    "EURUSD": ("EURUSD=X", 0.012), "GBPUSD": ("GBPUSD=X", 0.018), "USDJPY": ("USDJPY=X", 0.018),
}
GRID = list(itertools.product((1.5, 2.5, 3.5), (1.0, 1.5, 2.5), (24, 48)))  # SL, TP (x ATR), ore


def signal(df, kind, ext):
    r = ta.rsi(df["close"], 14 if kind == "rsi14" else 2)
    return np.where(r < ext, 1, np.where(r > 100 - ext, -1, 0))


def main():
    data = {}
    for n, (s, cost) in INSTR.items():
        try:
            df = ta.fetch_ohlc(s, "1h", "730d")
            if len(df) > 2000:
                data[n] = (df, cost, sim.prep(df))
        except Exception as e:  # noqa: BLE001
            print(f"[!] {n}: {e}")
    print({k: len(v[0]) for k, v in data.items()})
    variants = [("rsi14", e) for e in (15, 20, 25)] + [("rsi2", e) for e in (3, 5)]
    sigs = {(k, e): {n: signal(d[0], k, e) for n, d in data.items()} for k, e in variants}

    def run(kind_ext, sl, tp, mb, names):
        tr, te, per = [], [], {}
        for n in names:
            df, cost, P = data[n]
            s = sigs[kind_ext][n]
            h = len(df) // 2
            a = [t[2] for t in sim.simulate(P, s, sl, tp, mb, 0, h, cost)]
            b = [t[2] for t in sim.simulate(P, s, sl, tp, mb, h, len(df), cost)]
            tr += a
            te += b
            per[n] = (len(a) + len(b), round(sim.pf(a), 2), round(sim.pf(b), 2))
        return np.array(tr), np.array(te), per

    allnames = list(data)
    rows = []
    for ke in variants:
        for sl, tp, mb in GRID:
            tr, te, per = run(ke, sl, tp, mb, allnames)
            if len(tr) < 50 or len(te) < 50:
                continue
            good = sum(1 for v in per.values() if v[1] > 1 and v[2] > 1)
            rows.append((min(sim.pf(tr), sim.pf(te)), ke, sl, tp, mb, len(tr) + len(te), sim.pf(tr), sim.pf(te), good, per))
    rows.sort(key=lambda r: -r[0])
    print("minPF | variante | n | PF antrenare | PF test | active cu PF>1 in AMBELE jumatati")
    for r in rows[:12]:
        print(f"{r[0]:.2f} {r[1]} SL{r[2]} TP{r[3]} {r[4]}h | {r[5]} | {r[6]:.2f} | {r[7]:.2f} | {r[8]}/{len(allnames)}")
    best = rows[0]
    print("\nCel mai bun setup, pe fiecare activ (n, PF antrenare, PF test):")
    for n, v in best[9].items():
        print(f"  {n}: {v}")
    # robustete: acelasi setup pe un singur activ, pe ani
    print("\nSetup-uri cu cele mai multe active bune:")
    for r in sorted(rows, key=lambda r: (-r[8], -r[0]))[:8]:
        print(f"  {r[8]}/{len(allnames)} {r[1]} SL{r[2]} TP{r[3]} {r[4]}h minPF {r[0]:.2f} n={r[5]}")
    rng = np.random.default_rng(0)
    base = []
    for _ in range(10):
        res = []
        for sl, tp, mb in GRID:
            tr, te = [], []
            for n, (df, cost, P) in data.items():
                s = ((rng.random(len(df)) < 0.01) * rng.choice([-1, 1], len(df))).astype(int)
                h = len(df) // 2
                tr += [t[2] for t in sim.simulate(P, s, sl, tp, mb, 0, h, cost)]
                te += [t[2] for t in sim.simulate(P, s, sl, tp, mb, h, len(df), cost)]
            res.append(min(sim.pf(tr), sim.pf(te)))
        base.append(max(res))
    print(f"\nNoroc (semnale aleatoare): cel mai bun minPF = {np.mean(base):.2f} medie, {np.max(base):.2f} max; combinatii: {len(rows)}")


if __name__ == "__main__":
    main()
