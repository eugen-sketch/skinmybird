#!/usr/bin/env python3
"""Verificare pe date reale: bare, proaspatime, RSI recalculat independent, trend, ATR, voturi pe familii, pret Yahoo vs eToro.
Doar date de piata (nimic despre cont) - poate rula in loguri publice."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import signals
import strategies
import ta

cfg = json.loads((Path(__file__).parent / "config.json").read_text())
now = pd.Timestamp(datetime.now(timezone.utc))
print(f"Acum: {now:%Y-%m-%d %H:%M} UTC ({now:%A})\n")


def rsi_wilder(close: np.ndarray, n: int = 14) -> float:
    d = np.diff(close)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    for x, y in zip(up[n:], dn[n:]):
        au, ad = (au * (n - 1) + x) / n, (ad * (n - 1) + y) / n
    return 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)


api = ids = None
try:
    from etoro import EToroDemo
    api = EToroDemo()
except Exception as e:  # noqa: BLE001
    print(f"[!] fara eToro: {type(e).__name__}")

for inst in cfg["instruments"]:
    n = inst["name"]
    try:
        raw = ta.fetch_ohlc(inst["yahoo"], "1h", "90d")
        df = signals.completed(raw, now)
        s = signals.scan(raw, inst["signals"], now)
    except Exception as e:  # noqa: BLE001
        print(f"{n}: EROARE {type(e).__name__}: {str(e)[:100]}")
        continue
    stamps = ",".join(f"{t:%d %H:%M}" for t in raw.index[-3:])
    own, ref = s["rsi"], rsi_wilder(df["close"].to_numpy())
    S = strategies.all_signals(df)
    votes = {k: int(S[k].iloc[-1]) for k in inst["signals"]}
    line = (f"{n:8s} bare brute {len(raw):4d} (ultimele: {stamps}) | complete {len(df):4d}, ultima {df.index[-1]:%d %H:%M}, vechime {s['age_min']:6.0f} min"
            f" | RSI {own:5.1f} (control {ref:5.1f}) | trend {s['trend']:8s} | ATR {s['atr_pct'] * 100:.3f}% | voturi {votes} -> {s['side']:+d}")
    if api:
        try:
            et = api.last_price(api.find_instrument_id(inst["etoro"]))
            line += f" | Yahoo {s['price']:.4g} vs eToro {et:.4g} ({(et / s['price'] - 1) * 100:+.2f}%)"
        except Exception as e:  # noqa: BLE001
            line += f" | eToro pret: {type(e).__name__}"
    print(line)
