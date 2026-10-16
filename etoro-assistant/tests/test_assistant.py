import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import signals  # noqa: E402

CFG = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
T0 = datetime(2026, 10, 9, 8, 15, tzinfo=timezone.utc)      # vineri 08:15 UTC


class FakeTG:
    def __init__(self):
        self.sent, self.cleared, self.events, self._mid = [], [], [], 100

    def send(self, text, buttons=None, menu=None, silent=False):
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

    def positions(self, fresh=False):
        return [dict(p) for p in self.pos.values()]

    def open(self, name, side, amount, lev, sl, tp, max_amount=None):
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
    def scan(df, names, now=None, *wa):
        return {"side": sides.get(tuple(names), 0), "why": "a spart intervalul din noaptea asiatică", "rsi": 50.0, "price": 1.1, "bar": "bar1"}
    monkeypatch.setattr(signals, "scan", scan)


def press(a, data, mid=1):
    a.handle({"kind": "button", "id": "x", "data": data, "msg_id": mid})


def test_signal_asks_first_and_opens_nothing_without_ok(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    assert not br.pos and a.pending                       # nimic deschis fara OK
    text, buttons, _ = tg.sent[0]
    assert "Semnal" in text and "Deschid?" in text and buttons[0][0][1].startswith("open:")


def test_ok_opens_with_target_and_stop(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
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
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): -1})
    a.scan()
    assert len(a.pending) == 3                              # maxim 3 semnale in asteptare, restul intr-un singur mesaj
    assert sum("Semnal pe" in t for t in tg.texts) == 3 and any("Mai sunt semnale" in t for t in tg.texts)
    ids = ",".join(str(k) for k in a.pending)
    press(a, f"skipall:{ids}")
    assert not br.pos and not a.pending and any("nu deschid nimic" in t for t in tg.texts)


def test_expired_signal_is_not_executed(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    sid = next(iter(a.pending))
    a.now_fn = lambda: T0 + timedelta(minutes=45)
    press(a, f"open:{sid}")
    assert not br.pos and any("expirat" in t for t in tg.texts)


def test_oil_needs_big_margin_and_blocks_others(monkeypatch):
    a, tg, br = make()
    amount, lev, notional = a.sizing(a.inst["OIL"])
    assert lev == 10 and 100 <= amount <= 102 and notional >= 1000
    fake_scan(monkeypatch, {("rsi_rev25", "pullback45", "donchian24_trend"): 1})
    a.scan()
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert a.free_margin() < 2 * a.sizing(a.inst["EURUSD"])[0]    # dupa petrol nu mai incap doua pozitii forex


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
    assert not any("ai închis-o tu" in t for t in tg.texts)      # o singura citire fara ea: poate fi o eroare a API-ului, mai astept
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
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
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


def test_menu_buttons_work_and_close_all_asks_for_confirmation():
    a, tg, br = make()
    a.pending[1] = {"name": "EURUSD", "side": 1, "created": T0, "msg_id": 5, "amount": 46.66}
    a.open_pending(1)
    a.handle({"kind": "text", "text": "📊 Status"})
    assert "Pozițiile deschise" in tg.texts[-1]
    a.handle({"kind": "text", "text": "🔒 Închide tot"})
    text, buttons, _ = tg.sent[-1]
    assert "Sigur închid" in text and br.pos                      # inca nimic inchis, doar intrebare
    press(a, "closeall")
    assert not br.pos
    a.handle({"kind": "text", "text": "⛔ Oprește"})
    assert "Sigur mă opresc" in tg.texts[-1] and a.stop_reason is None
    press(a, "cancel")
    assert a.stop_reason is None
    a.handle({"kind": "text", "text": "🔎 Caută semnale"})
    a.handle({"kind": "text", "text": "❓ Ajutor"})
    assert "Ce pot face" in tg.texts[-1]
    press(a, "stopnow")
    assert a.stop_reason == "la cererea ta"


def test_manual_scan_explains_what_it_checked(monkeypatch):
    a, tg, br = make()
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"side": 0, "why": "", "rsi": 61.0, "price": 1.1, "bar": "2026-10-09T07:00:00+00:00",
                                                           "asia_pos": "în interior", "n_bars": 700})
    a.scan(manual=True)
    text = tg.texts[-1]
    assert "Scanare" in text and "EUR/USD 61" in text and "Cel mai aproape" in text and "10:00–11:00" in text      # raport scurt, o linie pentru toate
    assert "HOLD" in text and "Semnale active" not in text                                                      # fara semnal activ: HOLD


def test_scan_counter_and_heartbeat_text(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {})
    a.scan()
    a.scan()
    assert a.scans == 2 and a.last_scan == "11:15"
    import messages
    t = messages.heartbeat("09:15", a.scans, a.last_scan, 1, True)
    assert "sunt activ" in t and "2 scanări" in t and "11:15" in t and "1 poziții" in t
    assert "piața e închisă" in messages.heartbeat("22:00", 5, "21:45", 0, False)


