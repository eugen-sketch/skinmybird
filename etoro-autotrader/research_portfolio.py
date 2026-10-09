#!/usr/bin/env python3
"""Simulare in DOLARI pe contul de 140$: expunere minima 1000$/pozitie, marja = expunere/levier, locuri limitate.
Raspunde la: ce se intampla in ferestre de 1 an, cate ies pe minus?"""
import sys

import numpy as np
import pandas as pd

import research_daily as rd
import ta

EQ0 = 140.0
EXPO = 1010.0
LEV = {"SP500": 20, "NASDAQ": 20, "GOLD": 20, "SILVER": 10, "OIL": 10}
CFG = {
    "SP500": ("rsi2", (0,), 3), "NASDAQ": ("rsi2", (0,), 3),
    "GOLD": ("tsmom", (250,), 3), "SILVER": ("tsmom", (250,), 3), "OIL": ("tsmom", (250,), 3),
}
SETS = {
    "indici RSI2": ["SP500", "NASDAQ"],
    "indici RSI2 + aur": ["SP500", "NASDAQ", "GOLD"],
    "toate (indici+aur+argint+petrol)": ["SP500", "NASDAQ", "GOLD", "SILVER", "OIL"],
    "doar aur+argint+petrol tendinta": ["GOLD", "SILVER", "OIL"],
}


def trades_of(ret, act, idx):
    out, i, n = [], 0, len(act)
    while i < n:
        if act[i] != 0:
            j = i
            while j + 1 < n and act[j + 1] == act[i]:
                j += 1
            out.append((idx[i], idx[j], np.array(ret[i:j + 1])))
            i = j + 1
        else:
            i += 1
    return out


def simulate(all_trades, start, end, eq0=EQ0):
    """all_trades: list (instrument, t0, t1, rets). Intrari in ordinea datei; sar peste daca marja nu ajunge."""
    tr = sorted((t for t in all_trades if start <= t[1] <= end), key=lambda x: x[1])
    eq, peak, mdd, taken, wins = eq0, eq0, 0.0, [], 0
    open_pos = []   # (t_end, margin)
    daily = {}
    for inst, t0, t1, rets in tr:
        open_pos = [(te, m) for te, m in open_pos if te >= t0]
        used = sum(m for _, m in open_pos)
        margin = EXPO / LEV[inst]
        if eq < margin + 1 or used + margin > eq:
            continue
        pnl = (rets * EXPO).sum()
        eq += pnl
        open_pos.append((t1, margin))
        taken.append(pnl)
        wins += pnl > 0
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
        if eq <= 0:
            eq = 0
            break
    n = len(taken)
    return {"final": eq, "n": n, "win": wins / n * 100 if n else 0, "mdd": mdd * 100, "pnl": taken}


def main():
    data = {}
    for name in CFG:
        sym, cost, grp = rd.INSTR[name]
        df = rd.fetch_daily(sym)
        data[name] = (df, cost)
    all_tr = {}
    for name, (fam, p, k) in CFG.items():
        df, cost = data[name]
        o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
        atr = ta.atr(df).to_numpy()
        ret, act = rd.executor(o, h, l, c, atr, rd.targets(df, fam, p), k, cost, 10 if fam == "rsi2" else None, with_active=True)
        all_tr[name] = trades_of(ret, act, df.index)
        print(f"{name}: {len(all_tr[name])} tranzactii in {len(df)/252:.1f} ani")
    t_start, t_end = pd.Timestamp("2003-06-01", tz="UTC"), pd.Timestamp.now(tz="UTC")
    for label, names in SETS.items():
        trades = [(n, a, b, r) for n in names for a, b, r in all_tr[n]]
        full = simulate(trades, t_start, t_end)
        oos = simulate(trades, pd.Timestamp(rd.OOS_START, tz="UTC"), t_end)
        # ferestre de 1 an, start in fiecare luna, cont nou de 140$
        res = []
        for st in pd.date_range("2005-01-01", "2025-09-01", freq="MS", tz="UTC"):
            res.append(simulate(trades, st, st + pd.DateOffset(years=1))["final"] - EQ0)
        res = np.array(res)
        print(f"\n== {label} ==")
        print(f"  Tot istoricul: {full['n']} tranz, {full['win']:.0f}% castig, cont final {full['final']:.0f}$, cadere max {full['mdd']:.0f}%")
        print(f"  Din 2016 (nevazut): {oos['n']} tranz ({oos['n']/10:.1f}/an), {oos['win']:.0f}% castig, cont final {oos['final']:.0f}$, cadere max {oos['mdd']:.0f}%")
        print(f"  Ferestre de 1 an cu 140$: pe minus in {np.mean(res < 0)*100:.0f}% din {len(res)} ferestre; "
              f"mediana {np.median(res):+.0f}$, 10% cele mai rele <= {np.percentile(res, 10):+.0f}$, 10% cele mai bune >= {np.percentile(res, 90):+.0f}$, "
              f"cont pierdut aproape tot (<30$) in {np.mean(res < -110)*100:.0f}%")


if __name__ == "__main__":
    sys.exit(main())
