#!/usr/bin/env python3
"""Scalping forex: tinta fixa in % (=2.5$ / 3.5$ la expunere ~1400$), semnale combinate, antrenare/test, comparatie cu noroc."""
import itertools

import numpy as np

import sim
import strategies
import ta

PAIRS = {"EURUSD": 0.012, "GBPUSD": 0.018, "USDJPY": 0.018, "AUDUSD": 0.022, "USDCAD": 0.022, "USDCHF": 0.025, "NZDUSD": 0.030}
EXPO = 1400.0  # 3 ordine din 140$, levier 30
TPS = [("2.5$", 2.5), ("3.0$", 3.0), ("3.5$", 3.5), ("4.0$", 4.0)]
SLS = [("2$", 2.0), ("3.5$", 3.5), ("5$", 5.0)]
MBS = (6, 12, 24)


def comb(S, names):
    arr = np.zeros(len(next(iter(S.values()))), dtype=int)
    pos = sum((S[n].to_numpy() == 1).astype(int) for n in names)
    neg = sum((S[n].to_numpy() == -1).astype(int) for n in names)
    arr[(pos > 0) & (neg == 0)] = 1
    arr[(neg > 0) & (pos == 0)] = -1
    return arr


def main():
    data = {}
    for n, cost in PAIRS.items():
        try:
            df = ta.fetch_ohlc(f"{n}=X", "1h", "730d")
            if len(df) > 2000:
                data[n] = (df, cost, sim.prep(df), strategies.all_signals(df))
        except Exception as e:  # noqa: BLE001
            print(f"[!] {n}: {e}")
    print("Perechi:", {k: len(v[0]) for k, v in data.items()})
    sets = {
        "london": ["london_breakout"],
        "rsi25": ["rsi_rev25"],
        "donchian48": ["donchian48_trend"],
        "london+rsi25": ["london_breakout", "rsi_rev25"],
        "london+rsi25+donch48": ["london_breakout", "rsi_rev25", "donchian48_trend"],
        "toate_active": ["london_breakout", "rsi_rev30", "donchian24_trend", "rsi2_trend10", "boll2.0_range"],
    }
    sigs = {k: {n: comb(d[3], names) for n, d in data.items()} for k, names in sets.items()}
    days = max((d[0].index[-1] - d[0].index[0]).days for d in data.values())
    rows = []
    for k in sets:
        for (tl, tp), (sl_l, sl), mb in itertools.product(TPS, SLS, MBS):
            tr, te = [], []
            for n, (df, cost, P, _) in data.items():
                h = len(df) // 2
                s = sigs[k][n]
                tr += [t[2] for t in sim.simulate_pct(P, s, sl / EXPO * 100, tp / EXPO * 100, mb, 0, h, cost)]
                te += [t[2] for t in sim.simulate_pct(P, s, sl / EXPO * 100, tp / EXPO * 100, mb, h, len(df), cost)]
            allp = np.array(tr + te)
            if len(tr) < 100 or len(te) < 100:
                continue
            usd = allp / 100 * EXPO
            rows.append((min(sim.pf(tr), sim.pf(te)), k, tl, sl_l, mb, len(allp), len(allp) / days, (allp > 0).mean() * 100,
                         sim.pf(tr), sim.pf(te), usd.mean(), usd.sum() / (days / 30)))
    rows.sort(key=lambda r: -r[0])
    print("minPF | semnale | TP | SL | max ore | n | tranz/zi | win% | PF antren | PF test | $/tranz | $/luna (1 slot)")
    for r in rows[:25]:
        print(f"{r[0]:.2f} {r[1]} TP{r[2]} SL{r[3]} {r[4]}h | {r[5]} | {r[6]:.1f}/zi | {r[7]:.0f}% | {r[8]:.2f} | {r[9]:.2f} | {r[10]:+.2f}$ | {r[11]:+.0f}$/luna")
    print("\nCele mai bune per set de semnale:")
    best = {}
    for r in rows:
        best.setdefault(r[1], r)
    for k, r in best.items():
        print(f"  {k}: minPF {r[0]:.2f} TP{r[2]} SL{r[3]} {r[4]}h n={r[5]} win {r[7]:.0f}%")
    print("\nTinta 2.5$ vs 3.5$ (media minPF, toate setarile):")
    import pandas as pd
    d = pd.DataFrame([(r[2], r[0]) for r in rows], columns=["tp", "m"])
    print(d.groupby("tp")["m"].agg(["mean", "max"]).round(2).to_string())
    rng = np.random.default_rng(0)
    base = []
    for _ in range(8):
        res = []
        for (tl, tp), (sl_l, sl), mb in itertools.product(TPS, SLS, MBS):
            tr, te = [], []
            for n, (df, cost, P, _) in data.items():
                s = ((rng.random(len(df)) < 0.01) * rng.choice([-1, 1], len(df))).astype(int)
                h = len(df) // 2
                tr += [t[2] for t in sim.simulate_pct(P, s, sl / EXPO * 100, tp / EXPO * 100, mb, 0, h, cost)]
                te += [t[2] for t in sim.simulate_pct(P, s, sl / EXPO * 100, tp / EXPO * 100, mb, h, len(df), cost)]
            res.append(min(sim.pf(tr), sim.pf(te)))
        base.append(max(res))
    print(f"\nNoroc (semnale aleatoare): cel mai bun minPF = {np.mean(base):.2f} medie, {np.max(base):.2f} max; combinatii testate: {len(rows)}")


if __name__ == "__main__":
    main()
