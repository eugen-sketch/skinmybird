#!/usr/bin/env python3
"""Cautare riguroasa pe date ZILNICE (~20 ani): parametri alesi pe 2003-2015, verificati pe 2016-azi (nevazut)."""
import itertools
import sys

import numpy as np
import pandas as pd

import ta

INSTR = {  # nume: (simbol Yahoo, cost dus-intors %, grup)
    "EURUSD": ("EURUSD=X", 0.012, "fx"), "GBPUSD": ("GBPUSD=X", 0.018, "fx"), "USDJPY": ("USDJPY=X", 0.018, "fx"),
    "AUDUSD": ("AUDUSD=X", 0.022, "fx"), "USDCAD": ("USDCAD=X", 0.022, "fx"), "USDCHF": ("USDCHF=X", 0.025, "fx"),
    "NZDUSD": ("NZDUSD=X", 0.030, "fx"), "GOLD": ("GC=F", 0.04, "cmd"), "SILVER": ("SI=F", 0.08, "cmd"),
    "OIL": ("CL=F", 0.06, "cmd"), "SP500": ("ES=F", 0.03, "idx"), "NASDAQ": ("NQ=F", 0.04, "idx"),
}
CARRY = 0.02          # % din expunere pe noapte (taxa de tinere peste noapte eToro, estimat)
OOS_START = "2016-01-01"


def executor(o, h, l, c, atr, target, k, cost, max_hold=None):
    """target[t] = pozitia dorita (+1/-1/0) decisa la inchiderea zilei t, executata la deschiderea zilei t+1. Stop = k*ATR."""
    n = len(c)
    ret = np.zeros(n)
    pos, entry, stop, held = 0, 0.0, 0.0, 0
    for t in range(1, n):
        want = int(target[t - 1])
        if max_hold and pos != 0 and held >= max_hold:
            want = 0
        prev = c[t - 1]
        day = 0.0
        if pos != 0 and want != pos:                     # iesire la deschidere
            day += pos * (o[t] / prev - 1) - cost / 2 / 100
            prev, pos, held = o[t], 0, 0
        if pos == 0 and want != 0 and np.isfinite(atr[t - 1]):
            pos, entry, held = want, o[t], 0
            stop = entry - pos * k * atr[t - 1]
            day -= cost / 2 / 100
            prev = o[t]
        if pos != 0:
            hit = (l[t] <= stop) if pos == 1 else (h[t] >= stop)
            if hit:
                px = min(stop, o[t]) if pos == 1 else max(stop, o[t])
                day += pos * (px / prev - 1) - cost / 2 / 100 - CARRY / 100
                pos, held = 0, 0
                ret[t] = day
                continue
            day += pos * (c[t] / prev - 1) - CARRY / 100
            held += 1
        ret[t] = day
    return ret


def rsi_arr(c, n):
    return ta.rsi(pd.Series(c), n).to_numpy()


def targets(df, fam, p):
    c = df["close"].to_numpy(); hi = df["high"].to_numpy(); lo = df["low"].to_numpy()
    n = len(c)
    t = np.zeros(n, dtype=int)
    if fam == "donchian":
        N, M = p
        hh = pd.Series(hi).rolling(N).max().shift().to_numpy(); ll = pd.Series(lo).rolling(N).min().shift().to_numpy()
        xh = pd.Series(hi).rolling(M).max().shift().to_numpy(); xl = pd.Series(lo).rolling(M).min().shift().to_numpy()
        cur = 0
        for i in range(n):
            if cur == 0:
                if c[i] > hh[i]:
                    cur = 1
                elif c[i] < ll[i]:
                    cur = -1
            elif cur == 1 and c[i] < xl[i]:
                cur = 0
            elif cur == -1 and c[i] > xh[i]:
                cur = 0
            t[i] = cur
    elif fam == "macross":
        f, s = p
        fa = pd.Series(c).rolling(f).mean().to_numpy(); sa = pd.Series(c).rolling(s).mean().to_numpy()
        t = np.where(fa > sa, 1, np.where(fa < sa, -1, 0))
        t[np.isnan(sa)] = 0
    elif fam == "tsmom":
        L = p[0]
        r = pd.Series(c).pct_change(L).to_numpy()
        t = np.where(r > 0, 1, np.where(r < 0, -1, 0))
        t[np.isnan(r)] = 0
    elif fam == "rsi2":
        up, dn = pd.Series(c).rolling(200).mean().to_numpy(), None
        r = rsi_arr(c, 2)
        cur = 0
        for i in range(n):
            if np.isnan(up[i]):
                continue
            if cur == 0:
                if r[i] < 10 and c[i] > up[i]:
                    cur = 1
                elif r[i] > 90 and c[i] < up[i]:
                    cur = -1
            elif cur == 1 and r[i] > 60:
                cur = 0
            elif cur == -1 and r[i] < 40:
                cur = 0
            t[i] = cur
    return t


