"""Ecranele din 16.10: semnal BUY pe GBP/USD (nu s-a putut deschide, $45.79 liber), apoi «Caută semnale» spunea «Niciun semnal nou… HOLD»;
iar Status repeta aceleași explicații și trimitea poze la fiecare apăsare."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import signals  # noqa: E402
from test_assistant import make, press  # noqa: E402


def _blocked_assistant(monkeypatch):
    a, tg, br = make()
    a.inst = {"GBPUSD": a.inst["GBPUSD"], "EURUSD": a.inst["EURUSD"]}
    a.fetch = lambda yahoo, *x, **k: yahoo                    # df = simbolul Yahoo, ca testul să știe pe ce instrument e
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {
        "side": 1 if str(df).startswith("GBP") else 0, "why": "trendul orar e clar și prețul a spart maximul", "rsi": 72.0 if str(df).startswith("GBP") else 62.0,
        "price": 1.3312, "bar": "2026-10-16T07:00:00+00:00", "trend": "sus", "trend4h": "sus", "asia_pos": "în interior"})
    a.free_margin = lambda: 45.79                              # sub minimul eToro de 50 $
    a.scan()
    return a, tg, br


def test_scan_report_does_not_contradict_a_signal_that_could_not_open(monkeypatch):
    a, tg, br = _blocked_assistant(monkeypatch)
    first = next(t for t in tg.texts if "Semnal pe" in t)
    assert "CUMPĂR" in first and "Nu pot deschide acum" in first
    a.scan(manual=True)
    rep = tg.texts[-1]
    assert "Semnale active" in rep and "CUMPĂR" in rep and "GBP/USD" in rep
    assert "45.79" in rep or "minim" in rep                                    # spune de ce nu s-a deschis
    assert "HOLD" not in rep and "Niciun semnal nou" not in rep                # nu mai contrazice semnalul de mai devreme
    assert "BUY GBP/USD" in rep                                                # recomandarea e aceeași


def test_scan_report_is_short_and_has_no_filler(monkeypatch):
    a, tg, br = _blocked_assistant(monkeypatch)
    a.scan(manual=True)
    rep = tg.texts[-1]
    assert len(rep.splitlines()) <= 8                                          # nu o listă lungă cu un rând pe instrument
    assert "Cumpăr/vând doar când văd semnal clar" not in rep and "RSI-ul fără paranteză" not in rep


def test_scan_report_without_any_signal_says_hold_once(monkeypatch):
    a, tg, br = make()
    a.inst = {"EURUSD": a.inst["EURUSD"]}
    monkeypatch.setattr(signals, "scan", lambda df, names, now=None, *wa: {"side": 0, "why": "", "rsi": 55.0, "price": 1.1,
                                                                          "bar": "2026-10-16T07:00:00+00:00", "trend": "lateral"})
    a.scan(manual=True)
    rep = tg.texts[-1]
    assert rep.count("HOLD") == 1 and "Semnale active" not in rep


def test_status_is_short_and_sends_charts_only_on_request(monkeypatch):
    a, tg, br = make()
    br.pos["1"] = {"id": "1", "name": "GBPUSD", "side": 1, "open_rate": 1.3300, "units": 1700.0, "amount": 73.0, "leverage": 30,
                   "sl": 1.3200, "tp": 1.3340, "time": ""}
    a.known["1"] = {**br.pos["1"], "last_pnl": 0.5, "tp_usd": 2.9, "sl_usd": 8.0, "opened_at": None}
    sent_photos = []
    a.tg.send_photo = lambda png, caption="", silent=False: sent_photos.append(caption)      # FakeTG nu are poze: le numărăm
    a.send_chart = lambda *args, **k: sent_photos.append("poza")
    a.status()
    text, buttons, _ = tg.sent[-1]
    assert not sent_photos                                                                   # Status nu mai trimite poze automat
    assert "ℹ️ Sfaturile vin din reguli simple" not in text                                   # fără explicația repetată
    assert any(b[1] == "charts" for row in buttons for b in row)                             # graficele vin din butonul „Grafice”
    press(a, "charts")
    assert sent_photos                                                                       # la cerere: poza


def test_blocked_signal_is_reproposed_with_current_money_not_a_stale_reason(monkeypatch):
    a, tg, br = _blocked_assistant(monkeypatch)
    assert any("Nu pot deschide acum" in t for t in tg.texts)
    a.free_margin = lambda: 110.42                                              # între timp ai mai mulți bani liberi
    n = len([t for t in tg.texts if "Semnal pe" in t])
    a.scan()
    sig = [t for t in tg.texts if "Semnal pe" in t]
    assert len(sig) == n + 1 and "Deschid?" in sig[-1] and "Nu pot deschide acum" not in sig[-1]      # propunere nouă, cu OK/NU, nu motivul vechi
    assert "GBPUSD" not in a.blocked


def test_blocked_reason_in_report_uses_current_free_money(monkeypatch):
    a, tg, br = _blocked_assistant(monkeypatch)
    a.free_margin = lambda: 30.00                                               # tot sub minim, dar cifra s-a schimbat
    a.scan(manual=True)
    rep = tg.texts[-1]
    assert "$30.00" in rep and "$45.79" not in rep                              # cifra de ACUM, nu cea veche
