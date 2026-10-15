"""Cazuri-limita gasite la auditul riguros: stare veche, cont real cu bani putini, repornire in mijlocul unui val."""
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import modes  # noqa: E402
import state as state_mod  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG, T0  # noqa: E402
from test_spec_audit import T1, wave_df  # noqa: E402

RAW = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))


class RealBroker(FakeBroker):
    def __init__(self, credit):
        super().__init__()
        self._credit = credit

    def credit(self, fresh=False):
        return self._credit


def build(cfg, broker, now=T1, df=None, real=True):
    tg = FakeTG()
    a = A.Assistant(cfg, tg, broker, fetch=lambda *x, **k: df, now_fn=lambda: now, sleep=lambda s: None, real=real)
    a.inst = {k: v for k, v in a.inst.items() if k == "EURUSD"}
    return a, tg


def test_old_state_without_new_keys_loads(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    state_mod.save({"realized": 5.0, "n_closed": 3, "autotrade": False, "day": "2026-10-13", "day_pnl": 1.0, "seen": {}}, p)
    monkeypatch.setattr(state_mod, "PATH", p)
    monkeypatch.delenv("CONTINUED", raising=False)
    a, tg = build(modes.apply(RAW, False), FakeBroker(), real=False)
    a.inst = dict(a.inst)
    a.stop_reason = "test"
    a.run(0.1)                                              # nu trebuie sa pice la o stare fara total_pnl / history / since
    assert a.total_pnl == 5.0 and a.history == {} and a.since            # totalul porneste din castigul realizat deja stiut
    assert any("pornit" in t for t in tg.texts)


def test_real_low_balance_blocks_order_with_clear_message():
    br = RealBroker(credit=30.0)                              # 30 $ liberi: sub minimul eToro de 50 $
    a, tg = build(modes.apply(RAW, True), br, df=wave_df(3.0, 0.00002, T1))
    a.unlocked = True
    a.refresh_real()
    a.scan()
    sig = [t for t in tg.texts if "Semnal pe" in t]
    assert sig and "Nu pot deschide" in sig[0] and not br.pos        # explică, nu trimite ordin
    assert not a.pending


def test_real_enough_balance_proposes_and_ok_opens_with_sl_tp():
    br = RealBroker(credit=150.0)
    a, tg = build(modes.apply(RAW, True), br, df=wave_df(3.0, 0.00002, T1))
    a.unlocked = True
    a.refresh_real()
    a.scan()
    assert a.pending and not br.pos
    sid = next(iter(a.pending))
    a.handle({"kind": "button", "id": "x", "data": f"open:{sid}", "msg_id": 1})
    assert len(br.pos) == 1
    pos = next(iter(br.pos.values()))
    assert pos["sl"] and pos["tp"] and pos["leverage"] == 30 and pos["amount"] >= 50
    assert pos["id"] in a.bot_pids


def test_restart_does_not_repropose_same_wave(monkeypatch, tmp_path):
    cfg = modes.apply(RAW, False)
    monkeypatch.setenv("AGGRESSIVE_MODE", "1")
    cfg = modes.apply(RAW, False)
    cfg["wave_max_proposals"] = 2                            # testul verifică mecanismul „val”, indiferent de valoarea din config
    a, tg = build(cfg, FakeBroker(), df=wave_df(3.0, 0.00002, T1), real=False)
    a.unlocked = True
    a.scan()
    n = len([t for t in tg.texts if "Semnal pe" in t])
    a.cfg["signal_cooldown_min"] = 0
    a.pending.clear()
    # sesiune noua: aceleasi cheie de val in `seen`; dupa reincarcare nu mai cere de 2 ori
    seen = dict(a.seen_bar)
    a2, tg2 = build(cfg, FakeBroker(), df=wave_df(3.0, 0.00002, T1), real=False)
    a2.unlocked = True
    a2.seen_bar = seen
    for k, v in a2.seen_bar.items():
        if str(v).startswith("wave"):
            a2.wave_n[(k, v)] = a2.cfg.get("wave_max_proposals", 1)
    a2.cfg["signal_cooldown_min"] = 0
    a2.scan()
    assert n == 1 and not [t for t in tg2.texts if "Semnal pe" in t]


def test_stale_data_does_not_trigger_signals():
    a, tg = build(modes.apply(RAW, False), FakeBroker(), now=T1 + timedelta(hours=5), df=wave_df(3.0, 0.00002, T1), real=False)
    a.unlocked = True
    a.scan()
    assert not [t for t in tg.texts if "Semnal pe" in t]      # date vechi de ore: piața pare închisă
