"""Petrol, varianta A (alegerea lui Eugen): doar «spargere» + «pullback», fara «revenire RSI»; oprire automata a petrolului la pierderea maxima din experiment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import signals  # noqa: E402
from test_assistant import CFG, make_real  # noqa: E402

GATE = CFG["entry_gate"]
GOOD = {"side": 1, "bar_hour": 10, "adx": 31.0, "vol_rank": 0.7, "sig_key": "2026-10-16T10:00:00+00:00"}


def test_oil_uses_breakout_and_pullback_but_not_rsi_reversal():
    assert signals.gate({**GOOD, "fired": ["donchian24_trend"]}, GATE, "OIL") is None
    assert signals.gate({**GOOD, "fired": ["pullback50"]}, GATE, "OIL") is None                      # pullback permis DOAR pe petrol
    assert signals.gate({**GOOD, "fired": ["rsi_rev30"]}, GATE, "OIL")[0] == "regula"                 # revenirea RSI pierde pe petrol
    assert signals.gate({**GOOD, "fired": ["rsi_rev30", "donchian24_trend"]}, GATE, "OIL") is None   # daca si spargerea e de acord, trece


def test_other_instruments_keep_the_old_rules():
    assert signals.gate({**GOOD, "fired": ["pullback50"]}, GATE, "EURUSD")[0] == "regula"             # pullback ramane interzis pe forex
    assert signals.gate({**GOOD, "fired": ["rsi_rev36"]}, GATE, "EURUSD") is None
    assert signals.gate({**GOOD, "fired": ["pullback50"]}, GATE) [0] == "regula"                      # fara nume: regula generala


def test_oil_is_stopped_automatically_at_the_loss_limit_and_the_reserve_goes_back_to_forex():
    a, tg, br = make_real(278.18)
    a.cfg = {**a.cfg, "max_positions": 4}
    assert a.oil_reserve() == 105.0
    a.oil_test("EURUSD", -50.0)                                                      # alte instrumente nu conteaza
    a.oil_test("OIL", -12.0)
    a.oil_test("OIL", +3.0)
    assert not a.oil_paused and abs(a.oil_pnl + 9.0) < 1e-9
    a.oil_test("OIL", -22.0)                                                         # total -31 <= -30
    assert a.oil_paused and any("Petrolul e oprit" in t and "porneste petrol" in t for t in tg.texts)
    assert a.oil_reserve() == 0.0                                                    # rezerva se elibereaza
    assert abs(a.free_margin("EURUSD") - 278.18) < 0.01                              # forexul vede din nou tot bugetul
    n = len([t for t in tg.texts if "Petrolul e oprit" in t])
    a.oil_test("OIL", -5.0)
    assert len([t for t in tg.texts if "Petrolul e oprit" in t]) == n                # un singur anunt


def test_oil_is_skipped_in_scans_while_paused_and_resumes_on_command(monkeypatch):
    a, tg, br = make_real(278.18)
    a.unlocked = True
    a.oil_paused, a.oil_pnl = True, -31.0
    a.handle({"kind": "text", "text": "Pornește petrol"})
    assert not a.oil_paused and a.oil_pnl == 0.0 and a.oil_reserve() == 105.0
    assert any("Petrolul e pornit din nou" in t for t in tg.texts)


def test_oil_counter_survives_a_restart():
    import state
    a, tg, br = make_real(278.18)
    a.oil_pnl, a.oil_paused = -31.0, True
    a.save_state()
    st = state.load()
    assert st["oil_paused"] is True and st["oil_pnl"] == -31.0
