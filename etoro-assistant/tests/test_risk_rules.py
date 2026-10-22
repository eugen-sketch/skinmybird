"""Regulile de risc din studii (Eugen, 22 oct, proba pe demo): pozitia minima peste tot si un singur pariu pe dolar odata."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import CFG, fake_scan, make  # noqa: E402

import pytest  # noqa: E402

SIGS = ("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend")


@pytest.fixture(autouse=True)
def _rules_on(monkeypatch):
    monkeypatch.delenv("BOT_RISK_RULES_OFF", raising=False)


def test_every_position_is_the_minimum_size():
    a, tg, br = make()
    inst = a.inst["EURUSD"]
    assert a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001})
    plan = next(iter(a.pending.values()))
    assert plan["min_size"] is True
    amount, lev, notional = a.min_size(inst)
    assert notional < 1100                                   # ~1.010 $ expunere, cat cere eToro minim


def test_only_one_dollar_pair_at_a_time(monkeypatch):
    fake_scan(monkeypatch, {SIGS: 1})
    a, tg, br = make()
    a.unlocked = True
    a.scan()
    fx = [p["name"] for p in a.pending.values() if p["name"] in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD")]
    assert len(fx) == 1                                       # un singur pariu pe dolar, desi semnalul apare pe toate
    assert a.usd_bet_taken("GBPUSD") or fx == ["GBPUSD"]


def test_rules_can_be_turned_off():
    a, tg, br = make()
    a.cfg = {**CFG, "risk_rules": {"min_size_all": False, "one_usd_bet": False}}
    assert a.usd_bet_taken("EURUSD") is None


def test_demo_uses_the_virtual_budget_of_300_and_real_is_unchanged():
    a, tg, br = make()
    assert a.equity() == 300.0 and a.max_pos() == CFG["max_positions"]
    assert abs(a.scale() - 2.0) < 1e-9                       # limitele pe zi: de 2 ori cele de la 150 $
    b, _, _ = make()
    b.cfg = {k: v for k, v in CFG.items() if k != "demo_budget_usd"}
    assert b.equity() == CFG["budget_usd"]                   # fara setare: ca inainte
