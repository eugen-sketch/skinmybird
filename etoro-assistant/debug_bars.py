#!/usr/bin/env python3
"""Depanare: ce ore au ultimele bare Yahoo si ce ora e acum (doar date de piata, fara pozitii)."""
import pandas as pd

import signals
import ta

now = pd.Timestamp.now(tz="UTC")
print("ACUM (UTC):", now)
for sym in ("EURUSD=X", "USDJPY=X", "CL=F"):
    df = ta.fetch_ohlc(sym, "1h", "30d")
    print(sym, "ultimele 3 bare:", [str(t) for t in df.index[-3:]], "tz:", df.index.tz)
    s = signals.scan(df, ["london_breakout"])
    print("   scan() a folosit bara:", s["bar"], "| pozitie fata de interval:", s["asia_pos"])