def test_scanner_ignores_forming_hour_and_live_tick_bar():
    import pandas as pd
    import signals as sg
    now = pd.Timestamp("2026-10-09 08:07:51", tz="UTC")
    idx = list(pd.date_range("2026-10-09 05:00", "2026-10-09 08:00", freq="h", tz="UTC")) + [now]   # ...07:00, 08:00 (in formare), 08:07:51 (live)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    done = sg.completed(df, now)
    assert str(done.index[-1]) == "2026-10-09 07:00:00+00:00"          # ultima ora INCHEIATA e 07:00, nu 08:00
    exactly = sg.completed(df, pd.Timestamp("2026-10-09 09:00:00", tz="UTC"))
    assert str(exactly.index[-1]) == "2026-10-09 08:00:00+00:00"       # la 09:00 fix, ora de 08:00 s-a incheiat


def test_long_sessions_are_chained_in_two_runs():
    assert A.plan_session(8) == (5.5, 2.5)
    assert A.plan_session(5) == (5, 0)
    this, rest = A.plan_session(10)
    assert this == 5.5 and abs(rest - 4.5) < 1e-9


def test_unanswered_signal_is_repeated_until_answered(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    sid = next(iter(a.pending))
    n0 = len(tg.texts)
    a.now_fn = lambda: T0 + timedelta(minutes=2)
    a.remind_pending()
    assert len(tg.texts) == n0                       # prea devreme
    for m in (4, 8, 12, 16, 20, 24, 27):
        a.now_fn = lambda m=m: T0 + timedelta(minutes=m)
        a.remind_pending()
    reminders = [t for t in tg.texts if "Aștept încă" in t and "EUR/USD" in t]
    assert len(reminders) == 6                       # maxim 6, apoi se opresc
    press(a, f"open:{sid}")
    assert br.pos                                    # raspunsul OK deschide in continuare


def test_radar_is_rare_and_silent(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {})
    a.scan()
    assert sum("Radar" in x for x in tg.texts) == 1              # primul radar
    a.now_fn = lambda: T0 + timedelta(minutes=60)
    a.scan()
    assert sum("Radar" in x for x in tg.texts) == 1              # nu se repeta la fiecare ora
    a.now_fn = lambda: T0 + timedelta(hours=4)
    a.scan()
    assert sum("Radar" in x for x in tg.texts) == 2              # abia dupa 4 ore
    assert not any("Am scanat acum" in x for x in tg.texts)


def test_wave_signal_rides_a_big_move():
    import pandas as pd, numpy as np
    idx = pd.date_range("2026-10-01", periods=300, freq="1h", tz="UTC")
    rng = np.random.default_rng(1)
    c = 100 + np.cumsum(rng.normal(0, 0.2, 300))
    df = pd.DataFrame({"open": c, "high": c + 0.15, "low": c - 0.15, "close": c, "volume": 1}, index=idx)
    now = idx[-1] + pd.Timedelta(minutes=10)
    done = signals.completed(df, now)
    w, mv = signals.wave(df, done, "lateral")
    assert w == 0
    df2 = df.copy()
    df2.iloc[-1, df2.columns.get_loc("close")] += 0.5               # salt mare in sus pe ora in curs
    w, mv = signals.wave(df2, signals.completed(df2, now), "lateral")
    assert w == 1 and mv > 1.6
    assert signals.wave(df2, signals.completed(df2, now), "jos")[0] == 0     # nu mergem impotriva trendului


def test_progressive_budget_grows_with_profit_and_shrinks_with_loss():
    a, tg, br = make()
    base = a.sizing(a.inst["EURUSD"])[0]
    assert abs(base - 50.0) < 0.01                       # 150 / 3
    a.add_realized(+10.0)
    assert abs(a.sizing(a.inst["EURUSD"])[0] - 53.33) < 0.01    # 160 / 3
    a.add_realized(-200.0)
    assert a.equity() == 75.0                            # minim 50% din bugetul de baza


def test_atr_levels_small_tp_wide_sl_clamped():
    a, tg, br = make()
    notional = 1500.0
    sl, tp, tp_usd, sl_usd = a.levels(1, 1.1, notional, atr_pct=0.0012)
    assert 2.25 <= tp_usd <= 6.0 and sl_usd > tp_usd and sl < 1.1 < tp
    _, _, tp_big, sl_big = a.levels(1, 1.1, notional, atr_pct=0.05)       # volatilitate uriasa: limitat in $
    assert tp_big <= 6.0 + 1e-9 and sl_big <= 20.0 + 1e-9


def test_autotrade_opens_without_asking_and_stops_at_daily_loss(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.handle({"kind": "text", "text": "🤖 Autotrading"})
    assert not a.autotrade and any("Pornesc autotrading" in x for x in tg.texts)         # cere confirmare
    press(a, "autoon")
    assert a.autotrade
    a.scan()
    assert br.pos and any("Autotrading:" in x for x in tg.texts)                          # a deschis singur
    assert not any("Deschid?" in x for x in tg.texts)
    # pierdere zilnica mare: se opreste din deschis
    a2, tg2, br2 = make()
    a2.autotrade = True
    a2.add_realized(-16.0)
    a2.scan()
    assert not a2.autotrade and not br2.pos and any("am oprit autotrading" in x.lower() for x in tg2.texts)


def test_hold_alert_after_two_hours(monkeypatch):
    a, tg, br = make()
    fake_scan(monkeypatch, {("rsi_rev25", "pullback45", "donchian24_trend"): 1})
    a.scan()
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert br.pos
    a.now_fn = lambda: T0 + timedelta(minutes=125)
    a.monitor()
    assert not any("deschisă de" in x and "ore" in x for x in tg.texts)                      # alerta vine abia dupa 5 ore (hold_alert_min=300)
    a.now_fn = lambda: T0 + timedelta(minutes=305)
    br.prices["OIL"] = 82.0 + 0.0
    a.monitor()
    assert any("nu și-a atins încă ținta" in x or "acum pe minus" in x for x in tg.texts)
    n = sum(("nu și-a atins încă ținta" in x or "acum pe minus" in x) for x in tg.texts)
    a.monitor()
    assert sum(("nu și-a atins încă ținta" in x or "acum pe minus" in x) for x in tg.texts) == n          # o singura data


def test_state_roundtrip(tmp_path):
    import state
    p = tmp_path / "s.json"
    state.save({"realized": 12.5, "autotrade": True}, p)
    assert "12.5" not in p.read_text(encoding="utf-8") and state.load(p) == {"realized": 12.5, "autotrade": True}
    assert state.load(tmp_path / "missing") == {}


def test_stale_bar_never_becomes_a_signal(monkeypatch):
    a, tg, br = make()
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"side": 1, "why": "x", "rsi": 20.0, "price": 1.1, "bar": "2026-10-08T15:00:00+00:00",
                                                                     "age_min": 900.0, "atr_pct": 0.001, "trend": "sus"})
    a.scan()
    assert not a.pending and not br.pos                    # ultima bara are 15 ore: nu se propune nimic


