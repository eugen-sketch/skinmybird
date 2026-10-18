"""Paznicul de petrol si proba de miercuri (raportul american de stocuri de petrol), cerute de Eugen pe 18 oct 2026.

- Paznicul: la fiecare 15 minute se uita doar la petrol. Daca petrolul face o miscare mare (intr-o ora a mers de cel putin `move_atr` ori
  mai mult decat de obicei, sau iese din maximul/minimul zilei cu o miscare de cel putin `break_atr`), te avertizeaza clar sa urmaresti
  graficul si propune intrarea in directia miscarii, pe pozitia minima.
- Proba de miercuri: raportul de stocuri apare la 10:30 ora New York-ului. Cu 15 minute inainte te anunta; la 15 minute dupa propune
  intrarea in directia in care a fugit pretul in primele 15 minute, cu plasa dincolo de varful/fundul acelor 15 minute si tinta de
  `tp_mult` ori distanta plasei (plus spreadul), pe pozitia minima."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pandas as pd

import ta

try:
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001 - fara baza de fusuri orare: regula americana de ora de vara, calculata de mana
    NY = None


def ny_to_utc(day, hh: int, mm: int) -> datetime:
    """Ora din New York (cu ora de vara/iarna americana) a zilei `day`, in UTC."""
    if NY is not None:
        return datetime.combine(day, time(hh, mm), tzinfo=NY).astimezone(timezone.utc)
    y = day.year
    mar = datetime(y, 3, 8) + timedelta(days=(6 - datetime(y, 3, 8).weekday()) % 7)        # a doua duminica din martie
    nov = datetime(y, 11, 1) + timedelta(days=(6 - datetime(y, 11, 1).weekday()) % 7)      # prima duminica din noiembrie
    off = 4 if mar.date() <= day < nov.date() else 5
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc) + timedelta(hours=off)


def watch_signal(d5: pd.DataFrame, h1: pd.DataFrame, now: datetime, o: dict) -> dict | None:
    """Miscare mare pe petrol acum? {side, move, brk, atr, px, day_hi, day_lo} sau None. d5 = lumanari de 5 min, h1 = de 1 ora (Yahoo)."""
    if d5 is None or h1 is None or len(d5) < 20 or len(h1) < 20:
        return None
    d5 = d5[d5.index <= now]
    if d5.empty or (now - d5.index[-1]).total_seconds() > 20 * 60:                    # date vechi: piata inchisa sau blocata
        return None
    done = h1[(h1.index.minute == 0) & (h1.index + timedelta(hours=1) <= now)]
    if len(done) < 20:
        return None
    atr = float(ta.atr(done).iloc[-1])
    px = float(d5["close"].iloc[-1])
    ago = d5[d5.index <= d5.index[-1] - timedelta(minutes=60)]
    if ago.empty or atr <= 0:
        return None
    move = (px - float(ago["close"].iloc[-1])) / atr
    day = d5[d5.index >= d5.index[-1].normalize()]
    before = day[day.index <= d5.index[-1] - timedelta(minutes=15)]
    brk = 0
    hi = lo = None
    if len(before) >= 3:
        hi, lo = float(before["high"].max()), float(before["low"].min())
        brk = 1 if px > hi else -1 if px < lo else 0
    side = 0
    if abs(move) >= o.get("move_atr", 1.5):
        side = 1 if move > 0 else -1
    elif brk and (move > 0) == (brk > 0) and abs(move) >= o.get("break_atr", 0.75):
        side = brk
    if not side:
        return None
    return {"side": side, "move": move, "brk": brk == side, "atr": atr, "px": px, "day_hi": hi, "day_lo": lo}


def eia_entry(d5: pd.DataFrame, t_rel: datetime, px: float, spread_pct: float, o: dict) -> dict | None:
    """Intrarea de proba dupa raport: directia primelor 15 minute, plasa dincolo de extrema lor, tinta = tp_mult x plasa + spread.
    Intoarce {side, sl_pct, tp_pct, move_pct, ext} (distante ca fractie din pret) sau {'skip': motiv}."""
    if d5 is None or d5.empty:
        return {"skip": "nu am prețuri pe 5 minute pentru petrol"}
    pre = d5[d5.index < t_rel]
    first = d5[(d5.index >= t_rel) & (d5.index < t_rel + timedelta(minutes=15))]
    if pre.empty or len(first) < 2:
        return {"skip": "nu am prețurile primelor 15 minute de după raport"}
    p0, p15 = float(pre["close"].iloc[-1]), float(first["close"].iloc[-1])
    mv = (p15 - p0) / p0
    if abs(mv) < o.get("min_move_pct", 0.0005):
        return {"skip": f"petrolul aproape nu s-a mișcat în primele 15 minute ({mv * 100:+.2f}%)"}
    side = 1 if mv > 0 else -1
    ext = float(first["low"].min()) if side == 1 else float(first["high"].max())
    buf = px * spread_pct / 200
    sl_px = ext - buf if side == 1 else ext + buf
    sl_pct = side * (px - sl_px) / px
    if sl_pct <= 0.0005:
        return {"skip": "prețul a revenit deja lângă vârful/fundul primelor 15 minute; plasa ar fi prea aproape"}
    tp_pct = o.get("tp_mult", 1.5) * sl_pct + spread_pct / 100
    return {"side": side, "sl_pct": sl_pct, "tp_pct": tp_pct, "move_pct": mv, "ext": ext}


def oil4h_signal(h1: pd.DataFrame, now: datetime, o: dict) -> dict | None:
    """Petrol pe 4 ore (proba aprobata de Eugen pe 18 oct): lumanarea de 4 ore abia incheiata a inchis peste maximul celor `lookback_bars`
    lumanari de 4 ore dinainte (~5 zile), pentru prima oara, iar trendul pe zile e in sus (inchiderea zilei peste media ei pe `ema_daily` zile).
    Doar cumparare. {px, atr4, bar_end, hh} sau None. Se folosesc doar ore incheiate."""
    if h1 is None or len(h1) < 200:
        return None
    done = h1[(h1.index.minute == 0) & (h1.index + timedelta(hours=1) <= now)]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    b4 = done.resample("4h", label="left", closed="left").agg(agg).dropna()
    b4 = b4[b4.index + timedelta(hours=4) <= now]
    d1 = done.resample("1D", label="left", closed="left").agg(agg).dropna()
    d1 = d1[(d1.index.weekday < 5) & (d1.index + timedelta(days=1) <= now)]
    n = int(o.get("lookback_bars", 30))
    if len(b4) < n + 20 or len(d1) < int(o.get("ema_daily", 50)) + 5:
        return None
    bar_end = b4.index[-1] + timedelta(hours=4)
    if (now - bar_end).total_seconds() > o.get("max_age_min", 90) * 60:            # lumanare veche (pornire dupa o pauza): nu o mai folosim
        return None
    hh = b4["high"].rolling(n).max().shift()
    above = b4["close"] > hh
    ema = ta.ema(d1["close"], int(o.get("ema_daily", 50)))
    up = bool(d1["close"].iloc[-1] > ema.iloc[-1])
    if not (above.iloc[-1] and not above.iloc[-2] and up):
        return None
    return {"px": float(b4["close"].iloc[-1]), "atr4": float(ta.atr(b4).iloc[-1]), "bar_end": bar_end, "hh": float(hh.iloc[-1])}

