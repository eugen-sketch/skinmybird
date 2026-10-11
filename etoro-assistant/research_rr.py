#!/usr/bin/env python3
"""Test: exista vreo proportie tinta/plasa (TP/SL in $) la care semnalele asistentului ies macar pe zero?

Aceleasi semnale ca in asistent, aceleasi 13 instrumente, ~2 ani de date. Ordonat dupa cel mai slab dintre
jumatatea veche (train) si cea noua (test), ca sa nu premiem norocul pe o singura jumatate."""
import itertools
import json
from pathlib import Path

import numpy as np

import sim
import strategies
import ta

EXPO = 1400.0
TPS = [2.75, 4.0, 6.0, 9.0]
SLS = [2.0, 3.0, 4.5, 6.0, 9.0]
MBS = [12, 24, 72]
cfg = json.loads((Path(__file__).parent / "config.json").read_text())


def main() -> None:
    data = {}
    for inst in cfg["instruments"]:
        try:
            df = ta.fetch_ohlc(inst["yahoo"], "1h", "730d")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {inst['name']}: {type(e).__name__}")
            continue
        if len(df) < 2000:
            continue
        S = strategies.all_signals(df)
        pos = sum((S[n].to_numpy() == 1).astype(int) for n in inst["signals"])
        neg = sum((S[n].to_numpy() == -1).astype(int) for n in inst["signals"])
        sig = np.zeros(len(df), dtype=int)
        sig[(pos > 0) & (neg == 0)] = 1
        sig[(neg > 0) & (pos == 0)] = -1
        data[inst["name"]] = (df, inst["cost"], sim.prep(df), sig)
    print("Instrumente:", len(data))
    rows = []
    for tp, sl, mb in itertools.product(TPS, SLS, MBS):
        tr, te, per = [], [], {}
        for n, (df, cost, P, sig) in data.items():
            h = len(df) // 2
            a = [t[2] / 100 * EXPO for t in sim.simulate_pct(P, sig, sl / EXPO * 100, tp / EXPO * 100, mb, 0, h, cost)]
            b = [t[2] / 100 * EXPO for t in sim.simulate_pct(P, sig, sl / EXPO * 100, tp / EXPO * 100, mb, h, len(df), cost)]
            tr += a
            te += b
            per[n] = np.mean(a + b) if a + b else 0.0
        if len(tr) < 300 or len(te) < 300:
            continue
        allp = np.array(tr + te)
        rows.append((min(sim.pf(tr), sim.pf(te)), tp, sl, mb, len(allp), (allp > 0).mean() * 100, allp.mean(), sim.pf(tr), sim.pf(te),
                     sum(1 for v in per.values() if v > 0)))
    rows.sort(reverse=True)
    print("\nTop 15 (dupa cel mai slab PF dintre train/test). PF>1 inseamna ca a castigat; <1 ca a pierdut.")
    print("tinta  plasa  max_ore  tranz  castig%  medie$/tr  PF_train  PF_test  instrumente_pe_plus")
    for r in rows[:15]:
        print(f"{r[1]:5.2f}$ {r[2]:5.2f}$ {r[3]:6d} {r[4]:7d} {r[5]:7.1f} {r[6]:+9.3f} {r[7]:8.2f} {r[8]:8.2f} {r[9]:10d}/{len(data)}")
    pos = [r for r in rows if r[7] > 1 and r[8] > 1]
    print(f"\nCombinatii cu PF>1 si pe train si pe test: {len(pos)} din {len(rows)} testate.")


if __name__ == "__main__":
    main()
