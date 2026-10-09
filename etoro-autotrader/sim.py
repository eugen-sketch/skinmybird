"""Simulator de tranzactii: intrare la deschiderea barei urmatoare, SL/TP in multipli ATR, cost inclus."""
from __future__ import annotations

import numpy as np
import pandas as pd

import ta


def prep(df: pd.DataFrame) -> dict:
    return {k: df[k].to_numpy() for k in ("open", "high", "low", "close")} | {"atr": ta.atr(df).to_numpy(), "index": df.index}


def simulate(P: dict, sig: np.ndarray, sl_m: float, tp_m: float, max_bars: int, lo: int, hi: int, cost_pct: float):
    """Returneaza lista (i_intrare, j_iesire, pnl_pct, sl_pct)."""
    o, h, l, c, at = P["open"], P["high"], P["low"], P["close"], P["atr"]
    out, i = [], max(lo, 250)
    while i < hi - 2:
        s = int(sig[i])
        if s == 0 or not np.isfinite(at[i]) or at[i] <= 0:
            i += 1
            continue
        e = o[i + 1]
        sl, tp = e - s * sl_m * at[i], e + s * tp_m * at[i]
        end = min(i + 1 + max_bars, hi - 1)
        px, j = c[end], end
        for k in range(i + 1, end + 1):
            if s == 1:
                if l[k] <= sl:
                    px, j = min(sl, o[k]) if k > i + 1 else sl, k
                    break
                if h[k] >= tp:
                    px, j = tp, k
                    break
            else:
                if h[k] >= sl:
                    px, j = max(sl, o[k]) if k > i + 1 else sl, k
                    break
                if l[k] <= tp:
                    px, j = tp, k
                    break
        out.append((i, j, s * (px / e - 1) * 100 - cost_pct, sl_m * at[i] / e * 100))
        i = j + 1
    return out


def pf(p) -> float:
    p = np.asarray(p)
    if len(p) == 0:
        return 0.0
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    return float(g / l) if l else 9.9


def simulate_pct(P: dict, sig: np.ndarray, sl_pct: float, tp_pct: float, max_bars: int, lo: int, hi: int, cost_pct: float):
    """Ca simulate(), dar SL/TP sunt procente fixe din pretul de intrare (tinte in $ la expunere fixa)."""
    o, h, l, c = P["open"], P["high"], P["low"], P["close"]
    out, i = [], max(lo, 250)
    while i < hi - 2:
        s = int(sig[i])
        if s == 0:
            i += 1
            continue
        e = o[i + 1]
        sl, tp = e * (1 - s * sl_pct / 100), e * (1 + s * tp_pct / 100)
        end = min(i + 1 + max_bars, hi - 1)
        px, j = c[end], end
        for k in range(i + 1, end + 1):
            if s == 1:
                if l[k] <= sl:
                    px, j = min(sl, o[k]) if k > i + 1 else sl, k
                    break
                if h[k] >= tp:
                    px, j = tp, k
                    break
            else:
                if h[k] >= sl:
                    px, j = max(sl, o[k]) if k > i + 1 else sl, k
                    break
                if l[k] <= tp:
                    px, j = tp, k
                    break
        out.append((i, j, s * (px / e - 1) * 100 - cost_pct))
        i = j + 1
    return out