def test_index_outside_its_hours_is_skipped(monkeypatch):
    a, tg, br = make()                                      # 08:15 UTC: indicii americani nu sunt in program
    calls = []

    def scan(df, names, now=None, *wa):
        calls.append(names)
        return {"side": 0, "why": "", "rsi": 50.0, "price": 1.1, "bar": "2026-10-09T07:00:00+00:00", "age_min": 15.0}
    monkeypatch.setattr(signals, "scan", scan)
    a.scan(manual=True)
    text = tg.texts[-1]
    assert "în afara programului" in text and "S&P 500" not in text.split("•")[0]
    assert len(calls) == 10                                  # 13 instrumente - 3 indici americani


def test_real_scan_reports_bar_age_and_atr():
    import numpy as np
    import pandas as pd
    idx = pd.date_range("2026-09-01", periods=800, freq="h", tz="UTC")
    c = 100 + np.cumsum(np.random.default_rng(5).normal(0, 0.1, 800))
    df = pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c}, index=idx)
    now = idx[-1] + pd.Timedelta(minutes=70)
    s = signals.scan(df, ["rsi_rev25"], now)
    assert s["bar"].startswith(str(idx[-1].date())) and abs(s["age_min"] - 10) < 1 and 0 < s["atr_pct"] < 0.05
    s2 = signals.scan(df, ["rsi_rev25"], idx[-1] + pd.Timedelta(hours=30))
    assert s2["age_min"] > 1000


def test_signal_fires_only_on_new_condition():
    import pandas as pd
    s = pd.Series([0, 0, 1, 1, 1, 0, -1, -1])
    assert [signals.edge(s.iloc[:i]) for i in range(2, 9)] == [0, 1, 0, 0, 0, -1, 0]


def test_three_index_positions_fit_in_150():
    a, tg, br = make()
    m, lev, notional = a.sizing(a.inst["SPX500"])
    assert lev == 20 and notional >= 1000
    for _ in range(3):
        assert a.free_margin() >= m
        a.known[str(len(a.known))] = {"amount": m, "name": "SPX500", "side": 1}


def test_ger40_pnl_converted_from_eur_to_usd():
    a, tg, br = make()
    a.eurusd = 1.10
    pos = {"name": "GER40", "side": 1, "units": 1.0, "open_rate": 24000.0, "amount": 50.0, "leverage": 20}
    assert abs(a.pnl(pos, 24010.0) - (10 * 1.10 - 0.05 / 2 / 100 * 1000)) < 1e-6


def test_vanished_position_booked_at_target_not_at_stale_reading():
    a, tg, br = make()
    old = {"name": "EURUSD", "side": 1, "tp": 1.1010, "sl": 1.0940, "tp_usd": 2.5, "sl_usd": 8.0, "last_pnl": 0.3}
    br.prices["EURUSD"] = 1.1012                          # pretul a trecut de TP intre doua verificari
    assert a.classify_vanished(old, 0.3) == ("TP", 2.5)
    br.prices["EURUSD"] = 1.0930                          # sub SL
    assert a.classify_vanished(old, -0.5) == ("SL", -8.0)
    br.prices["EURUSD"] = 1.1000                          # pretul in interior: a inchis-o altcineva
    assert a.classify_vanished(old, 0.3) == ("OTHER", 0.3)


def test_seen_bars_survive_a_restart(monkeypatch):
    import state
    a, tg, br = make()
    a.seen_bar = {"EURUSD": "bar1"}
    a.realized = 5.0
    a.save_state()
    st = state.load()
    assert st["seen"] == {"EURUSD": "bar1"} and st["realized"] == 5.0


