"""Paznicul de petrol, proba de miercuri (raportul de stocuri) si alarma contului (cerute de Eugen pe 18 oct 2026)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import oilwatch  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG, press  # noqa: E402

WED = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)          # miercuri; raportul: 10:30 New York = 14:30 UTC


def h1(end, px=80.0, n=300):
    idx = pd.date_range(end=end.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1), periods=n, freq="1h")
    c = px + np.sin(np.arange(n) / 5) * 0.3
    return pd.DataFrame({"open": c, "high": c + 0.25, "low": c - 0.25, "close": c}, index=idx)


def m5(end, path):
    """Lumanari de 5 minute care se termina la `end`, cu inchiderile `path` (ultimele)."""
    n = 600
    base = np.full(n, float(path[0]))
    base[-len(path):] = path
    idx = pd.date_range(end=end - timedelta(minutes=5), periods=n, freq="5min")
    return pd.DataFrame({"open": base, "high": base + 0.03, "low": base - 0.03, "close": base}, index=idx)


def make(now, d5, hh, auto=False):
    cfg = {**CFG, "max_positions": 4}
    tg, br = FakeTG(), FakeBroker()
    br.prices["OIL"] = float(d5["close"].iloc[-1])
    fetch = lambda sym, interval="1h", rng="": d5 if interval == "5m" else hh  # noqa: E731
    a = A.Assistant(cfg, tg, br, fetch=fetch, now_fn=lambda: now, sleep=lambda s: None)
    a.unlocked, a.autotrade = True, auto
    return a, tg, br


def test_new_york_time_follows_us_daylight_saving():
    assert oilwatch.ny_to_utc(datetime(2026, 10, 21).date(), 10, 30) == datetime(2026, 10, 21, 14, 30, tzinfo=timezone.utc)
    assert oilwatch.ny_to_utc(datetime(2026, 11, 4).date(), 10, 30) == datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc)


def test_watch_signal_big_move_flat_and_stale():
    now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    hh = h1(now)
    jump = list(np.linspace(80.0, 81.2, 12))                       # +1,2 $ intr-o ora, fata de o miscare obisnuita de ~0,5 $
    s = oilwatch.watch_signal(m5(now, [80.0] * 20 + jump), hh, now, {"move_atr": 1.5})
    assert s and s["side"] == 1 and s["move"] >= 1.5 and s["brk"]
    assert oilwatch.watch_signal(m5(now, [80.0] * 40), hh, now, {"move_atr": 1.5}) is None
    assert oilwatch.watch_signal(m5(now - timedelta(hours=1), [80.0] * 20 + jump), hh, now, {}) is None       # date vechi


def test_eia_entry_follows_first_15_minutes_with_stop_beyond_them():
    t_rel = WED.replace(minute=30)
    d5 = m5(t_rel + timedelta(minutes=15), [80.0] * 10 + [80.1, 80.3, 80.5])
    e = oilwatch.eia_entry(d5, t_rel, 80.5, 0.06, {"tp_mult": 1.5})
    assert e["side"] == 1 and abs(e["ext"] - (80.1 - 0.03)) < 1e-9
    assert abs(e["sl_pct"] - (80.5 - (e["ext"] - 80.5 * 0.0003)) / 80.5) < 1e-9 and abs(e["tp_pct"] - (1.5 * e["sl_pct"] + 0.0006)) < 1e-12
    flat = oilwatch.eia_entry(m5(t_rel + timedelta(minutes=15), [80.0] * 13), t_rel, 80.0, 0.06, {})
    assert "skip" in flat


def test_oil_watch_warns_and_proposes_minimum_position_with_buttons():
    now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    a, tg, br = make(now, m5(now, [80.0] * 20 + list(np.linspace(80.0, 81.2, 12))), h1(now))
    a.oil_watch(now)
    assert any("URMĂREȘTE GRAFICUL PETROLULUI" in t for t in tg.texts)
    p = next(iter(a.pending.values()))
    assert p["name"] == "OIL" and p["min_size"] and abs(p["amount"] - 101.0) < 0.01 and not br.pos      # pozitia minima, nimic deschis
    a.oil_watch(now + timedelta(minutes=15))                          # cel mult un avertisment pe ora
    assert sum("URMĂREȘTE" in t for t in tg.texts) == 1


def test_oil_watch_on_autotrade_opens_minimum_position():
    now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    a, tg, br = make(now, m5(now, [80.0] * 20 + list(np.linspace(80.0, 81.2, 12))), h1(now), auto=True)
    a.oil_watch(now)
    pos = list(br.pos.values())
    assert len(pos) == 1 and pos[0]["name"] == "OIL" and abs(pos[0]["amount"] - 101.0) < 0.01 and pos[0]["leverage"] == 10
    assert a.special[pos[0]["id"]]["tag"] == "paznic"


def test_eia_trial_heads_up_then_entry_then_hour_check():
    t_rel = WED.replace(minute=30)
    d5 = m5(t_rel + timedelta(minutes=15), [80.0] * 10 + [80.1, 80.3, 80.5])
    a, tg, br = make(WED.replace(minute=16), d5, h1(WED))
    a.eia_tick(WED.replace(minute=16))
    assert any("raportul american de stocuri" in t and "17:30" in t for t in tg.texts)
    a.now_fn = lambda: t_rel + timedelta(minutes=16)
    a.eia_tick(t_rel + timedelta(minutes=16))
    p = next(iter(a.pending.values()))
    assert p["special"] == "eia" and p["side"] == 1 and p["min_size"] and p["sl_px"] < 80.1 < 80.5 < p["tp_px"]
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    pid = next(iter(br.pos))
    a.known[pid]["last_pnl"] = -1.2
    later = t_rel + timedelta(minutes=80)
    a.now_fn = lambda: later
    a.eia_tick(later)
    assert any("deschisă de o oră" in t and "-$1.20" in t for t in tg.texts)
    a.eia_tick(later + timedelta(minutes=5))
    assert sum("deschisă de o oră" in t for t in tg.texts) == 1


def test_eia_trial_only_on_wednesday_and_until_end_date():
    t_rel = WED.replace(minute=30)
    d5 = m5(t_rel + timedelta(minutes=15), [80.0] * 10 + [80.1, 80.3, 80.5])
    thu = WED + timedelta(days=1, minutes=16)
    a, tg, br = make(thu, d5, h1(WED))
    a.eia_tick(thu)
    assert not tg.texts
    late = datetime(2026, 11, 18, 15, 16, tzinfo=timezone.utc)      # dupa sfarsitul probei (11 nov)
    a.eia_tick(late)
    assert not tg.texts


def test_account_alarm_once_and_rearms():
    now = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
    a, tg, br = make(now, m5(now, [80.0] * 30), h1(now))
    a.real, a.real_balance, a.eq_peak = True, 240.0, 300.0          # limita: 17% sub varf = 249 $
    a.account_alarm()
    a.account_alarm()
    assert sum("Contul a coborât sub $249.00" in t for t in tg.texts) == 1
    a.real_balance = 270.0
    a.account_alarm()
    a.real_balance = 245.0
    a.account_alarm()
    assert sum("Contul a coborât" in t for t in tg.texts) == 2
