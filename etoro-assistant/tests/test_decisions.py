"""Socoteala deciziilor tale: registrul (cine a deschis / cine a inchis), «ce-ar fi fost» din preturile de 5 minute, raportul."""
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import decisions  # noqa: E402
import messages as msg  # noqa: E402
from test_assistant import T0, make, press  # noqa: E402

CFG = {"max_hold_hours": 5, "time_stop_min_profit_usd": 0.30}
INST = {"EURUSD": {"yahoo": "EURUSD=X", "cost": 0.012}}


def path(start, closes, spread=0.0002):
    idx = pd.date_range(start, periods=len(closes), freq="5min")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c.shift().fillna(c.iloc[0]), "high": c + spread, "low": c - spread, "close": c})


def test_walk_finds_target_stop_time_limit_and_still_open():
    t0 = T0
    p = path(t0, [1.1000, 1.1010, 1.1030, 1.1060])
    assert decisions.walk(p, 1, 1.1000, t0, 1.1050, 1.0950, 1.1000, 3000, t0, 0, 0.3, 0.012) == (1.1050, "tinta")
    p = path(t0, [1.1000, 1.0990, 1.0940])
    assert decisions.walk(p, 1, 1.1000, t0, 1.1050, 1.0950, 1.1000, 3000, t0, 0, 0.3, 0.012)[1] == "plasa"
    p = path(t0, [1.1000, 1.1001, 1.1002])                                    # nu atinge nimic: se socoteste la pretul de acum
    assert decisions.walk(p, 1, 1.1000, t0, 1.1050, 1.0950, 1.1000, 3000, t0, 0, 0.3, 0.012)[1] == "încă deschisă"
    old = t0 - timedelta(hours=6)                                             # deschisa de 6 ore, pe plus: limita de timp o inchide
    x = decisions.walk(p, 1, 1.1000, t0, 1.1050, 1.0950, 1.1000, 3000, old, 5, 0.3, 0.012)
    assert x[1] == "limita de timp" and x[0] > 1.1000


def test_walk_brings_yahoo_prices_to_etoro_scale():
    p = path(T0, [2000.0, 2010.0, 2030.0], spread=0.5)                         # Yahoo (futures) ~1% peste eToro
    x = decisions.walk(p, 1, 1980.0, T0, 1995.0, 1950.0, 1980.0, 2000, T0, 0, 0.3, 0.05)
    assert x == (1995.0, "tinta")                                             # 2010 Yahoo = 1990 eToro; 2030 = 2009.8 >= tinta


def test_summary_counts_your_closes_against_what_the_bot_would_have_done():
    close_t = T0
    ledger = [
        decisions.entry("TP", "EURUSD", 1, origin="auto", net=2.5, close_t=close_t),
        decisions.entry("YOU", "EURUSD", 1, origin="auto", net=0.5, open_rate=1.1000, close_rate=1.1002, tp=1.1010, sl=1.0950,
                        notional=3000.0, open_t=close_t - timedelta(hours=1), close_t=close_t),
        decisions.entry("TP", "EURUSD", -1, origin="manual", net=1.2, close_t=close_t),
        decisions.entry("SKIP", "EURUSD", 1, px=1.1000, tp=1.1010, sl=1.0950, notional=3000.0, at=close_t),
    ]
    fetch = lambda *a, **k: path(close_t, [1.1002, 1.1006, 1.1012])          # noqa: E731 - dupa inchiderea ta, pretul atinge tinta
    o = decisions.summarize(ledger, close_t - timedelta(days=1), fetch, INST, CFG, [{"net": -3.0}], close_t + timedelta(hours=2))
    assert (o["bot_n"], round(o["bot_net"], 2)) == (1, 2.5)
    assert o["you_n"] == 1 and round(o["you_alt"], 2) == round(0.5 + (1.1010 - 1.1002) / 1.1 * 3000, 2)      # ar fi luat tinta
    assert (o["mine_n"], round(o["mine_net"], 2)) == (2, -1.8)               # comanda ta + una din eToro
    assert o["skip_n"] == 1 and o["skip_alt"] > 0
    assert o["effect"] < 0                                                   # inchiderea devreme + refuzul au costat
    t = msg.decisions_report(o, 7)
    assert "Lăsate botului: 1" in t and "Închise de tine" in t and "te-au costat" in t


def test_summary_without_prices_counts_your_close_as_neutral():
    ledger = [decisions.entry("OTHER", "EURUSD", 1, origin="auto", net=1.0, open_rate=1.1, close_rate=1.1002, tp=1.101, sl=1.095,
                              notional=3000.0, open_t=T0, close_t=T0)]
    o = decisions.summarize(ledger, T0 - timedelta(days=1), lambda *a, **k: None, INST, CFG, [], T0)
    assert o["you_miss"] == 1 and o["you_alt"] == o["you_net"] and o["effect"] == 0


def test_bot_records_who_opened_and_who_closed(monkeypatch):
    a, tg, br = make()
    a.unlocked = True
    a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001, "origin": "manual"})
    press(a, "open:1")
    pid = next(iter(br.pos))
    assert a.origin[pid] == "manual"
    press(a, f"close:{pid}")
    rows = [r for r in a.ledger if r["kind"] == "YOU"]
    assert rows and rows[0]["origin"] == "manual" and rows[0]["name"] == "EURUSD" and rows[0]["notional"] > 0


def test_refused_signal_goes_to_the_ledger_and_command_sends_report(monkeypatch):
    a, tg, br = make()
    a.unlocked = True
    a.propose("EURUSD", {"side": -1, "why": "test", "price": 1.1, "atr_pct": 0.001})
    press(a, "skip:1")
    assert [r["kind"] for r in a.ledger] == ["SKIP"] and a.ledger[0]["tp"] < 1.1
    a.ledger_since = (T0 - timedelta(days=3)).isoformat()
    a.handle({"kind": "text", "text": "decizii"})
    assert any(t.startswith("🧭 Deciziile tale") for t in tg.texts)
