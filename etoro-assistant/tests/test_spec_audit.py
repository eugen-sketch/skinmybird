"""Audit pe specificatia botului (ce i s-a cerut sa faca), cu semnalele reale (nu simulate) unde se poate."""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import messages as M  # noqa: E402
import signals  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG, T0, press  # noqa: E402

ROOT = Path(__file__).parent.parent
T1 = T0.replace(hour=14, minute=15)      # vineri 14:15 UTC: dupa fereastra Londrei, deci doar valul poate da semnal


def make(now=T0, only=("EURUSD",), df=None, real=False):
    tg, br = FakeTG(), FakeBroker()
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: df, now_fn=lambda: now, sleep=lambda s: None, real=real)
    a.inst = {k: v for k, v in a.inst.items() if k in only}
    a.unlocked = True
    return a, tg, br


def wave_df(jump: float, drift: float = 0.0, now=T0):
    """Ore pana la ora curenta (in formare); ultimele 3 ore urca cu `jump` x zgomotul orar."""
    n = 400
    idx = pd.date_range(end=now.replace(minute=0, second=0, microsecond=0), periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(7)
    c = 1.10 + np.cumsum(rng.normal(drift, 0.0004, n))
    c[-3:] = c[-4] + np.linspace(1, 3, 3) * jump * 0.0004 / 2
    return pd.DataFrame({"open": c, "high": c + 0.0003, "low": c - 0.0003, "close": c}, index=idx)


def test_wave_proposes_real_signal_without_opening_anything():
    a, tg, br = make(now=T1, df=wave_df(3.0, 0.00002, T1))
    a.scan()
    props = [t for t in tg.texts if "Semnal pe" in t]
    assert props, tg.texts                                        # a propus intrarea (val mare)
    assert not br.pos                                             # dar nu a deschis nimic fara OK
    assert any("val mare" in t.lower() for t in tg.texts)                 # explicat in cuvinte


def test_no_wave_no_signal_on_flat_market():
    a, tg, br = make(now=T1, df=wave_df(0.0, 0.0, T1))
    a.scan()
    assert not [t for t in tg.texts if "Semnal pe" in t] and not br.pos


def test_wave_not_repeated_for_same_wave():
    a, tg, br = make(now=T1, df=wave_df(3.0, 0.00002, T1))
    a.scan()
    n1 = len([t for t in tg.texts if "Semnal pe" in t])
    a.pending.clear()
    a.now_fn = lambda: T1 + timedelta(minutes=5)
    a.scan()
    assert len([t for t in tg.texts if "Semnal pe" in t]) == n1  # acelasi val: nu cere iar


def test_ok_opens_with_sl_and_tp_and_two_positions_max_under_150():
    a, tg, br = make(only=("EURUSD", "GBPUSD", "USDJPY"))
    assert a.max_pos() == 3 and a.sizing(a.inst["EURUSD"])[0] == 50.0     # de la 150 $: 3 pozitii, cate 50 $ (minimul eToro)
    a.realized = -30.0                                                    # cont 120 $: doar 2 pozitii, cate 60 $
    assert a.max_pos() == 2 and a.sizing(a.inst["EURUSD"])[0] == 60.0
    a.realized = 150.0                                                    # cont 300 $: 3 pozitii, cate 100 $
    assert a.max_pos() == 3 and a.sizing(a.inst["EURUSD"])[0] == 100.0
    a.realized = 0.0
    sl, tp, tpu, slu = a.levels(1, 1.10, 75 * 30, 0.0008)
    assert sl < 1.10 < tp and tpu >= CFG["min_tp_usd"] and slu <= CFG["max_sl_usd"] + 1e-9


def test_autotrade_is_off_by_default_and_real_is_locked_until_confirmed():
    a, tg, br = make(real=True)
    a.unlocked = False
    a.scan()
    assert not a.autotrade and not br.pos and not a.pending          # fara confirmare: nu propune, nu deschide


def test_scan_every_5_minutes_and_slots():
    assert CFG["scan_slot_min"] == 5 and CFG["wave_atr"] > 0
    assert all("rsi_rev30" in i["signals"] or not (len(i["name"]) == 6) for i in CFG["instruments"])


def test_no_repeated_hourly_report_but_radar_every_4h():
    a, tg, br = make(df=wave_df(0.0))
    for k in range(0, 36):                                           # 3 ore de scanari la 5 minute
        a.now_fn = lambda k=k: T0 + timedelta(minutes=5 * k)
        a.scan()
    assert sum("Radar" in t for t in tg.texts) <= 1
    assert not any("Am scanat acum" in t for t in tg.texts)


def test_daily_report_is_timed_before_close_and_romanian_time():
    a, tg, br = make()
    for h, m in ((20, 29), (19, 29)):
        assert not a.report_due(datetime(2026, 10, 14 if h == 20 else 16, h, m, tzinfo=timezone.utc))
    assert a.report_due(datetime(2026, 10, 14, 20, 30, tzinfo=timezone.utc))    # miercuri
    assert a.report_due(datetime(2026, 10, 16, 19, 30, tzinfo=timezone.utc))    # vineri (piata se inchide la 20:00)
    assert M.ro_hm(datetime(2026, 10, 14, 7, 0, tzinfo=timezone.utc)) == "10:00"
    assert M.ro_hm(datetime(2026, 12, 14, 7, 0, tzinfo=timezone.utc)) == "09:00"   # ora de iarna


def test_no_repeated_disclaimers_in_messages():
    src = (ROOT / "messages.py").read_text() + (ROOT / "assistant.py").read_text()
    for bad in ("decizia e a ta", "nu garantează nimic", "Nu este sfat"):
        assert bad not in src


def test_real_uses_real_order_status_route_and_refuses_demo_paths():
    import etoro
    api = etoro.EToroDemo(api_key="k", user_key="u", real=True)
    seen = []
    api._req = lambda method, path, **k: seen.append(path) or {}
    api.order_status(5)
    assert seen == ["/api/v1/trading/info/real/orders/5"]
    try:
        etoro.EToroDemo(api_key="k", user_key="u", real=True)._req("GET", "/api/v1/trading/info/demo/portfolio", trading=True)
        assert False
    except etoro.EToroError:
        pass


def test_launcher_defaults_to_real():
    src = (ROOT / "launcher.py").read_text()
    assert re.search(r'"demo" if re\.search\(r"\\bdemo\\b"', src)


def test_profit_today_vs_total_are_clearly_separated_everywhere():
    a, tg, br = make()
    a.since = "2026-10-12"
    a.history = {"2026-10-12": {"pnl": 4.0, "n": 2}, "2026-10-13": {"pnl": 3.0, "n": 1}}
    a.total_pnl, a.n_total = 7.0, 3
    a.add_realized(+1.5)                                   # azi (09.10 in test): 1 poziție, +1.5 ; total: 4 poziții, +8.5
    block = a.profit_text()
    assert "PROFIT AZI (09.10): +$1.50 · 1 poziții închise azi" in block
    assert "PROFIT TOTAL de la început (12.10): +$8.50 · 4 poziții închise în total" in block
    closed = M.closed("EURUSD", "TP", 1.5, block, 150.0)
    assert "PROFIT AZI" in closed and "PROFIT TOTAL" in closed
    a.status()
    assert "PROFIT AZI" in tg.texts[-1] and "PROFIT TOTAL" in tg.texts[-1]
    a.daily_report(final=False)
    rep = tg.texts[-1]
    assert "PROFIT AZI (09.10)" in rep and "PROFIT TOTAL de la început (12.10)" in rep
    assert "Profit azi: +$1.50" in rep and "Profit total: +$8.50" in rep and "Poziții închise azi: 1" in rep and "Poziții închise în total: 4" in rep
    assert "Zilele dinainte" in rep and "12.10" in rep


def test_daily_report_shows_target_in_dollars_for_open_positions():
    a, tg, br = make()
    a.known["p1"] = {"id": "p1", "name": "EURUSD", "side": 1, "last_pnl": 0.80, "tp_usd": 2.25, "sl_usd": 3.90, "amount": 50, "leverage": 30}
    a.daily_report(final=False)
    rep = tg.texts[-1]
    assert "Poziții deschise acum: 1" in rep and "+$0.80 nerealizat" in rep
    assert "EUR/USD (cumpărat): acum +$0.80 · ținta e +$2.25 (mai are $1.45 până la țintă) · plasa −$3.90" in rep


def test_target_in_dollars_in_update_and_status_too():
    a, tg, br = make()
    a.known["p1"] = {"id": "p1", "name": "EURUSD", "side": 1, "last_pnl": 0.80, "tp_usd": 2.25, "sl_usd": 3.90, "amount": 50,
                     "leverage": 30, "open_rate": 1.1, "tp": 1.1017, "sl": 1.097, "opened_at": T0}
    assert "EUR/USD +$0.80 (ținta +$2.25)" in M.update([{"name": "EURUSD", "pnl": 0.8, "tp_usd": 2.25}], 0.8)
    a.status()
    assert "ținta e +$2.25" in tg.texts[-1]
