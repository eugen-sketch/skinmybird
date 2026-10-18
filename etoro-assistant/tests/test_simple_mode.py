"""Modul simplu (decizia lui Eugen, 19 oct): 50 $ pe pozitie, plasa mica, tinta mare (cel putin de 3 ori plasa), fara petrol,
fara limita de 5 ore, fara cos comun, fara blocaj de profit."""
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import make, press  # noqa: E402


@pytest.fixture(autouse=True)
def simple_on(monkeypatch):
    monkeypatch.delenv("BOT_SIMPLE_OFF", raising=False)


def test_fixed_50_usd_per_position():
    a, tg, br = make()
    assert a.sizing(a.inst["EURUSD"]) == (50.0, 30, 1500.0)
    assert a.sizing(a.inst["AUDUSD"]) == (50.5, 20, 1010.0)               # minimul eToro de expunere (1.000 $ + 1%)


def test_small_stop_and_target_at_least_three_times_bigger():
    a, tg, br = make()
    tp, sl = a.pcts(1500.0, 0.001, "EURUSD")                      # miscarea obisnuita pe o ora: 0,1%
    assert abs(sl - 0.0004) < 1e-12 and abs(tp - 0.003) < 1e-12    # plasa ~0,60 $ pe 1.500 $; tinta 3x miscarea orara (~4,5 $)
    tp, sl = a.pcts(1500.0, 0.0001, "EURUSD")                     # piata foarte linistita: tinta tot de 3 ori plasa
    assert abs(tp - 3 * sl) < 1e-12
    tp, sl = a.pcts(1000.0, 0.001, "GOLD")                        # spread mare: plasa de cel putin 2 x spreadul
    assert abs(sl - 0.001) < 1e-12 and tp >= 3 * sl


def test_order_carries_small_stop_and_big_target():
    a, tg, br = make()
    a.unlocked = True
    a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001})
    press(a, "open:1")
    p = next(iter(br.pos.values()))
    assert p["amount"] == 50.0 and p["leverage"] == 30
    loss = (p["open_rate"] - p["sl"]) / p["open_rate"] * 1500
    gain = (p["tp"] - p["open_rate"]) / p["open_rate"] * 1500
    assert 0.55 < loss < 0.65 and gain >= 3 * loss


def test_no_oil_no_time_limit_no_basket_no_profit_lock():
    a, tg, br = make()
    assert a.simple_skip("OIL") and not a.simple_skip("EURUSD") and a.oil_reserve() == 0.0
    a.day, a.day_pnl = a.now_fn().strftime("%Y-%m-%d"), 999.0
    assert a.profit_locked() is False
    a.unlocked = True
    a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001})
    press(a, "open:1")
    pid = next(iter(br.pos))
    a.known[pid]["opened_at"] = a.now_fn() - timedelta(hours=9)
    a.fresh_pnl = lambda p: 3.0
    a.time_stop()
    assert pid in br.pos and not br.closed
