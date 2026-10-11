#!/usr/bin/env python3
"""Test: ajuta o 'a doua parere' (mai multi indicatori care confirma) semnalele actuale ale asistentului?

Pentru fiecare semnal real al asistentului (aceleasi reguli, aceleasi instrumente) calculez cate din 6 confirmari sunt
de partea lui si masor rezultatul cu TP/SL in $ ca in asistent. Impartit in jumatatea veche (train) si noua (test)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sim
import strategies
import ta

EXPO, TP_USD, SL_USD, MAX_BARS = 1400.0, 2.75, 6.0, 24
cfg = json.loads((Path(__file__).parent / "config.json").read_text())


def confirmations(df: pd.DataFrame) -> np.ndarray:
    """Matrice (n, 6) cu +1/-1/0: votul fiecarui indicator pe fiecare bara (+1 = BUY, -1 = SELL)."""
    c, o, h, l = df["close"], df["open"], df["high"], df["low"]
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    stoch = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    macd = ta.ema(c, 12) - ta.ema(c, 26)
    hist = macd - ta.ema(macd, 9)
    r2 = ta.rsi(c, 2)
    e200 = ta.ema(c, 200)
    votes = [
        np.where(c < mid - 2 * sd, 1, np.where(c > mid + 2 * sd, -1, 0)),          # in afara benzii Bollinger
        np.where(stoch < 20, 1, np.where(stoch > 80, -1, 0)),                       # stocastic extrem
        np.where(hist > hist.shift(), 1, np.where(hist < hist.shift(), -1, 0)),     # MACD isi schimba directia
        np.where(c > o, 1, np.where(c < o, -1, 0)),                                 # lumanarea inchisa in directia semnalului
        np.where(r2 < 10, 1, np.where(r2 > 90, -1, 0)),                             # RSI(2) extrem
        np.where(c > e200, 1, np.where(c < e200, -1, 0)),                           # pozitia fata de media de 200
    ]
    return np.column_stack(votes)


def score(sig: np.ndarray, conf: np.ndarray) -> np.ndarray:
    return (conf == sig[:, None]).sum(axis=1) * (sig != 0)


def main() -> None:
    rows = []   # (instrument, jumatate, scor, pnl_usd)
    for inst in cfg["instruments"]:
        try:
            df = ta.fetch_ohlc(inst["yahoo"], "1h", "730d")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {inst['name']}: {type(e).__name__}")
            continue
        if len(df) < 2000:
            print(f"[!] {inst['name']}: prea putine bare ({len(df)})")
            continue
        S = strategies.all_signals(df)
        pos = sum((S[n].to_numpy() == 1).astype(int) for n in inst["signals"])
        neg = sum((S[n].to_numpy() == -1).astype(int) for n in inst["signals"])
        sig = np.zeros(len(df), dtype=int)
        sig[(pos > 0) & (neg == 0)] = 1
        sig[(neg > 0) & (pos == 0)] = -1
        sc = score(sig, confirmations(df))
        P, half = sim.prep(df), len(df) // 2
        for part, (lo, hi) in (("train", (0, half)), ("test", (half, len(df)))):
            for t in sim.simulate_pct(P, sig, SL_USD / EXPO * 100, TP_USD / EXPO * 100, MAX_BARS, lo, hi, inst["cost"]):
                rows.append((inst["name"], part, int(sc[t[0]]), t[2] / 100 * EXPO))
        print(f"{inst['name']}: {len(df)} bare, semnale {int((sig != 0).sum())}")
    d = pd.DataFrame(rows, columns=["inst", "part", "score", "usd"])
    if d.empty:
        print("Nicio tranzactie.")
        return
    print("\n=== Toate semnalele asistentului, dupa nr. de confirmari (0-6), $ pe tranzactie la TP 2.75$ / SL 6$ ===")
    for k in range(0, 7):
        x = d[d.score >= k]
        if len(x) < 30:
            continue
        tr, te = x[x.part == "train"].usd, x[x.part == "test"].usd
        print(f"confirmari >= {k}: {len(x):5d} tranzactii | castig {100 * (x.usd > 0).mean():4.1f}% | medie {x.usd.mean():+.3f}$ "
              f"| PF train {sim.pf(tr):.2f} / test {sim.pf(te):.2f} | total {x.usd.sum():+.0f}$")
    print("\n=== Pe instrument, confirmari >= 4 vs toate ===")
    for n, g in d.groupby("inst"):
        a, b = g, g[g.score >= 4]
        print(f"{n:8s} toate {len(a):4d} tr {a.usd.mean():+.3f}$ PF {sim.pf(a.usd):.2f} | >=4: {len(b):4d} tr "
              f"{(b.usd.mean() if len(b) else float('nan')):+.3f}$ PF {sim.pf(b.usd):.2f}")


if __name__ == "__main__":
    main()