# ---------------------------------------------------------------- modul REAL
def test_etoro_paths_demo_vs_real(monkeypatch):
    import etoro
    seen = []

    class R:
        status_code, text = 200, "{}"

        def json(self):
            return {}
    monkeypatch.setattr(etoro.requests, "request", lambda m, url, **k: (seen.append(url), R())[1])
    demo = etoro.EToroDemo("k", "u")
    demo.portfolio()
    assert "/demo/" in seen[-1]
    real = etoro.EToroDemo("k", "u", real=True)
    real.portfolio()
    real.close_position(1, 2)
    assert all("/demo" not in u for u in seen[-2:]) and seen[-2].endswith("/api/v1/trading/info/portfolio")
    import pytest
    with pytest.raises(etoro.EToroError):
        real._req("GET", "/api/v1/trading/info/demo/portfolio", trading=True)       # real refuza caile demo
    with pytest.raises(etoro.EToroError):
        demo._req("GET", "/api/v1/trading/info/portfolio", trading=True)            # demo refuza caile nedemo


def test_real_keys_are_separate_from_demo_keys(monkeypatch):
    import etoro
    monkeypatch.setenv("ETORO_API_KEY", "demo")
    monkeypatch.setenv("ETORO_USER_KEY", "demo")
    monkeypatch.delenv("ETORO_REAL_API_KEY", raising=False)
    monkeypatch.delenv("ETORO_REAL_USER_KEY", raising=False)
    import pytest
    with pytest.raises(etoro.EToroError):
        etoro.EToroDemo(real=True)                       # cheile demo nu pot fi folosite pe real


class RealBroker(FakeBroker):
    """Ca eToro: soldul liber scade cu marja pozitiilor deschise."""

    def __init__(self, balance):
        super().__init__()
        self.balance = balance

    def credit(self):
        return self.balance - sum(p["amount"] for p in self.pos.values())


def make_real(balance, now=T0):
    tg, br = FakeTG(), RealBroker(balance)
    a = A.Assistant(CFG, tg, br, fetch=lambda *a, **k: None, now_fn=lambda: now, sleep=lambda s: None, real=True)
    a.refresh_real()
    return a, tg, br


def test_real_is_locked_until_confirmed(monkeypatch):
    a, tg, br = make_real(500.0)
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    assert not a.pending and not br.pos                  # blocat: nu propune nimic
    a.handle({"kind": "text", "text": "🤖 Autotrading"})
    assert any("confirmă contul real" in x for x in tg.texts) and not a.autotrade
    press(a, "realok")
    assert a.unlocked
    a.seen_bar.clear()
    a.scan()
    assert a.pending                                    # dupa confirmare propune, tot cu OK
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert br.pos and any("CONT REAL" in x for x in tg.texts)


def test_real_budget_has_no_cap_and_limits_scale():
    small, _, _ = make_real(150.0)
    big, _, _ = make_real(3000.0)
    assert abs(big.equity() - 3000.0) < 1e-6 and abs(small.equity() - 150.0) < 1e-6
    m_small = small.sizing(small.inst["EURUSD"])[0]
    m_big = big.sizing(big.inst["EURUSD"])[0]
    assert abs(m_big - 1000.0) < 0.01 and m_big / m_small > 19          # 3000/3 vs 150/3, fara plafon
    _, _, tp_s, sl_s = small.levels(1, 1.1, small.sizing(small.inst["EURUSD"])[2], atr_pct=0.0008)
    _, _, tp_b, sl_b = big.levels(1, 1.1, big.sizing(big.inst["EURUSD"])[2], atr_pct=0.0008)
    assert abs(tp_b / tp_s - 20) < 0.5 and abs(sl_b / sl_s - 20) < 0.5   # aceleasi procente, sume proportionale


def test_real_only_tracks_positions_opened_by_the_bot(monkeypatch):
    a, tg, br = make_real(1500.0)
    a.unlocked = True
    br.pos["999"] = {"id": "999", "name": "GOLD", "side": 1, "open_rate": 4000.0, "units": 5.0, "amount": 400.0, "leverage": 1,
                     "sl": 0, "tp": 0, "time": ""}                      # investitia ta personala, nu a botului
    br.prices["GOLD"] = 4200.0
    a.monitor()
    assert "999" not in a.known                          # nu o ating si nu o includ in cos
    a.close_all = None
    fake_scan(monkeypatch, {("rsi_rev25", "pullback45", "donchian24_trend"): 1})
    a.scan()
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert len(a.bot_pids) == 1 and next(iter(a.bot_pids)) in a.known


def test_min_50_per_position_and_two_positions_below_150():
    a, _, _ = make_real(45.0)                                  # sub 50$: eToro nu permite nicio pozitie
    m, lev, n = a.sizing(a.inst["NZDUSD"])
    assert a.free_margin() < m and m >= 50.0
    b, _, _ = make_real(60.0)                                  # 60$: o singura pozitie, cu tot ce ai
    assert b.max_pos() == 2 and abs(b.sizing(b.inst["NZDUSD"])[0] - 60.0) < 0.01
    c, _, _ = make_real(120.0)                                 # 120$: doua pozitii de cate 60$
    assert c.max_pos() == 2 and abs(c.sizing(c.inst["NZDUSD"])[0] - 60.0) < 0.01
    d, _, _ = make_real(150.0)                                 # 150$: trei pozitii de cate 50$
    assert d.max_pos() == 3 and abs(d.sizing(d.inst["NZDUSD"])[0] - 50.0) < 0.01
    e, _, _ = make_real(100.0)                                 # 100$: doua de cate 50$
    assert abs(e.sizing(e.inst["NZDUSD"])[0] - 50.0) < 0.01


