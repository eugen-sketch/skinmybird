#!/usr/bin/env python3
"""Cauta strategii robuste pe forex + aur: antrenare/test separate, cost inclus, comparatie cu semnale aleatoare."""
import itertools

import numpy as np

import sim
import strategies
import ta

INSTR = {  # nume: (simbol Yahoo, cost estimat dus-intors in % din pret: spread + alunecare)
    "EURUSD": ("EURUSD=X", 0.012), "GBPUSD": ("GBPUSD=X", 0.018), "USDJPY": ("USDJPY=X", 0.018),
    "AUDUSD": ("AUDUSD=X", 0.022), "USDCAD": ("USDCAD=X", 0.022), "USDCHF": ("USDCHF=X", 0.025),
    "NZDUSD": ("NZDUSD=X", 0.030), "GOLD": ("GC=F", 0.040),
}
GRID = list(itertools.product((1.0, 1.5, 2.0), (1.0, 1.5, 2.5), (12, 24, 48)))  # SL x ATR, TP x ATR, ore max


def load():
    data = {}
    for name, (sym, cost) in INSTR.items():
        try:
            df = ta.fetch_ohlc(sym, "1h", "730d")
            if len(df) > 2000:
                data[name] = (df, cost)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {name}: {e}")
    return data


def evaluate(data, sigs, name, sl, tp, mb):
    tr, te, per = [], [], {}
    for nm, (df, cost) in data.items():
        P = data_P[nm]
        s = sigs[nm][name]
        h = len(df) // 2
        a = [t[2] for t in sim.simulate(P, s, sl, tp, mb, 0, h, cost)]
        b = [t[2] for t in sim.simulate(P, s, sl, tp, mb, h, len(df), cost)]
        tr += a
        te += b
        per[nm] = round(sim.pf(a + b), 2)
    return np.array(tr), np.array(te), per


def main():
    global data_P
    data = load()
    print("Instrumente:", {k: len(v[0]) for k, v in data.items()})
    data_P = {nm: sim.prep(df) for nm, (df, _) in data.items()}
    sigs = {nm: {k: v.to_numpy() for k, v in strategies.all_signals(df).items()} for nm, (df, _) in data.items()}
    names = list(next(iter(sigs.values())))
    rows = []
    for name in names:
        for sl, tp, mb in GRID:
            tr, te, per = evaluate(data, sigs, name, sl, tp, mb)
            if len(tr) < 60 or len(te) < 60:
                continue
            allp = np.concatenate([tr, te])
            rows.append((min(sim.pf(tr), sim.pf(te)), name, sl, tp, mb, len(allp), (allp > 0).mean() * 100,
                         sim.pf(tr), sim.pf(te), te.sum(), sum(v > 1 for v in per.values()), len(per)))
    rows.sort(key=lambda r: -r[0])
    print("minPF strategie SL TP maxh | n | castig% | PF antrenare | PF test | total test % | instrumente cu PF>1")
    for r in rows[:30]:
        print(f"{r[0]:.2f} {r[1]} SL{r[2]} TP{r[3]} {r[4]}h | {r[5]} | {r[6]:.0f}% | {r[7]:.2f} | {r[8]:.2f} | {r[9]:+.1f}% | {r[10]}/{r[11]}")
    print("\nMedia minPF pe strategie:")
    import pandas as pd
    df_ = pd.DataFrame([(r[1], r[0]) for r in rows], columns=["s", "m"])
    print(df_.groupby("s")["m"].agg(["mean", "max"]).sort_values("mean", ascending=False).round(2).to_string())
    # referinta: semnale aleatoare cu aceeasi frecventa medie
    rng = np.random.default_rng(0)
    best = []
    for _ in range(15):
        res = []
        for sl, tp, mb in GRID:
            tr, te = [], []
            for nm, (df, cost) in data.items():
                s = ((rng.random(len(df)) < 0.01) * rng.choice([-1, 1], len(df))).astype(int)
                h = len(df) // 2
                tr += [t[2] for t in sim.simulate(data_P[nm], s, sl, tp, mb, 0, h, cost)]
                te += [t[2] for t in sim.simulate(data_P[nm], s, sl, tp, mb, h, len(df), cost)]
            res.append(min(sim.pf(tr), sim.pf(te)))
        best.append(max(res))
    print(f"\nSemnale ALEATOARE (noroc): cel mai bun minPF din {len(GRID)} setari = {np.mean(best):.2f} medie, {np.max(best):.2f} max")
    print(f"Total combinatii testate: {len(rows)}")


if __name__ == "__main__":
    main()