GRID = {
    "donchian": [((20, 10), 3), ((40, 20), 3), ((55, 20), 3), ((100, 50), 3), ((55, 20), 5), ((100, 50), 5)],
    "macross": [((10, 50), 3), ((20, 100), 3), ((50, 200), 3), ((20, 100), 5), ((50, 200), 5)],
    "tsmom": [((60,), 3), ((120,), 3), ((250,), 3), ((120,), 5), ((250,), 5)],
    "rsi2": [((0,), 3), ((0,), 5)],
}


def sharpe(r):
    r = np.asarray(r)
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 10 and r.std() > 0 else 0.0


def main():
    data = {}
    for name, (sym, cost, grp) in INSTR.items():
        try:
            df = ta.fetch_ohlc(sym, "1d", "max").dropna()
            df = df[df.index >= "2003-01-01"]
            if len(df) > 1500:
                data[name] = (df, cost, grp)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {name}: {e}")
    print({k: (len(v[0]), str(v[0].index[0].date())) for k, v in data.items()})
    res = {}   # (fam, p, k) -> {instrument: Series zilnic}
    for fam, plist in GRID.items():
        for p, k in plist:
            per = {}
            for name, (df, cost, grp) in data.items():
                o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
                atr = ta.atr(df).to_numpy()
                per[name] = pd.Series(executor(o, h, l, c, atr, targets(df, fam, p), k, cost, 10 if fam == "rsi2" else None), index=df.index)
            res[(fam, p, k)] = per

    def port(per, grp=None):
        d = pd.DataFrame({n: s for n, s in per.items() if grp is None or data[n][2] in grp})
        return d.mean(axis=1, skipna=True).dropna()
    print("\nfamilie parametri | IS Sharpe | OOS Sharpe | OOS an% (expunere 1x) | OOS dd% | instrumente OOS>0")
    rows = []
    for key, per in res.items():
        pf = port(per)
        is_, oos = pf[pf.index < OOS_START], pf[pf.index >= OOS_START]
        pos_inst = sum(1 for s in per.values() if s[s.index >= OOS_START].sum() > 0)
        eq = (1 + oos).cumprod()
        rows.append((key, sharpe(is_), sharpe(oos), oos.mean() * 252 * 100, ((eq / eq.cummax()) - 1).min() * 100, pos_inst))
        print(f"{key[0]} {key[1]} stop{key[2]} | {rows[-1][1]:+.2f} | {rows[-1][2]:+.2f} | {rows[-1][3]:+.1f}% | {rows[-1][4]:.0f}% | {pos_inst}/{len(per)}")
    print("\nAlegere pe IS, verdict pe OOS (cea mai buna setare IS a fiecarei familii):")
    for fam in GRID:
        best = max((r for r in rows if r[0][0] == fam), key=lambda r: r[1])
        meds = np.median([r[2] for r in rows if r[0][0] == fam])
        print(f"  {fam}: aleasa {best[0][1]} stop{best[0][2]} IS {best[1]:+.2f} -> OOS {best[2]:+.2f} ({best[3]:+.1f}%/an, dd {best[4]:.0f}%), mediana OOS pe toata grila {meds:+.2f}")
    print("\nPe grupe (cea mai buna setare IS a fiecarei familii):")
    for grp in (("fx",), ("cmd",), ("idx",)):
        if not any(v[2] in grp for v in data.values()):
            continue
        for fam in GRID:
            keys = [r[0] for r in rows if r[0][0] == fam]
            best = max(keys, key=lambda k: sharpe(port(res[k], grp)[port(res[k], grp).index < OOS_START]))
            pf = port(res[best], grp)
            print(f"  {grp[0]} {fam} {best[1]} st{best[2]}: IS {sharpe(pf[pf.index < OOS_START]):+.2f} OOS {sharpe(pf[pf.index >= OOS_START]):+.2f}")
    # noroc: semnale aleatoare zilnice, acelasi executor
    rng = np.random.default_rng(0)
    sh = []
    for _ in range(10):
        per = {}
        for name, (df, cost, grp) in data.items():
            o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
            atr = ta.atr(df).to_numpy()
            t = np.zeros(len(c), dtype=int); cur = 0
            for i in range(len(c)):
                if rng.random() < 0.03:
                    cur = int(rng.choice([-1, 0, 1]))
                t[i] = cur
            per[name] = pd.Series(executor(o, h, l, c, atr, t, 3, cost), index=df.index)
        pf = port(per)
        sh.append(sharpe(pf[pf.index >= OOS_START]))
    print(f"\nNoroc (pozitii aleatoare): Sharpe OOS mediu {np.mean(sh):+.2f}, max {np.max(sh):+.2f}")


if __name__ == "__main__":
    sys.exit(main())