def test_second_position_uses_remaining_money_and_third_is_refused_under_150():
    a, tg, br = make_real(120.0)
    a.unlocked = True
    for name in ("EURUSD", "GBPUSD"):
        m, lev, notional = a.sizing(a.inst[name])
        a.known[name] = {"amount": m, "name": name, "side": 1, "leverage": lev}
        a.real_balance = 120.0 - sum(p["amount"] for p in a.known.values())
    assert len(a.known) == 2 and a.max_pos() == 2
    br.balance = a.real_balance


def test_below_minimum_signal_message_explains_the_50_rule(monkeypatch):
    a, tg, br = make_real(30.0)
    a.unlocked = True
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a.scan()
    assert any("eToro cere minim $50.00" in x for x in tg.texts) and not a.pending


def test_manual_sell_asks_with_buttons_and_opens(monkeypatch):
    a, tg, br = make_real(60.0)
    br.prices["NZDUSD"] = 0.56
    a.unlocked = True
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"side": 0, "why": "", "rsi": 50.0, "price": 0.56, "bar": "b",
                                                                     "age_min": 5.0, "atr_pct": 0.0009})
    a.handle({"kind": "text", "text": "vinde nzdusd"})
    text, buttons, _ = tg.sent[-1]
    assert "VÂND" in text and "Deschid?" in text and buttons[0][0][1].startswith("open:")
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    pos = next(iter(br.pos.values()))
    assert pos["side"] == -1 and pos["amount"] <= 60.0 and pos["amount"] * pos["leverage"] >= 1000 and pos["tp"] < pos["open_rate"] < pos["sl"]


def test_manual_command_names_and_lock():
    a, tg, br = make_real(60.0)
    assert a.resolve_name("nzd/usd") == "NZDUSD" and a.resolve_name("aur") == "GOLD" and a.resolve_name("dax") == "GER40"
    assert a.resolve_name("xyz") is None
    a.handle({"kind": "text", "text": "cumpără eurusd"})
    assert any("confirmă contul real" in x for x in tg.texts) and not a.pending        # blocat pana confirmi


def test_unconfirmed_order_is_never_repeated(monkeypatch):
    import broker as B
    monkeypatch.setattr(B.time, "sleep", lambda s: None)

    class Api:
        def __init__(self):
            self.opened, self.pos = 0, []

        def positions(self, fresh=False):
            return self.pos

        def open_market(self, *a, **k):
            self.opened += 1
            return {"orderForOpen": {"orderID": 77}}

        def order_status(self, oid):
            return {"statusID": 1}
    api = Api()
    br = B.EToroBroker(api, {"NZDUSD": 3})
    import pytest
    with pytest.raises(B.OrderUnconfirmed):
        br.open("NZDUSD", -1, 47.67, 30, 0.562, 0.559)
    assert api.opened == 1                                   # nicio reincercare cu levier 20 (risc de ordin dublu)
    assert B.EToroBroker._order_id({"a": {"orderID": 9}}) == "9"


def test_unconfirmed_order_gets_adopted_when_it_appears(monkeypatch):
    import broker as B
    a, tg, br = make_real(80.0)
    a.unlocked = True
    br.prices["NZDUSD"] = 0.56
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"side": 0, "why": "", "rsi": 50.0, "price": 0.56, "bar": "b",
                                                                     "age_min": 5.0, "atr_pct": 0.0009})
    orig = br.open

    def failing_open(*args, **kw):
        orig(*args, **kw)                                    # ordinul ajunge la eToro...
        raise B.OrderUnconfirmed("nevazut", set(), {"orderId": 1})      # ...dar nu e confirmat in timp
    br.open = failing_open
    a.handle({"kind": "text", "text": "vinde nzdusd"})
    sid = next(iter(a.pending))
    press(a, f"open:{sid}")
    assert any("NU repet" in x for x in tg.texts) and len(a.adopt) == 1
    a.monitor()                                              # pozitia exista deja in portofoliu
    assert not a.adopt and len(a.bot_pids) == 1 and any("a apărut în eToro" in x for x in tg.texts)


def test_adopt_existing_position_by_command():
    a, tg, br = make_real(80.0)
    a.unlocked = True
    br.pos["555"] = {"id": "555", "name": "NZDUSD", "side": -1, "open_rate": 0.56, "units": 2500.0, "amount": 47.0, "leverage": 30,
                     "sl": 0.5625, "tp": 0.5595, "time": ""}
    br.prices["NZDUSD"] = 0.56
    a.handle({"kind": "text", "text": "preia nzdusd"})
    assert "555" in a.bot_pids and "555" in a.known and any("Am preluat 1" in x for x in tg.texts)
    a.handle({"kind": "text", "text": "preia nzdusd"})
    assert any("nu găsesc" in x.lower() or "Nu găsesc" in x for x in tg.texts)         # a doua oara: o urmaresc deja


