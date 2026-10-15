#!/usr/bin/env python3
"""Test intraday: intrare pe trendul orar, TP automat mic (multiplu de ATR orar) atins in 1-3 ore, SL larg (multiplu de ATR).

Indici + aur (si separat forex/petrol). Impartit in jumatatea veche (train) si noua (test); se cer 300+ tranzactii pe fiecare."""
import itertools
import json
from pathlib import Path

import numpy as np

import sim
import strategies
import ta

EXPO = 1000.0
FAMILIES = ["pullback35", "pullback40", "pullback45", "donchian24_trend", "donchian48_trend", "macd_trend"]
TPS, SLS, MBS = [0.3, 0.5, 0.75, 1.0, 1.5], [2.0, 3.0, 4.0, 6.0], [2, 3, 6]
GROUPS = {"indici+aur": ["SPX500", "NSDQ100", "DJ30", "GER40", "GOLD"],
          "forex+petrol": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "OIL"]}
cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))


def main() -> None:
    data = {}
    for inst in cfg["instruments"]:
        try:
            df = ta.fetch_ohlc(inst["yahoo"], "1h", "730d")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {inst['name']}: {type(e).__name__}")
            continue
        if len(df) >= 2000:
            data[inst["name"]] = (df, inst["cost"], sim.prep(df), strategies.all_signals(df))
    for gname, members in GROUPS.items():
        names = [n for n in members if n in data]
        rows = []
        for fam, tp, sl, mb in itertools.product(FAMILIES, TPS, SLS, MBS):
            tr, te, hit = [], [], []
            for n in names:
                df, cost, P, S = data[n]
                s, h = S[fam].to_numpy(), len(df) // 2
                a = sim.simulate(P, s, sl, tp, mb, 0, h, cost)
                b = sim.simulate(P, s, sl, tp, mb, h, len(df), cost)
                tr += [t[2] for t in a]
                te += [t[2] for t in b]
            if len(tr) < 300 or len(te) < 300:
                continue
            allp = np.array(tr + te)
            rows.append((min(sim.pf(tr), sim.pf(te)), fam, tp, sl, mb, len(allp), (allp > 0).mean() * 100, allp.mean() / 100 * EXPO,
                         sim.pf(tr), sim.pf(te)))
        rows.sort(reverse=True)
        print(f"\n=== {gname} ({len(names)} instrumente), expunere {EXPO:.0f}$ ===")
        print("familie             TP_ATR SL_ATR max_ore tranz castig% medie$/tr PF_train PF_test")
        for r in rows[:12]:
            print(f"{r[1]:18s} {r[2]:6.2f} {r[3]:6.1f} {r[4]:7d} {r[5]:5d} {r[6]:6.1f} {r[7]:+8.3f} {r[8]:8.2f} {r[9]:7.2f}")
        good = [r for r in rows if r[8] > 1 and r[9] > 1]
        print(f"PF>1 si pe train si pe test: {len(good)} din {len(rows)} combinatii")


if __name__ == "__main__":
    main()
