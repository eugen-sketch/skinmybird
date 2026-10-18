"""Petrol pe 4 ore (proba aprobata de Eugen pe 18 oct): doar cumparare, doar propunere cu butoane, pozitia minima, plasa de cel mult 10 $,
fara limita de 5 ore si fara cosul comun."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import oilwatch  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG, press  # noqa: E402

NOW = datetime(2026, 10, 20, 12, 5, tzinfo=timezone.utc)            # marti, la 5 minute dupa o lumanare de 4 ore (08:00-12:00)
O = CFG["oil_4h"]


def hourly(breakout=True):
    """~120 de zile: urcare lenta (trend zilnic in sus), apoi ~6 zile pe loc, apoi ultima lumanare de 4 ore sparge in sus."""
    idx = pd.date_range(end=NOW.replace(minute=0) - timedelta(hours=1), periods=24 * 120, freq="1h")
    n = len(idx)
    c = np.linspace(60.0, 80.0, n)
    flat = n - 4 - 24 * 6
    c[flat:] = 80.0 + np.sin(np.arange(n - flat)) * 0.2
    if breakout:
        c[-4:] = [80.5, 81.0, 81.5, 82.0]
    return pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c}, index=idx)


def make(auto=False, df=None):
    tg, br = FakeTG(), FakeBroker()
    d = df if df is not None else hourly()
    br.prices["OIL"] = float(d["close"].iloc[-1])
    a = A.Assistant({**CFG, "max_positions": 4}, tg, br, fetch=lambda *x, **k: d, now_fn=lambda: NOW, sleep=lambda s: None)
    a.unlocked, a.autotrade = True, auto
    return a, tg, br


def test_signal_on_breakout_only_once_and_not_without_it():
    s = oilwatch.oil4h_signal(hourly(), NOW, O)
    assert s and s["bar_end"] == NOW.replace(minute=0) and s["px"] == 82.0
    assert oilwatch.oil4h_signal(hourly(False), NOW, O) is None
    assert oilwatch.oil4h_signal(hourly(), NOW + timedelta(hours=3), O) is None          # lumanare prea veche


def test_proposal_has_buttons_even_on_autotrade_minimum_size_and_10_usd_stop():
    a, tg, br = make(auto=True)
    a.oil4h_tick(NOW)
    assert not br.pos                                                   # nu deschide singur, nici pe autotrading
    assert any("PETROL PE 4 ORE" in t for t in tg.texts)
    sid, p = next(iter(a.pending.items()))
    assert p["side"] == 1 and p["min_size"] and abs(p["amount"] - 101.0) < 0.01 and p["special"] == "petrol4h"
    assert (p["px"] - p["sl_px"]) / p["px"] * p["notional"] <= 10.0 + 1e-6
    a.oil4h_tick(NOW + timedelta(minutes=15))                           # aceeasi lumanare: nu se repeta
    assert sum("PETROL PE 4 ORE" in t for t in tg.texts) == 1
    press(a, f"open:{sid}")
    pid = next(iter(br.pos))
    assert a.held_long(pid)


def test_held_position_skips_time_limit_and_basket():
    a, tg, br = make()
    a.oil4h_tick(NOW)
    press(a, f"open:{next(iter(a.pending))}")
    pid = next(iter(br.pos))
    a.known[pid]["opened_at"] = NOW - timedelta(hours=8)
    a.fresh_pnl = lambda p: 3.0                                        # pe plus, dupa 8 ore
    a.time_stop()
    assert pid in br.pos and not br.closed