def test_status_shows_zero_free_when_cash_is_fully_used():
    """Scenariul real: 146.4$ in cont, doua pozitii de ~73$ -> in eToro nu mai e cash; Status trebuie sa arate 0 liber, nu 72$."""
    a, tg, br = make_real(146.4)
    a.unlocked = True
    assert a.max_pos() == 2
    for name in ("GBPUSD", "USDCAD"):
        br.prices.setdefault(name, 1.3)
        a.propose(name, {"side": -1 if name == "GBPUSD" else 1, "why": "test", "price": 1.3, "atr_pct": 0.0008})
    for sid in list(a.pending):
        press(a, f"open:{sid}")
    assert len(br.pos) == 2 and abs(sum(p["amount"] for p in br.pos.values()) - 146.4) < 0.05
    a.status()
    text = tg.texts[-1]
    assert "Buget liber: $0.00" in text and "$146.4" in text and "218" not in text
    assert abs(a.free_margin()) < 0.1 and abs(a.equity() - 146.4) < 0.1


class _Api:
    """eToro fals pentru testele de ordine."""

    def __init__(self, post_error=None, status=None):
        self.post_error, self.status, self.opened, self.calls, self.pos = post_error, status, [], 0, []

    def positions(self, fresh=False):
        self.calls += 1
        return self.pos

    def open_market(self, iid, buy, amount, lev, sl, tp):
        self.opened.append((amount, lev))
        if self.post_error:
            raise self.post_error
        return {"orderId": 5}

    def order_status(self, oid):
        return self.status or {"statusID": 1}


def _broker(api, monkeypatch):
    import broker as B
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    return B, B.EToroBroker(api, {"NZDUSD": 3})


def test_network_error_on_order_is_unconfirmed_not_retried(monkeypatch):
    import etoro
    api = _Api(post_error=etoro.EToroNetworkError("POST x: ReadTimeout"))
    B, br = _broker(api, monkeypatch)
    import pytest
    with pytest.raises(B.OrderUnconfirmed):
        br.open("NZDUSD", -1, 73.0, 30, 0.562, 0.559)
    assert len(api.opened) == 1                                   # un singur ordin, fara reincercare cu levier 20


def test_server_error_is_unconfirmed_but_client_error_is_a_clean_rejection(monkeypatch):
    import etoro
    B, br = _broker(_Api(post_error=etoro.EToroHTTPError("POST x -> 503", 503)), monkeypatch)
    import pytest
    with pytest.raises(B.OrderUnconfirmed):
        br.open("NZDUSD", -1, 73.0, 30, 0.562, 0.559)
    api = _Api(post_error=etoro.EToroHTTPError("POST x -> 400: insufficient funds", 400))
    B, br = _broker(api, monkeypatch)
    with pytest.raises(B.OrderRejected):
        br.open("NZDUSD", -1, 73.0, 30, 0.562, 0.559)
    assert len(api.opened) == 1                                   # respingere care nu tine de levier: nu se reincearca


def test_leverage_retry_only_for_leverage_rejection_and_within_free_money(monkeypatch):
    import etoro
    api = _Api(post_error=etoro.EToroHTTPError("POST x -> 400: leverage 30 not allowed", 400))
    B, br = _broker(api, monkeypatch)
    import pytest
    with pytest.raises(B.OrderRejected) as ei:
        br.open("NZDUSD", -1, 73.0, 30, 0.562, 0.559, max_amount=80.0)       # lev 20 ar cere 109.5$ > 80$ liber
    assert len(api.opened) == 1 and "peste banii liberi" in str(ei.value)


