"""AUD/USD respins de eToro: «Requested value: 30 exceeds User MaxLeverage setting [20]». AUD/USD si NZD/USD au levier maxim 20."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import broker as B  # noqa: E402
from test_assistant import CFG, FakeBroker, fake_scan, make, press  # noqa: E402

MSG = "Ordin respins: Requested value: 30 exceeds User MaxLeverage setting [20]"


def test_audusd_and_nzdusd_are_capped_at_20_in_config():
    caps = {i["name"]: i["lev_cap"] for i in CFG["instruments"]}
    assert caps["AUDUSD"] == 20 and caps["NZDUSD"] == 20 and caps["EURUSD"] == 30 and caps["OIL"] == 10


def test_sizing_for_audusd_uses_leverage_20_and_still_meets_the_minimum_exposure():
    a, tg, br = make()
    a.inst = {"AUDUSD": a.inst["AUDUSD"]}
    m, lev, ex = a.sizing(a.inst["AUDUSD"])
    assert lev == 20 and ex >= 1000 and abs(ex - m * 20) < 0.01


class Rej(B.EToroBroker):
    """Primul ordin e respins pe levier; al doilea merge."""

    def __init__(self, first_error=MSG):
        super().__init__(None, {})
        self.calls, self.first_error = [], first_error

    def _open(self, name, side, amount, lev, sl, tp):
        self.calls.append((amount, lev))
        if len(self.calls) == 1:
            raise B.OrderRejected(self.first_error)
        return "p1"


def test_leverage_rejection_is_retried_with_the_same_margin_not_more_money():
    b = Rej()
    pid = b.open("AUDUSD", 1, 57.72, 30, 0.69, 0.70, max_amount=60.0)
    assert pid == "p1" and b.calls == [(57.72, 30), (57.72, 20)]                      # aceeasi marja, expunere mai mica (1.154 $ >= 1.000 $)
    assert b.last == {"amount": 57.72, "leverage": 20}


def test_limit_is_read_from_the_etoro_message_and_margin_grows_only_if_needed_for_the_minimum():
    b = Rej("Requested value: 30 exceeds User MaxLeverage setting [10]")
    b.open("OIL", 1, 40.0, 30, 90.0, 100.0, max_amount=500.0)
    assert b.calls[1] == (101.0, 10)                                                    # la levier 10 expunerea minima cere 101 $ marja
    c = Rej()
    with pytest.raises(B.OrderRejected):
        c.open("AUDUSD", 1, 40.0, 30, 0.69, 0.70, max_amount=45.0)                      # 50,5 $ nu incape in 45 $: respingere clara, nimic trimis a doua oara
    assert len(c.calls) == 1


def test_other_rejections_are_never_retried():
    b = Rej("Ordin respins: market closed")
    with pytest.raises(B.OrderRejected):
        b.open("AUDUSD", 1, 57.72, 30, 0.69, 0.70, max_amount=100.0)
    assert len(b.calls) == 1


class CappedBroker(FakeBroker):
    def open(self, name, side, amount, lev, sl, tp, max_amount=None):
        pid = super().open(name, side, amount, lev, sl, tp, max_amount)
        self.last = {"amount": amount, "leverage": 20}                                  # eToro a deschis la levier 20, nu 30
        return pid


def test_a_learned_leverage_limit_is_remembered_for_the_next_orders(monkeypatch):
    a, tg, br = make()
    a.broker = br = CappedBroker()
    a.inst = {"EURUSD": a.inst["EURUSD"]}
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    press(a, f"open:{next(iter(a.pending))}")
    assert a.lev_learned == {"EURUSD": 20}
    assert any("limitează" in t and "levier 20" in t for t in tg.texts)
    assert a.sizing(a.inst["EURUSD"])[1] == 20                                          # urmatorul ordin porneste direct de la 20
