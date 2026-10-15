"""T003: semnalul spune CUMPĂRĂ pe revenire, iar un minut mai târziu sfatul spunea „ATENȚIE, trendul e împotriva ta”."""
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import advisor  # noqa: E402
import assistant as A  # noqa: E402
import messages as msg  # noqa: E402
import signals  # noqa: E402
from test_assistant import FakeTG, T0, make, press  # noqa: E402

TREND_DOWN_BUY = dict(side=1, open_rate=1.4000, price=1.3998, tp=1.4030, sl=1.3900, pnl=-0.19, trend="jos", rsi=33)


def test_brand_new_position_gets_no_verdict_only_entry_cost_note():
    adv = advisor.advise(age_h=0.5 / 60, counter=True, **TREND_DOWN_BUY)             # „deschisă de 0 min”, exact cazul din 15.10
    txt = msg.advice_block(adv)
    assert adv["verdict"] == "NOU"
    assert "ATENȚIE" not in txt and "ÎMPOTRIVA" not in txt and "ÎNCHIDE" not in txt
    assert "costul de intrare" in txt and "în plan" in txt                          # explică și că revenirea era planul
    adv2 = advisor.advise(age_h=0.1, counter=False, **TREND_DOWN_BUY)               # și fără plan de revenire: tot fără verdict sub 15 min
    assert adv2["verdict"] == "NOU"


def test_reversal_position_with_trend_against_is_not_presented_as_a_warning():
    adv = advisor.advise(age_h=2.0, counter=True, **{**TREND_DOWN_BUY, "pnl": -0.5})
    assert adv["verdict"] == "TINE" and not any("ÎMPOTRIVA" in r for r in adv["reasons"])
    assert any("în plan" in r for r in adv["reasons"])
    old = advisor.advise(age_h=2.0, counter=False, **{**TREND_DOWN_BUY, "pnl": -0.5})   # o poziție pe trend care a întors: avertismentul rămâne
    assert old["verdict"] == "ATENTIE" and any("ÎMPOTRIVA" in r for r in old["reasons"])


def test_new_position_near_the_stop_still_gets_a_verdict():
    adv = advisor.advise(age_h=0.1, counter=True, **{**TREND_DOWN_BUY, "price": 1.3910, "pnl": -9.0})   # 90% spre plasă într-un minut
    assert adv["verdict"] != "NOU"


def _scan_down(monkeypatch, names):
    def scan(df, sig_names, now=None, *wa):
        return {"side": 1 if sig_names and sig_names[0] in names else 0, "why": "RSI 33, prețul a scăzut prea mult", "rsi": 33.0, "price": 1.1,
                "bar": "b1", "trend": "jos", "trend4h": "jos"}
    monkeypatch.setattr(signals, "scan", scan)


def _one_pair(a, name="EURUSD"):
    a.inst = {name: a.inst[name]}
    return a.inst[name]["signals"][0]


def test_signal_says_it_expects_a_bounce_and_advice_agrees(monkeypatch):
    a, tg, br = make()
    _scan_down(monkeypatch, {_one_pair(a)})
    a.scan()
    sig = next(t for t in tg.texts if "Semnal pe" in t)
    assert "Mă aștept la revenire, deși trendul orar e în jos" in sig
    press(a, f"open:{next(iter(a.pending))}")
    pos = next(iter(a.known.values()))
    assert pos["counter"] is True and str(pos["id"]) in a.counter_pids
    assert a.advice_for(pos)["verdict"] == "NOU"                                     # imediat după deschidere: fără verdict
    a.now_fn = lambda: T0 + timedelta(hours=2)
    pos["opened_at"] = T0
    adv = a.advice_for(pos)
    assert adv["verdict"] == "TINE" and not any("ÎMPOTRIVA" in r for r in adv["reasons"])


def test_reversal_plan_survives_a_restart(monkeypatch):
    a, tg, br = make()
    _scan_down(monkeypatch, {_one_pair(a)})
    a.scan()
    press(a, f"open:{next(iter(a.pending))}")
    pid = next(iter(a.known))
    a.save_state()
    saved = A.state_mod.load()
    assert saved["counter_pids"] == [pid]
    b = A.Assistant(a.cfg, FakeTG(), br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None)
    b.counter_pids = set(saved["counter_pids"])                                      # așa îl încarcă pornirea
    b.track(next(p for p in br.positions() if p["id"] == pid))
    assert b.known[pid]["counter"] is True


def test_two_pending_signals_are_one_message_each_with_all_buttons_not_a_third_message(monkeypatch):
    a, tg, br = make()
    names = [n for n in ("EURUSD", "GBPUSD") if n in a.inst]
    a.inst = {n: a.inst[n] for n in names}
    _scan_down(monkeypatch, {a.inst[n]["signals"][0] for n in names})
    a.scan()
    assert len(a.pending) == 2
    assert not [t for t in tg.texts if "semnale în așteptare" in t]                   # fără mesajul separat 📦
    sig_msgs = [(t, b) for t, b, _ in tg.sent if "Semnal pe" in t]
    assert len(sig_msgs) == 2
    first = [x[1] for row in sig_msgs[0][1] for x in row]
    second = [x[1] for row in sig_msgs[1][1] for x in row]
    assert not any(d.startswith("openall") for d in first)
    assert any(d.startswith("openall") for d in second) and any(d.startswith("skipall") for d in second)


def test_same_close_advice_is_not_repeated(monkeypatch):
    a, tg, br = make()
    _scan_down(monkeypatch, {_one_pair(a)})
    a.scan()
    press(a, f"open:{next(iter(a.pending))}")
    pos = next(iter(a.known.values()))
    pos.update(counter=False, last_pnl=3.0, opened_at=T0 - timedelta(hours=3))      # în plus, de ore bune: sfatul „închide”
    a.now_fn = lambda: T0
    n0 = len([t for t in tg.texts if "💡" in t])
    a.advice_tick()
    a.advice_sent.clear()                                                            # trece ora, același motiv
    a.advice_tick()
    n1 = len([t for t in tg.texts if "💡" in t])
    assert n1 - n0 == 1                                                              # nu se repetă identic