def test_read_errors_while_waiting_for_the_fill_do_not_crash_into_a_retry(monkeypatch):
    import etoro
    api = _Api()
    calls = {"n": 0}
    orig = api.positions

    def flaky(fresh=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return []
        raise etoro.EToroHTTPError("GET portfolio -> 429", 429)
    api.positions = flaky
    B, br = _broker(api, monkeypatch)
    import pytest
    with pytest.raises(B.OrderUnconfirmed):
        br.open("NZDUSD", -1, 73.0, 30, 0.562, 0.559)
    assert len(api.opened) == 1


def test_empty_portfolio_glitch_does_not_drop_tracked_positions():
    a, tg, br = make_real(150.0)
    a.unlocked = True
    br.pos["1"] = {"id": "1", "name": "GBPUSD", "side": -1, "open_rate": 1.3, "units": 1000.0, "amount": 75.0, "leverage": 30,
                   "sl": 1.31, "tp": 1.29, "time": ""}
    a.bot_pids.add("1")
    a.monitor()
    assert "1" in a.known
    saved = dict(br.pos)
    br.pos.clear()                                        # raspuns gol (eroare API), pozitia exista de fapt
    a.monitor()
    assert "1" in a.known and "1" in a.bot_pids and not any("închisă" in x for x in tg.texts)
    br.pos.update(saved)                                  # apare la loc
    a.monitor()
    assert "1" in a.known and a.miss == {}


def test_manual_close_in_etoro_is_booked_at_current_profit_not_at_target():
    a, tg, br = make()
    old = {"name": "EURUSD", "side": 1, "tp": 1.1050, "sl": 1.0900, "tp_usd": 2.75, "sl_usd": 6.0, "last_pnl": 1.8,
           "units": 1000.0, "open_rate": 1.1000, "amount": 40.0, "leverage": 30}
    br.prices["EURUSD"] = 1.1018                          # sub TP: inchisa de mana la +1.8$ aprox.
    kind, pnl = a.classify_vanished(old, 1.8)
    assert kind == "OTHER" and abs(pnl - 1.8) < 0.6      # nu "TP cu 2.75$"
    br.prices["EURUSD"] = 1.1060
    assert a.classify_vanished(old, 1.8) == ("TP", 2.75)


def test_order_sanity_blocks_wrong_side_levels():
    a, _, _ = make()
    assert a.order_problem(1, 1.1, 1.09, 1.11) is None
    assert a.order_problem(-1, 1.1, 1.11, 1.09) is None
    assert a.order_problem(1, 1.1, 1.11, 1.09) is not None             # SL peste pret la o cumparare
    assert a.order_problem(-1, 1.1, 1.09, 1.11) is not None            # SL sub pret la o vanzare
    assert a.order_problem(1, 1.1, 1.0999, 1.1001) is not None         # prea aproape de pret


def test_live_quotes_pnl_matches_etoro_formula():
    a, _, _ = make()
    # USDCAD cumparat: unitati = USD, iesire la bid, conversie CAD->USD 0.7010
    pos = {"name": "USDCAD", "side": 1, "units": 2180.0, "open_rate": 1.42600}
    q = {"bid": 1.42649, "ask": 1.42650, "conv_bid": 0.7010, "conv_ask": 0.7010}
    assert abs(a.quote_pnl(pos, q) - 2180 * (1.42649 - 1.426) * 0.7010) < 1e-9
    short = {"name": "GBPUSD", "side": -1, "units": 1700.0, "open_rate": 1.3240}
    q2 = {"bid": 1.32296, "ask": 1.32299, "conv_bid": 1.0, "conv_ask": 1.0}
    assert abs(a.quote_pnl(short, q2) - (-1) * 1700 * (1.32299 - 1.3240)) < 1e-9          # iesire la ask


def test_full_loop_runs_on_real_with_existing_position_and_reports_correct_budget(monkeypatch):
    """Simulare a buclei de pornire pe real: o pozitie a botului exista deja; mesajul de pornire/status foloseste sold + marja ei."""
    import os
    import time as _t
    a, tg, br = make_real(146.4)
    br.pos["1"] = {"id": "1", "name": "GBPUSD", "side": -1, "open_rate": 1.3, "units": 1700.0, "amount": 73.0, "leverage": 30,
                   "sl": 1.31, "tp": 1.29, "time": "2026-10-09T08:00:00Z"}
    br.balance = 146.4 + 73.0 * 0 + 0.0
    br.pos["2"] = {"id": "2", "name": "USDCAD", "side": 1, "open_rate": 1.42, "units": 2180.0, "amount": 73.2, "leverage": 30,
                   "sl": 1.41, "tp": 1.43, "time": "2026-10-09T08:00:00Z"}
    a.bot_pids = {"1", "2"}
    monkeypatch.setenv("CONTINUED", "1")
    import state
    state.save({"bot_pids": ["1", "2"], "unlocked": True, "realized": 3.57, "n_closed": 2})
    monkeypatch.setattr(a, "scan", lambda manual=False: None)
    monkeypatch.setattr(_t, "time", lambda: 10 ** 9)
    a.stop_reason = "test"                                    # iese imediat din bucla, dupa partea de pornire
    a.run(0.01)
    assert a.unlocked and set(a.known) == {"1", "2"}
    assert abs(a.equity() - (br.credit() + 146.2)) < 0.5


def test_advisor_rules():
    import advisor as AD
    # in plus de 2$, deschisa de 3h, trendul s-a intors -> incaseaza
    r = AD.advise(1, 1.1000, 1.1020, 1.1050, 1.0900, 2.0, 3.0, "jos", 55)
    assert r["verdict"] == "INCHIDE" and any("+$2.00" in x for x in r["reasons"])
    # in plus de 2$ dar aproape de tinta -> tine
    assert AD.advise(1, 1.1000, 1.1040, 1.1050, 1.0900, 2.0, 1.0, "sus", 55)["verdict"] == "TINE"
    # Regula 1: pe minus NU mai sfatuim «inchide», chiar daca trendul e impotriva si suntem aproape de plasa
    r = AD.advise(-1, 1.1000, 1.1080, 1.0950, 1.1100, -4.0, 1.0, "sus", 60)
    assert r["verdict"] == "ATENTIE" and not any("tai pierderea" in x for x in r["reasons"])
    assert AD.advise(-1, 1.1000, 1.1030, 1.0950, 1.1100, -2.0, 20.0, "sus", 60)["verdict"] != "INCHIDE"        # nici dupa 20 de ore pe minus
    # pe minus mic, trend in directia ta -> tine
    assert AD.advise(-1, 1.1000, 1.1003, 1.0950, 1.1100, -0.5, 1.0, "jos", 45)["verdict"] == "TINE"
    # profit mic, de ore pe loc, fara trend favorabil -> poti iesi in verde
    assert AD.advise(1, 1.4260, 1.4264, 1.4290, 1.4230, 0.14, 3.5, "lateral", 52)["verdict"] == "INCHIDE"


def test_status_gives_advice_per_position():
    a, tg, br = make_real(150.0)
    a.unlocked = True
    br.pos["1"] = {"id": "1", "name": "GBPUSD", "side": -1, "open_rate": 1.3240, "units": 1700.0, "amount": 73.0, "leverage": 30,
                   "sl": 1.3280, "tp": 1.3225, "time": ""}
    a.bot_pids.add("1")
    br.prices["GBPUSD"] = 1.3230
    a.now_fn = lambda: T0 + timedelta(hours=3)
    a.monitor()
    a.known["1"]["opened_at"] = T0
    a.known["1"]["px_now"] = 1.3230
    a.status()
    text = tg.texts[-1]
    assert "ȚINE-O" in text or "ÎNCHIDE-O" in text
    assert "spre țintă" in text and "ℹ️ Sfaturile vin" not in text                       # Status scurt: sfat pe un rând, fără explicația repetată


def test_advice_tick_warns_once_per_hour_with_close_button(monkeypatch):
    a, tg, br = make_real(150.0)
    a.unlocked = True
    a.known["1"] = {"id": "1", "name": "EURUSD", "side": 1, "open_rate": 1.1000, "units": 1000.0, "amount": 50.0, "leverage": 30,
                    "sl": 1.0900, "tp": 1.1050, "last_pnl": 2.0, "px_now": 1.1020, "opened_at": T0 - timedelta(hours=4)}
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"trend": "jos", "rsi_live": 55.0})
    a.advice_tick()
    msgs = [x for x in tg.sent if "💡" in x[0]]
    assert len(msgs) == 1 and msgs[0][1][0][0][1] == "close:1" and "ÎNCHIDE-O" in msgs[0][0]
    a.advice_tick()
    assert len([x for x in tg.sent if "💡" in x[0]]) == 1                       # nu se repeta in aceeasi ora


