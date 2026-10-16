"""T004: verificarea pretului inainte de ordin (preturi vechi => tinte gresite pe 14-15.10) si planul/realul fiecarei pozitii salvat."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import telegram_bot  # noqa: E402
from test_assistant import fake_scan, make, press  # noqa: E402

SIGS = {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1}


def _pending(monkeypatch):
    a, tg, br = make()
    a.inst = {"EURUSD": a.inst["EURUSD"]}
    fake_scan(monkeypatch, SIGS)
    a.scan()
    return a, tg, br, next(iter(a.pending))


def test_order_is_not_sent_when_the_etoro_price_does_not_match_the_hourly_candle(monkeypatch):
    a, tg, br, sid = _pending(monkeypatch)
    br.prices["EURUSD"] = 1.1000                                                     # lumanarea orara (la zi)
    br.quotes = lambda names: {n: {"bid": 1.1099, "ask": 1.1100} for n in names}     # cotatia „live”: 0,9% mai sus => pret nesigur
    press(a, f"open:{sid}")
    assert not br.pos and not a.known
    assert any("Nu deschid" in t and "nu se potrivește cu lumânarea orară" in t for t in tg.texts)
    assert "EURUSD" not in a.seen_bar                                                # semnalul se poate relua la urmatoarea scanare


def test_order_is_sent_when_the_prices_agree(monkeypatch):
    a, tg, br, sid = _pending(monkeypatch)
    br.prices["EURUSD"] = 1.1000
    br.quotes = lambda names: {n: {"bid": 1.1000, "ask": 1.1001} for n in names}     # 0,01%: in regula
    press(a, f"open:{sid}")
    assert len(br.pos) == 1 and not any("Nu deschid" in t for t in tg.texts)


def test_price_check_never_blocks_when_the_candle_cannot_be_read(monkeypatch):
    a, tg, br, sid = _pending(monkeypatch)
    br.quotes = lambda names: {n: {"bid": 1.2, "ask": 1.2} for n in names}
    def boom(name):
        raise RuntimeError("fara lumanare")
    br.price = boom
    assert a.price_mismatch("EURUSD", 1.2, 0.001) is None                           # fara a doua sursa nu blocam (comportament de pana acum)


def test_plan_and_real_are_saved_per_position_and_logged_on_close(monkeypatch):
    events = []
    monkeypatch.setattr(telegram_bot, "HOOKS", [lambda kind, text, buttons=None: events.append((kind, text))])
    a, tg, br, sid = _pending(monkeypatch)
    press(a, f"open:{sid}")
    pid = next(iter(a.known))
    plan = a.plans[pid]
    assert plan["tp_usd"] > 0 and plan["sl_usd"] > 0 and plan["px_plan"] == 1.1                # planul: pret, tinta, plasa
    pos = br.pos[pid]
    pos["tp"] = pos["open_rate"] * 1.0003                                                       # eToro a pus o tinta mult mai mica decat planul
    a.monitor()
    assert plan["real"]["tp_usd"] < plan["tp_usd"] / 2 and plan["real"]["open"] == pos["open_rate"]
    import state
    state.save({"plans": a.plans}, a.__class__ and Path(__file__).parent / "_tmp_state.json")
    assert state.load(Path(__file__).parent / "_tmp_state.json")["plans"][pid]["real"]["tp_usd"] == plan["real"]["tp_usd"]
    (Path(__file__).parent / "_tmp_state.json").unlink()
    br.pos.clear()                                                                              # se inchide pe eToro
    a.monitor()
    a.monitor()
    assert pid not in a.plans                                                                   # planul se sterge la inchidere
    kinds = [t for k, t in events if k == "ev"]
    assert any(t.startswith("deschis EURUSD") for t in kinds) and any(t.startswith("inchis EURUSD") and "plan/real" in t for t in kinds)
