#!/usr/bin/env python3
"""Verificare riguroasa pe petrol (WTI+Brent): stabilitate pe jumatati si pe trimestre."""
import itertools

import numpy as np

import sim
import ta

COST = 0.06


def main():
    data = {}
    for n, s in {"WTI": "CL=F", "BRENT": "BZ=F"}.items():
        df = ta.fetch_ohlc(s, "1h", "730d")
        data[n] = (df, sim.prep(df))
    rows = []
    for ext, (sl, tp, mb) in itertools.product((15, 20, 25), itertools.product((1.5, 2.5, 3.5), (1.0, 1.5, 2.5), (24, 48))):
        halves, quarters, allp = [[], []], [[] for _ in range(4)], []
        for n, (df, P) in data.items():
            r = ta.rsi(df["close"], 14)
            s = np.where(r < ext, 1, np.where(r > 100 - ext, -1, 0))
            L = len(df)
            for t in sim.simulate(P, s, sl, tp, mb, 0, L, COST):
                pos = t[0] / L
                halves[int(pos >= 0.5)].append(t[2])
                quarters[min(int(pos * 4), 3)].append(t[2])
                allp.append(t[2])
        if len(allp) < 60:
            continue
        rows.append((min(sim.pf(h) for h in halves), ext, sl, tp, mb, len(allp), (np.array(allp) > 0).mean() * 100,
                     [round(sim.pf(h), 2) for h in halves], [round(sim.pf(q), 2) for q in quarters], sum(allp)))
    rows.sort(key=lambda r: -r[0])
    print("minPF_jumatati | RSI SL TP ore | n | win% | PF jumatati | PF trimestre | total %")
    for r in rows[:15]:
        print(f"{r[0]:.2f} RSI{r[1]} SL{r[2]} TP{r[3]} {r[4]}h | {r[5]} | {r[6]:.0f}% | {r[7]} | {r[8]} | {r[9]:+.1f}%")
    print(f"combinatii: {len(rows)}; cu minPF>1.1: {sum(r[0] > 1.1 for r in rows)}")


if __name__ == "__main__":
    main()
