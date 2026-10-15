"""Reconstituie, bara cu bara, ce au votat regulile botului pe EUR/USD in ultimele ~36 de ore (aceleasi reguli ca live)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import modes
import signals
import strategies
import ta

cfg = json.loads((Path(__file__).parent / "config.json").read_text())
inst = next(i for i in cfg["instruments"] if i["name"] == "EURUSD")
df = ta.fetch_ohlc("EURUSD=X", "1h", "30d")
df = df[(df.index.minute == 0) & (df.index.second == 0)]
names = inst["signals"]
print("semnale configurate:", names)
print("ora(RO)      close    rsi   trend  voturi(+1 cumpar/-1 vand)                    side  val(ATR)")
end = df.index[-1]
for t in df.index[df.index >= end - pd.Timedelta(hours=36)]:
    sub = df[df.index <= t]
    now = t + pd.Timedelta(hours=1, minutes=1)
    if len(sub) < 250:
        continue
    S = strategies.all_signals(sub)
    votes = {n: signals.edge(S[n]) for n in names}
    res = signals.scan(sub, names, now=now)
    v = " ".join(f"{n}={x:+d}" for n, x in votes.items() if x) or "-"
    ro = (t + pd.Timedelta(hours=3)).strftime("%d.%m %H:%M")
    print(f"{ro}  {float(sub['close'].iloc[-1]):.5f}  {res['rsi']:5.1f}  {res['trend']:7s} {v:50s} {res['side']:+d}  {res['move_atr']:+.2f}")
