import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import modes  # noqa: E402
import signals  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG, T0  # noqa: E402
from test_spec_audit import T1, make, wave_df  # noqa: E402

RAW = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))


def agg(monkeypatch, real=False, ok=False, flag="1"):
    monkeypatch.setenv("AGGRESSIVE_MODE", flag)
    monkeypatch.setenv("AGGRESSIVE_REAL_OK", "1" if ok else "")
    return modes.apply(RAW, real)


def test_default_is_off_and_config_identical(monkeypatch):
    monkeypatch.delenv("AGGRESSIVE_MODE", raising=False)
    c = modes.apply(RAW, False)
    assert c["_aggressive"] is False and c["wave_atr"] == 1.6 and c["max_positions"] == 3 and c["tp_atr"] == 0.75
    assert [i["signals"] for i in c["instruments"]] == [i["signals"] for i in RAW["instruments"]]
    assert RAW["aggressive_mode"] is False


def test_aggressive_values_from_the_patch(monkeypatch):
    c = agg(monkeypatch)
    assert c["_aggressive"] is True
    by = {i["name"]: i["signals"] for i in c["instruments"]}
    assert "rsi_rev36" in by["EURUSD"] and "pullback50" in by["EURUSD"] and "pullback50" in by["SPX500"]
    assert "rsi_rev30" in by["OIL"] and "rsi_rev36" not in by["OIL"]
    assert by["GOLD"] == ["pullback50", "donchian24_trend"]                 # fara regula RSI noua pe aur/indici
    assert (c["wave_atr"], c["wave_max_proposals"], c["wave_opts"]["cooldown_min"]) == (1.3, 2, 90)
    assert (c["wave_opts"]["rsi_buy_max"], c["wave_opts"]["rsi_sell_min"]) == (90, 10)
    assert (c["max_positions_small"], c["max_positions"], c["min_margin_usd"]) == (3, 4, 50)
    assert (c["tp_atr"], c["max_tp_usd"], c["sl_atr"], c["max_sl_usd"], c["min_tp_usd"]) == (1.1, 10, 3.5, 25, 2.25)
    assert c["autotrade_daily_loss_usd"] == 22 and c["signal_cooldown_min"] == 12 and c["boost_alloc"] == 0.40
    assert c["scan_slot_min"] == 5                                           # cadenta neschimbata
    assert {i["name"]: i["lev_cap"] for i in c["instruments"]} == {i["name"]: i["lev_cap"] for i in RAW["instruments"]}


def test_aggressive_applies_on_real_account_too(monkeypatch):
    c = agg(monkeypatch, real=True)
    assert c["_aggressive"] is True and c["_mode_note"] == "" and c["wave_atr"] == 1.3


def test_strategies_support_new_thresholds():
    import strategies
    S = strategies.all_signals(wave_df(0.0))
    assert "rsi_rev36" in S and "pullback50" in S


def test_wave_lateral_trend_can_be_blocked():
    df = wave_df(3.0, 0.00002, T1)
    done = signals.completed(df, __import__("pandas").Timestamp(T1))
    assert signals.wave(df, done, "lateral", 3, 1.3, {"allow_neutral": True})[0] == 1
    assert signals.wave(df, done, "lateral", 3, 1.3, {"allow_neutral": False})[0] == 0
    assert signals.wave(df, done, "sus", 3, 1.3, {"allow_neutral": False})[0] == 1


def build(monkeypatch, df, now=T1, only=("EURUSD",)):
    cfg = agg(monkeypatch)
    tg, br = FakeTG(), FakeBroker()
    a = A.Assistant(cfg, tg, br, fetch=lambda *x, **k: df, now_fn=lambda: now, sleep=lambda s: None)
    a.inst = {k: v for k, v in a.inst.items() if k in only}
    a.unlocked = True
    return a, tg, br


def test_aggressive_signal_has_prefix_and_surfer_reason(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.scan()
    t = next(x for x in tg.texts if "Semnal pe" in x)
    assert t.startswith("[AGGRESSIVE] ") and "SURFER" in t.split("\n")[0] and not br.pos


def test_wave_gets_two_proposals_then_stops_and_cooldown_applies(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    n = lambda: len([x for x in tg.texts if "Semnal pe" in x])  # noqa: E731
    a.scan()
    assert n() == 1
    a.pending.clear()
    a.now_fn = lambda: T1 + timedelta(minutes=5)
    a.scan()
    assert n() == 1                                          # pauza de 12 min pe acelasi instrument
    a.now_fn = lambda: T1 + timedelta(minutes=13)
    a.scan()
    assert n() == 2                                          # a doua propunere pentru acelasi val
    a.pending.clear()
    a.now_fn = lambda: T1 + timedelta(minutes=30)
    a.scan()
    assert n() == 2                                          # maxim 2 pe val


def test_boost_allocation_only_when_surfer_and_extreme_rsi(monkeypatch):
    a, tg, br = build(monkeypatch, None)
    a.realized = 150.0                                       # cont 300 $
    inst = a.inst["EURUSD"]
    base = a.sizing(inst)[0]
    boosted = a.sizing(inst, True)[0]
    assert base == 75.0 and boosted == 120.0                 # 300 $ / 4 pozitii vs 40% din 300 $
    wave_s = {"side": 1, "sig_key": "wave+1-x", "rsi_live": 70.0}
    assert a.is_boost("EURUSD", wave_s)                      # val + RSI extrem (>= 64 pe pragul 36)
    assert not a.is_boost("EURUSD", {**wave_s, "rsi_live": 55.0})            # val fara RSI extrem
    assert not a.is_boost("EURUSD", {**wave_s, "sig_key": "2026-10-09T08:00:00+00:00"})   # RSI fara val
    assert not a.is_boost("EURUSD", {**wave_s, "side": -1})                  # RSI extrem in sens contrar valului


def test_max_positions_and_levels_in_aggressive(monkeypatch):
    a, tg, br = build(monkeypatch, None)
    assert a.equity() >= 150 and a.max_pos() == 4              # de la 150 $: 4
    a.realized = -30.0
    assert a.max_pos() == 3                                  # sub 150 $: 3
    sl, tp, tpu, slu = a.levels(1, 1.10, 1500.0, 0.003)
    assert tpu <= 10 and slu <= 25 + 1e-9