class PhotoTG(FakeTG):
    def __init__(self):
        super().__init__()
        self.photos = []

    def send_photo(self, png, caption="", silent=False):
        self.photos.append((png[:8], caption))
        self.sent.append(("[FOTO] " + caption, None, self._mid))
        return 1


def _synthetic_df(n=400):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-09-20", periods=n, freq="h", tz="UTC")
    c = 1.1 + np.cumsum(rng.normal(0, 0.0005, n))
    return pd.DataFrame({"open": c, "high": c + 0.0004, "low": c - 0.0004, "close": c}, index=idx)


def test_signal_comes_with_a_chart_and_context_line(monkeypatch):
    tg, br = PhotoTG(), FakeBroker()
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None)
    df = _synthetic_df()
    monkeypatch.setattr(signals, "scan", lambda d, names, now=None, *wa: {"side": 1 if names[0] == "london_breakout" else 0, "why": "test", "rsi": 18.0,
        "price": 1.1, "bar": "b1", "age_min": 5.0, "atr_pct": 0.0008, "trend": "jos", "trend4h": "jos", "support": 1.095, "resistance": 1.105, "_df": df})
    a.scan()
    assert tg.photos and tg.photos[0][0] == b"\x89PNG\r\n\x1a\n"
    texts = [t for t, _, _ in tg.sent]
    i_photo = next(i for i, t in enumerate(texts) if t.startswith("[FOTO]"))
    i_sig = next(i for i, t in enumerate(texts) if "Semnal pe" in t)
    assert i_photo < i_sig and "Context: trend 1h ↘️, 4h ↘️" in texts[i_sig] and "suport 1.095" in texts[i_sig]


def test_levels_and_4h_trend_on_real_shaped_data():
    import signals as S
    df = _synthetic_df(900)
    sup, res = S.levels_sr(df)
    px = float(df["close"].iloc[-1])
    assert (sup is None or sup < px) and (res is None or res > px)
    assert S.trend4h(df) in ("sus", "jos", "lateral")


def test_daily_report_and_total_since_start():
    a, tg, br = make()
    a.add_realized(+3.0)
    a.add_realized(-1.0)
    a.add_realized(+0.5)
    assert a.total_pnl == 2.5 and a.history["2026-10-09"] == {"pnl": 2.5, "n": 3}
    a.realized = 0.0                                              # un /reset al bugetului nu sterge totalul de la inceput
    assert a.total_pnl == 2.5
    assert not a.report_due(T0)                                   # 08:15 UTC: prea devreme
    late = T0.replace(hour=19, minute=35)                         # vineri: piata se inchide la 20:00 UTC
    assert a.report_due(late) and not a.report_due(T0.replace(hour=19, minute=10))
    a.now_fn = lambda: late
    a.daily_report()
    t = tg.texts[-1]
    assert "Raportul zilei" in t and "+$2.50" in t and "3" in t and "TOTAL de la început" in t
    assert not a.report_due(late)                                 # o singura data pe zi
    assert not a.report_due(late + timedelta(days=1))             # sambata nu
