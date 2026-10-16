"""Regula 1 a proprietarului: nu se inchide niciodata nimic pe rosu din initiativa botului. Plus: semnale doar „adevarate” (poarta de calitate) si limita de timp doar pe plus."""
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import signals  # noqa: E402
from test_assistant import CFG, T0, make  # noqa: E402

GATE = {"enabled": True, "exclude_prefix": ["pullback"], "hours_utc": [7, 16], "adx_min": 25, "vol_min": 0.33}
GOOD = {"side": 1, "fired": ["donchian24_trend"], "bar_hour": 10, "adx": 31.0, "vol_rank": 0.7, "sig_key": "2026-10-16T10:00:00+00:00"}


def test_gate_accepts_a_clear_signal_and_says_why_it_rejects_the_others():
    assert signals.gate(GOOD, GATE) is None
    assert signals.gate({**GOOD, "fired": ["pullback50"]}, GATE)[0] == "regula"                # numai pullback: regula cea mai slaba
    assert signals.gate({**GOOD, "fired": ["pullback50", "donchian24_trend"]}, GATE) is None   # daca alta regula e de acord, trece
    assert signals.gate({**GOOD, "bar_hour": 20}, GATE)[0] == "ora"
    assert signals.gate({**GOOD, "bar_hour": 6}, GATE)[0] == "ora"
    assert signals.gate({**GOOD, "adx": 18.0}, GATE) == ("adx", "18")
    assert signals.gate({**GOOD, "vol_rank": 0.1}, GATE)[0] == "vol"
    assert signals.gate({**GOOD, "fired": [], "sig_key": "wave+1-20261016-1", "adx": 5.0}, GATE) is None   # valul nu trece pe aici (e oprit oricum)
    assert signals.gate({**GOOD, "adx": 1.0}, {**GATE, "enabled": False}) is None


def test_config_has_the_new_rules():
    assert CFG["max_hold_hours"] == 5 and CFG["time_stop_min_profit_usd"] == 0.3 and CFG["entry_gate"]["enabled"] is True
    assert CFG["entry_gate"]["adx_min"] == 25 and CFG["entry_gate"]["hours_utc"] == [7, 16] and "pullback" in CFG["entry_gate"]["exclude_prefix"]


def _scan_returns(monkeypatch, **extra):
    base = {"why": "a spart maximul", "rsi": 55.0, "price": 1.1, "bar": "2026-10-09T10:00:00+00:00", "trend": "sus", "trend4h": "sus", **GOOD, **extra}
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: dict(base))


def test_rejected_signal_is_not_proposed_and_the_report_says_why(monkeypatch):
    a, tg, br = make()
    a.inst = {"EURUSD": a.inst["EURUSD"]}
    _scan_returns(monkeypatch, adx=15.0)
    a.scan(manual=True)
    assert not a.pending and not [t for t in tg.texts if "Semnal pe" in t]
    assert "semnal respins: piața n-are direcție clară (ADX 15, minim 25)" in tg.texts[-1]


def test_accepted_signal_says_clearly_it_passed_the_checks(monkeypatch):
    a, tg, br = make()
    a.inst = {"EURUSD": a.inst["EURUSD"]}
    _scan_returns(monkeypatch)
    a.scan()
    sig = next(t for t in tg.texts if "Semnal pe" in t)
    assert "✅ Semnal verificat" in sig and "mișcare clară (ADX 31)" in sig


def _open(a, br, pid, side=1, hours_ago=6.0, open_rate=1.1000, name="EURUSD", pnl_price=1.1060):
    pos = {"id": pid, "name": name, "side": side, "open_rate": open_rate, "units": 1000.0, "amount": 55.0, "leverage": 30,
           "sl": open_rate * (1 - side * 0.01), "tp": open_rate * (1 + side * 0.01), "time": ""}
    br.pos[pid] = pos
    a.known[pid] = {**pos, "last_pnl": 0.0, "tp_usd": 2.5, "sl_usd": 7.0, "opened_at": T0 - timedelta(hours=hours_ago)}
    br.prices[name] = pnl_price


def test_time_stop_closes_only_positions_in_profit(monkeypatch):
    a, tg, br = make()
    a.now_fn = lambda: T0
    _open(a, br, "1", hours_ago=6.0, pnl_price=1.1060)                              # pe plus (+6 $), 6 ore: se inchide
    a.monitor()
    assert "1" in br.closed
    txt = [t for t in tg.texts if "limita de timp" in t]
    assert len(txt) == 1 and "am încasat profitul" in txt[0]


def test_time_stop_never_closes_a_losing_position_even_after_20_hours():
    a, tg, br = make()
    a.now_fn = lambda: T0
    _open(a, br, "1", hours_ago=20.0, pnl_price=1.0940)                             # pe minus (-6 $), 20 ore: NU se atinge
    for _ in range(3):
        a.monitor()
    assert br.closed == [] and "1" in br.pos
    assert not [t for t in tg.texts if "limita de timp" in t]


def test_time_stop_waits_for_the_limit_and_for_a_real_profit():
    a, tg, br = make()
    a.now_fn = lambda: T0
    a.cfg = {**a.cfg, "basket_target_usd": 999.0}                                   # fara tinta comuna: testam doar limita de timp
    _open(a, br, "1", hours_ago=2.0, pnl_price=1.1060)                              # pe plus, dar doar 2 ore
    _open(a, br, "2", hours_ago=7.0, pnl_price=1.1002, name="GBPUSD", open_rate=1.1000)          # 7 ore, dar profit de ~0,2 $ (sub 0,30 $)
    a.monitor()
    assert br.closed == []
    a.cfg = {**a.cfg, "max_hold_hours": 0}                                           # 0 = oprit
    br.prices["GBPUSD"] = 1.1060
    a.monitor()
    assert br.closed == []


def test_failed_time_stop_close_is_not_repeated_every_cycle():
    a, tg, br = make()
    a.now_fn = lambda: T0
    _open(a, br, "1", hours_ago=6.0, pnl_price=1.1060)

    def boom(pid, name):
        raise RuntimeError("eToro nu raspunde")
    br.close = boom
    for _ in range(4):
        a.monitor()
    assert len([t for t in tg.texts if "N-am reușit să închid" in t]) == 1           # o singura incercare in primele 10 minute
    a.now_fn = lambda: T0 + timedelta(minutes=11)
    a.monitor()
    assert len([t for t in tg.texts if "N-am reușit să închid" in t]) == 2           # dupa 10 minute reincearca


def test_shared_target_closes_only_the_positions_in_profit():
    a, tg, br = make()
    a.now_fn = lambda: T0
    _open(a, br, "1", hours_ago=1.0, pnl_price=1.1070, name="EURUSD")                # +7 $
    _open(a, br, "2", hours_ago=1.0, pnl_price=1.0990, name="GBPUSD")                # -1 $
    a.cfg = {**a.cfg, "max_hold_hours": 0}
    a.monitor()                                                                       # total +6 $ >= 4,5 $ (tinta comuna)
    assert br.closed == ["1"] and "2" in br.pos                                       # doar cea pe plus; cea pe minus ramane
    msg_ = next(t for t in tg.texts if "Țintă comună" in t)
    assert "rămân deschise" in msg_ and "nu închid niciodată pe minus" in msg_
