import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_aggressive import build  # noqa: E402
from test_spec_audit import T1, wave_df  # noqa: E402


def signals_sent(tg):
    return [x for x in tg.texts if "Semnal pe" in x]


def test_below_target_signals_still_come(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.day, a.day_pnl = T1.strftime("%Y-%m-%d"), 14.0          # sub tinta de 15 $
    a.scan()
    assert signals_sent(tg) and not any("🔒" in x for x in tg.texts)


def test_target_reached_blocks_new_signals_and_tells_once(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.day, a.day_pnl = T1.strftime("%Y-%m-%d"), 15.5          # tinta atinsa
    a.scan()
    a.scan()
    assert not signals_sent(tg) and not br.pos
    assert len([x for x in tg.texts if "🔒" in x]) == 1       # anuntul vine o singura data pe zi


def test_target_is_per_day_and_can_be_switched_off(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.day, a.day_pnl = "2000-01-01", 99.0                     # profit de alta zi nu blocheaza azi
    assert a.profit_locked() is False
    a.day, a.day_pnl = T1.strftime("%Y-%m-%d"), 99.0
    a.cfg["daily_profit_lock_usd"] = 0                        # 0 = oprit
    assert a.profit_locked() is False
