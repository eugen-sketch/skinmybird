"""Scanare semnale: aceleasi definitii ca in cercetare (strategies.py), pe ultima bara de 1 ora INCHEIATA."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

import strategies
import ta

REASONS = {
    "london_breakout": "a spart intervalul din noaptea asiatică, acum la deschiderea Londrei 🇬🇧",
    "rsi_rev": "a mers prea departe într-o direcție într-un timp scurt, mă aștept la o revenire",
    "pullback": "trendul orar e clar, iar prețul tocmai și-a revenit după o mică retragere",
    "donchian": "trendul orar e clar și prețul tocmai a spart maximul/minimul ultimelor ore, în direcția trendului",
}


def reason_for(name: str) -> str:
    key = "london_breakout" if name == "london_breakout" else "pullback" if name.startswith("pullback") else \
        "donchian" if name.startswith("donchian") else "rsi_rev"
    return REASONS[key]


def trend_of(df: pd.DataFrame) -> str:
    """Trendul orar: 'sus' / 'jos' / 'lateral' (EMA50 vs EMA200 si pretul fata de EMA50)."""
    c = df["close"]
    e50, e200 = float(ta.ema(c, 50).iloc[-1]), float(ta.ema(c, 200).iloc[-1])
    px = float(c.iloc[-1])
    return "sus" if e50 > e200 and px > e50 else "jos" if e50 < e200 and px < e50 else "lateral"


def completed(df: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Doar orele INCHEIATE. Yahoo trimite la final si bara orei curente (in formare) plus o 'bara live' cu ora exacta
    de acum (ex. 08:07:51): le scoatem pe amandoua."""
    now = now or pd.Timestamp.now(tz="UTC")
    real = df[(df.index.minute == 0) & (df.index.second == 0)]          # bare aliniate la ora fixa
    return real[real.index + timedelta(hours=1) <= now]                  # ora trebuie sa se fi terminat


def edge(series: pd.Series) -> int:
    """Votul barei curente, doar daca e NOU (bara de dinainte avea alt vot). O conditie care ramane adevarata ore la rand
    (RSI extrem, pret peste maximul ultimelor ore) nu mai produce un semnal nou la fiecare ora."""
    last = int(series.iloc[-1])
    prev = int(series.iloc[-2]) if len(series) > 1 else 0
    return last if last != prev else 0


def scan(df: pd.DataFrame, names: list[str], now: pd.Timestamp | None = None) -> dict:
    """+1 BUY / -1 SELL / 0. Semnale contradictorii => 0. Se folosesc doar orele incheiate."""
    now = now or pd.Timestamp.now(tz="UTC")
    df = completed(df, now)
    S = strategies.all_signals(df)
    votes = {n: edge(S[n]) for n in names}
    side = 1 if (1 in votes.values() and -1 not in votes.values()) else -1 if (-1 in votes.values() and 1 not in votes.values()) else 0
    why = [reason_for(n) for n, v in votes.items() if v == side and side]
    price = float(df["close"].iloc[-1])
    today = df[df.index >= df.index[-1].normalize()]
    asia = today.between_time("00:00", "06:59")
    hi, lo = (float(asia["high"].max()), float(asia["low"].min())) if len(asia) >= 5 else (None, None)
    pos = None if hi is None else ("deasupra" if price > hi else "sub" if price < lo else "în interior")
    return {"side": side, "why": "; ".join(dict.fromkeys(why)), "rsi": float(ta.rsi(df["close"], 14).iloc[-1]),
            "price": price, "bar": df.index[-1].isoformat(), "asia_pos": pos, "n_bars": len(df),
            "atr_pct": float(ta.atr(df).iloc[-1]) / price, "trend": trend_of(df),
            "age_min": (now - (df.index[-1] + timedelta(hours=1))).total_seconds() / 60}
