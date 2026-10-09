import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import signals  # noqa: E402

CFG = json.loads((Path(__file__).parent.parent / "config.json").read_text())
T0 = datetime(2026, 10, 9, 8, 15, tzinfo=timezone.utc)      # vineri 08:15 UTC


class FakeTG:
    def __init__(self):
        self.sent, self.cleared, self.events, self._mid = [], [], [], 100

    def send(self, text, buttons=None):
        self._mid += 1
        self.sent.append((text, buttons, self._mid))
        return self._mid

    def clear_buttons(self, mid):
        self.cleared.append(mid)

    def answer(self, *a, **k):
        pass

    def drain(self):
        pass

    def poll(self, timeout=15):
        ev, self.events = self.events, []
        return ev

    @property
    def texts(self):
        return [t for t, _, _ in self.sent]


class FakeBroker:
    def __init__(self):
        self.prices = {"EURUSD": 1.1000, "GBPUSD": 1.3000, "USDJPY": 158.0, "AUDUSD": 0.7, "OIL": 82.0}
        self.pos, self.n, self.last, self.closed = {}, 0, {}, []

    def price(self, name):
        return self.prices[name]

    def positions(self):
        return [dict(p) for p in self.pos.values()]

    def open(self, name, side, amount, lev, sl, tp):
        self.n += 1
        pid = str(1000 + self.n)
        notional = amount * lev
        px = self.prices[name]
        self.pos[pid] = {"id": pid, "name": name, "side": side, "open_rate": px, "units": notional / px if name != "USDJPY" else notional,
                         "amount": amount, "leverage": lev, "sl": sl, "tp": tp, "time": ""}
        self.last = {"amount": amount, "leverage": lev}
        return pid

    def close(self, pid, name):
        self.closed.append(pid)
        self.pos.pop(pid, None)


def make(now=T0):
    tg, br = FakeTG(), FakeBroker()
    a = A.Assistant(CFG, tg, br, fetch=lambda *a, **k: None, now_fn=lambda: now, sleep=lambda s: None)
    return a, tg, br


def fake_scan(monkeypatch, sides):
    def scan(df, names):
        return {"side": sides.get(tuple(names), 0), "why": "a spart intervalul din noaptea asiatică", "rsi": 50.0, "price": 1.1, "bar": "bar1"}
    monkeypatch.setattr(signals, "scan", scan)


def press(a, data, mid=1):
    a.handle({"kind": "button", "id": "x", "data": data, "msg_id": mid})


def test_signal_asks_first_and_opens_nothing_without_ok(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev25"): 1})
    a.scan()
    assert not br.pos and a.pending                       # nimic deschis fara OK
    text, buttons, _ = tg.sent[0]
    assert "Semnal" in text and "Deschid?" in text and buttons[0][0][1].startswith("open:")


def test_ok_opens_with_target_and_stop(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev25"): 1})
    a.scan()
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert len(br.pos) >= 1
    pos = next(iter(br.pos.values()))
    notional = pos["amount"] * pos["leverage"]
    assert notional >= 1000 and abs((pos["tp"] - pos["open_rate"]) / pos["open_rate"] * notional - CFG["tp_usd"]) < 0.05
    assert pos["sl"] < pos["open_rate"]
    assert any("Gata, am cumpărat" in t for t in tg.texts)


def test_no_button_means_nothing_opened(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev25"): -1})
    a.scan()
    assert len(a.pending) == 3                              # maxim 3 semnale in asteptare, restul intr-un singur mesaj
    assert sum("Semnal pe" in t for t in tg.texts) == 3 and any("Mai sunt semnale" in t for t in tg.texts)
    ids = ",".join(str(k) for k in a.pending)
    press(a, f"skipall:{ids}")
    assert not br.pos and not a.pending and any("nu deschid nimic" in t for t in tg.texts)


def test_expired_signal_is_not_executed(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev25"): 1})
    a.scan()
    sid = next(iter(a.pending))
    a.now_fn = lambda: T0 + timedelta(minutes=45)
    press(a, f"open:{sid}")
    assert not br.pos and any("expirat" in t for t in tg.texts)


def test_oil_needs_big_margin_and_blocks_others(monkeypatch):
    a, tg, br = make()
    amount, lev, notional = a.sizing(a.inst["OIL"])
    assert lev == 10 and 100 <= amount <= 102 and notional >= 1000
    fake_scan(monkeypatch, {("rsi_rev20",): 1})
    a.scan()
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert a.free_margin() < 46.66        # dupa petrol nu mai incape o pozitie forex de 46.66$


def test_three_positions_basket_closes_automatically(monkeypatch):
    a, tg, br = make()
    for name in ("EURUSD", "GBPUSD", "USDJPY"):
        a.pending[len(a.pending) + 1] = {"name": name, "side": 1, "created": T0, "msg_id": 5, "amount": 46.66}
    for sid in list(a.pending):
        a.open_pending(sid)
    assert len(br.pos) == 3
    for pos in br.pos.values():                           # preturile urca => profit pe toate 3
        br.prices[pos["name"]] = pos["open_rate"] * 1.0013
    a.monitor()
    assert not br.pos and any("Țintă comună" in t for t in tg.texts)
    assert a.n_closed == 3 and a.realized > 4.0


def test_below_basket_target_nothing_closes(monkeypatch):
    a, tg, br = make()
    for name in ("EURUSD", "GBPUSD"):
        a.pending[len(a.pending) + 1] = {"name": name, "side": 1, "created": T0, "msg_id": 5, "amount": 46.66}
    for sid in list(a.pending):
        a.open_pending(sid)
    for pos in br.pos.values():
        br.prices[pos["name"]] = pos["open_rate"] * 1.0003
    a.monitor()
    assert len(br.pos) == 2 and not br.closed


def test_you_can_close_with_command_and_manual_close_is_detected(monkeypatch):
    a, tg, br = make()
    a.pending[1] = {"name": "EURUSD", "side": 1, "created": T0, "msg_id": 5, "amount": 46.66}
    a.pending[2] = {"name": "GBPUSD", "side": 1, "created": T0, "msg_id": 6, "amount": 46.66}
    a.open_pending(1)
    a.open_pending(2)
    a.handle({"kind": "text", "text": "/inchide EURUSD"})
    assert len(br.pos) == 1 and any("la cererea ta" in t for t in tg.texts)
    br.pos.clear()                                        # inchisa de tine din eToro
    a.monitor()
    assert any("ai închis-o tu" in t for t in tg.texts)


def test_status_lists_positions_with_close_buttons():
    a, tg, br = make()
    a.pending[1] = {"name": "EURUSD", "side": -1, "created": T0, "msg_id": 5, "amount": 46.66}
    a.open_pending(1)
    a.handle({"kind": "text", "text": "/status"})
    text, buttons, _ = tg.sent[-1]
    assert "Pozițiile deschise" in text and "vândut" in text and buttons[0][0][1].startswith("close:")


def test_no_scan_on_weekend_and_stop_command(monkeypatch):
    a, tg, br = make(datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc))
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev25"): 1})
    a.scan()
    assert not a.pending
    a.handle({"kind": "text", "text": "/stop"})
    assert a.stop_reason == "la cererea ta"


def test_demo_only_guard():
    import etoro
    api = etoro.EToroDemo("k", "u", verbose=False)
    try:
        api._req("POST", "/api/v1/trading/execution/market-open-orders/by-amount", body={}, trading=True)
        assert False
    except etoro.EToroError as e:
        assert "REFUZ" in str(e)
