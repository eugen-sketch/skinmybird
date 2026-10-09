"""Scanare semnale: aceleasi definitii ca in cercetare (strategies.py), pe ultima bara de 1 ora INCHEIATA."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

import strategies
import ta

REASONS = {
    "london_breakout": "a spart intervalul din noaptea asiatică, acum la deschiderea Londrei 🇬🇧",
    "rsi_rev": "a mers prea departe într-o direcție într-un timp scurt, mă aștept la o revenire",
}


def scan(df: pd.DataFrame, names: list[str]) -> dict:
    """+1 BUY / -1 SELL / 0. Semnale contradictorii => 0. Bara in formare se ignora."""
    if df.index[-1] + timedelta(hours=1) > pd.Timestamp.now(tz="UTC"):
        df = df.iloc[:-1]
    S = strategies.all_signals(df)
    votes = {n: int(S[n].iloc[-1]) for n in names}
    side = 1 if (1 in votes.values() and -1 not in votes.values()) else -1 if (-1 in votes.values() and 1 not in votes.values()) else 0
    why = [REASONS["london_breakout" if n == "london_breakout" else "rsi_rev"] for n, v in votes.items() if v == side and side]
    return {"side": side, "why": "; ".join(dict.fromkeys(why)), "rsi": float(ta.rsi(df["close"], 14).iloc[-1]),
            "price": float(df["close"].iloc[-1]), "bar": df.index[-1].isoformat()}
