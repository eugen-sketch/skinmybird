#!/usr/bin/env python3
"""Variante RSI2 pe indici, alese pe ferestre 2005-2015 si verificate pe ferestre 2016-2025, cont de 140$."""
import itertools
import sys

import numpy as np
import pandas as pd

import research_daily as rd
import research_portfolio as rp
import ta

INDEX = {"SP500": ("ES=F", 0.03), "NASDAQ": ("NQ=F", 0.04), "DOW": ("YM=F", 0.04), "DAX": ("^GDAXI", 0.05), "FTSE": ("^FTSE", 0.05)}
for k in INDEX:
    rp.LEV[k] = 20


def rsi2_target(df, entry, exit_, sma, shorts):
    c = df["close"].to_numpy()
    r = ta.rsi(pd.Series(c), 2).to_numpy()
    ma = pd.Series(c).rolling(sma).mean().to_numpy()
    t = np.zeros(len(c), dtype=int)
    cur = 0
    for i in range(len(c)):
        if np.isnan(ma[i]):
            continue
        if cur == 0:
            if r[i] < entry and c[i] > ma[i]:
                cur = 1
            elif shorts and r[i] > 100 - entry and c[i] < ma[i]:
                cur = -1
        elif cur == 1 and r[i] > exit_:
            cur = 0
        elif cur == -1 and r[i] < 100 - exit_:
            cur = 0
        t[i] = cur
    return t


def windows(trades, y0, y1):
    res = []
    for st in pd.date_range(f"{y0}-01-01", f"{y1}-09-01", freq="MS", tz="UTC"):
        res.append(rp.simulate(trades, st, st + pd.DateOffset(years=1))["final"] - rp.EQ0)
    return np.array(res)


def main():
    data = {}
    for name, (sym, cost) in INDEX.items():
        try:
            df = rd.fetch_daily(sym)
            if len(df) > 1500:
                data[name] = (df, cost)
            print(f"{name}: {len(df)} zile")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {name}: {e}")
    rows = []
    for entry, exit_, sma, k, shorts in itertools.product((5, 10, 15), (50, 60, 70), (100, 200), (1.5, 2.5, 4.0, 8.0), (False, True)):
        trades = []
        for name, (df, cost) in data.items():
            o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
            ret, act = rd.executor(o, h, l, c, ta.atr(df).to_numpy(), rsi2_target(df, entry, exit_, sma, shorts), k, cost, 10, with_active=True)
            trades += [(name, a, b, r) for a, b, r in rp.trades_of(ret, act, df.index)]
        wi, wo = windows(trades, 2005, 2015), windows(trades, 2016, 2025)
        n_year = len(trades) / 23
        rows.append((entry, exit_, sma, k, shorts, n_year,
                     np.mean(wi < 0) * 100, np.median(wi), np.mean(wi < -110) * 100,
                     np.mean(wo < 0) * 100, np.median(wo), np.percentile(wo, 10), np.mean(wo < -110) * 100))
    # criteriu: mediana pozitiva in AMBELE perioade, apoi cele mai putine ferestre pe minus (media celor doua), apoi ruina
    ok = [r for r in rows if r[7] > 0 and r[10] > 0]
    ok.sort(key=lambda r: (r[6] + r[9]) / 2 + (r[8] + r[12]) / 2)
    print("\nentry exit sma stop shorts | tranz/an | 2005-15: minus% mediana$ ruina% | 2016-25: minus% mediana$ p10$ ruina%")
    for r in ok[:15]:
        print(f"RSI<{r[0]} exit>{r[1]} SMA{r[2]} stop{r[3]} {'L+S' if r[4] else 'doar L'} | {r[5]:.1f} | {r[6]:.0f}% {r[7]:+.0f}$ {r[8]:.0f}% | {r[9]:.0f}% {r[10]:+.0f}$ {r[11]:+.0f}$ {r[12]:.0f}%")
    print(f"\nVariante testate: {len(rows)}; cu mediana pozitiva in ambele perioade: {len(ok)}")
    base = [r for r in rows if (r[0], r[1], r[2], r[3], r[4]) == (10, 60, 200, 2.5, True)]
    if base:
        r = base[0]
        print(f"Referinta (10/60/SMA200/stop2.5/L+S): 2005-15 minus {r[6]:.0f}% med {r[7]:+.0f}$ | 2016-25 minus {r[9]:.0f}% med {r[10]:+.0f}$ p10 {r[11]:+.0f}$ ruina {r[12]:.0f}%")


if __name__ == "__main__":
    sys.exit(main())
