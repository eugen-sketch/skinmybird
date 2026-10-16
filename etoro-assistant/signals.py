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


def trend4h(df: pd.DataFrame) -> str | None:
    """Trendul pe 4 ore (din lumanarile de 1 ora regrupate): EMA20 vs EMA50 si pretul fata de EMA20."""
    try:
        c4 = df["close"].resample("4h").last().dropna()
        if len(c4) < 60:
            return None
        e20, e50 = float(ta.ema(c4, 20).iloc[-1]), float(ta.ema(c4, 50).iloc[-1])
        px = float(c4.iloc[-1])
        return "sus" if e20 > e50 and px > e20 else "jos" if e20 < e50 and px < e20 else "lateral"
    except Exception:  # noqa: BLE001
        return None


def levels_sr(df: pd.DataFrame, lookback: int = 200, k: int = 5) -> tuple[float | None, float | None]:
    """Suport si rezistenta apropiate: cele mai apropiate maxime/minime locale (varf cu k lumanari in fiecare parte) din ultimele ore."""
    d = df.iloc[-lookback:]
    px = float(d["close"].iloc[-1])
    hi, lo = d["high"].to_numpy(), d["low"].to_numpy()
    res, sup = [], []
    for i in range(k, len(d) - k):
        if hi[i] == hi[i - k:i + k + 1].max() and hi[i] > px:
            res.append(float(hi[i]))
        if lo[i] == lo[i - k:i + k + 1].min() and lo[i] < px:
            sup.append(float(lo[i]))
    return (max(sup) if sup else None), (min(res) if res else None)


def wave(raw: pd.DataFrame, done: pd.DataFrame, trend: str, bars: int = 3, min_atr: float = 1.6, opts: dict | None = None) -> tuple[int, float]:
    """Val mare: pretul LIVE a mers in ultimele `bars` ore cu cel putin `min_atr` x volatilitatea normala (ATR orar) intr-o directie.
    Intram cu valul daca nu merge impotriva trendului orar si nu e deja epuizat (RSI live extrem). Intoarce (directie, miscare in ATR)."""
    o = {"rsi_buy_max": 85, "rsi_sell_min": 15, "allow_neutral": True, **(opts or {})}
    try:
        atr = float(ta.atr(done).iloc[-1])
        live = float(raw["close"].iloc[-1])
        mv = (live - float(done["close"].iloc[-bars])) / atr if atr > 0 else 0.0
        if abs(mv) < min_atr:
            return 0, mv
        side = 1 if mv > 0 else -1
        last_leg = (live - float(done["close"].iloc[-1])) * side             # ultima ora nu s-a intors impotriva valului
        r = float(ta.rsi(raw["close"], 14).iloc[-1])
        if last_leg < -0.3 * atr or (trend == "jos" and side == 1) or (trend == "sus" and side == -1) or (side == 1 and r > o["rsi_buy_max"]) or (side == -1 and r < o["rsi_sell_min"]) \
                or (trend == "lateral" and not o["allow_neutral"]):
            return 0, mv
        return side, mv
    except Exception:  # noqa: BLE001
        return 0, 0.0


def gate(s: dict, g: dict | None) -> tuple[str, str] | None:
    """Poarta de calitate a semnalului. None = semnal acceptat; altfel (cod, detaliu) pentru care il respingem.
    Alese pe 8 luni de date si verificate pe 4 luni nefolosite la cautare: fara regula «pullback» (cea mai slaba), doar in orele bune (Londra+New York),
    doar cand piata are directie clara (ADX) si nu e prea linistita. Semnalele de «val» nu trec pe aici."""
    g = g or {}
    if not g.get("enabled") or str(s.get("sig_key", "")).startswith("wave"):
        return None
    fired = s.get("fired") or []
    pref = tuple(g.get("exclude_prefix", []))
    if pref and fired and all(n.startswith(pref) for n in fired):
        return "regula", ", ".join(fired)
    lo, hi = g.get("hours_utc", [0, 24])
    if s.get("bar_hour") is not None and not lo <= s["bar_hour"] < hi:
        return "ora", f"{lo}-{hi}"
    if s.get("adx") is not None and s["adx"] < g.get("adx_min", 0):
        return "adx", f"{s['adx']:.0f}"
    if s.get("vol_rank") is not None and s["vol_rank"] < g.get("vol_min", 0):
        return "vol", f"{s['vol_rank'] * 100:.0f}"
    return None


def scan(df: pd.DataFrame, names: list[str], now: pd.Timestamp | None = None, wave_atr: float = 1.6, wave_bars: int = 3, wave_opts: dict | None = None) -> dict:
    """+1 BUY / -1 SELL / 0. Semnale contradictorii => 0. Se folosesc doar orele incheiate."""
    now = now or pd.Timestamp.now(tz="UTC")
    raw = df
    live_rsi, live_px, tick = float(ta.rsi(df["close"], 14).iloc[-1]), float(df["close"].iloc[-1]), df.index[-1]     # cu bara in formare (doar informativ)
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
    trend = trend_of(df)
    w_side, w_mv = wave(raw, df, trend, wave_bars, wave_atr, wave_opts)
    cool = int((wave_opts or {}).get("cooldown_min", 180))
    sig_key = df.index[-1].isoformat()
    if side == 0 and w_side:                                                # nimic din regulile clasice, dar e val mare: ne dam cu el
        side, sig_key = w_side, f"wave{w_side:+d}-{now:%Y%m%d}-{(now.hour * 60 + now.minute) // cool}"
        why = [f"val mare: {abs(w_mv):.1f}× volatilitatea normală în ultimele {wave_bars} ore, {'în sus' if w_side == 1 else 'în jos'}, "
               f"nu contrazice trendul orar – mă dau cu valul"]
    vol = (ta.atr(df) / df["close"]).tail(500)
    return {"side": side, "why": "; ".join(dict.fromkeys(why)), "move_atr": w_mv, "sig_key": sig_key, "rsi": float(ta.rsi(df["close"], 14).iloc[-1]),
            "fired": [n for n, v in votes.items() if side and v == side], "adx": float(ta.adx(df).iloc[-1]),
            "vol_rank": float(vol.rank(pct=True).iloc[-1]) if len(vol) >= 100 else None, "bar_hour": df.index[-1].hour,
            "price": price, "bar": df.index[-1].isoformat(), "asia_pos": pos, "n_bars": len(df),
            "atr_pct": float(ta.atr(df).iloc[-1]) / price, "trend": trend,
            "age_min": (now - (df.index[-1] + timedelta(hours=1))).total_seconds() / 60,
            "rsi_live": live_rsi, "price_live": live_px, "tick": tick.isoformat(),
            "trend4h": trend4h(df), "support": levels_sr(raw)[0], "resistance": levels_sr(raw)[1], "_df": raw}
