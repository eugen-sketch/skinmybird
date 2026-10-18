"""Reparatiile din verificarea lui Sorin (19 oct): cosul reverifica «pe plus», eroare neasteptata dupa trimiterea ordinului = rezultat neclar,
ziua numarata dupa ora Romaniei."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import make, press  # noqa: E402


def test_basket_skips_position_that_turned_red_right_before_closing():
    a, tg, br = make()
    a.unlocked = True
    for n in ("EURUSD", "GBPUSD"):
        a.propose(n, {"side": 1, "why": "test", "price": br.prices[n], "atr_pct": 0.001})
    press(a, "open:1")
    press(a, "open:2")
    ids = list(br.pos)
    for pid in ids:
        a.known[pid]["last_pnl"] = 3.0
    a.quote_pnl = lambda pos, q: None
    a.pnl = lambda pos, price: 3.0                                   # la citire: amandoua pe plus, cosul se declanseaza
    fresh = {ids[0]: 2.0, ids[1]: -0.05}                              # chiar inainte de inchidere, a doua a trecut pe rosu
    a.fresh_pnl = lambda p: fresh[p["id"]]
    a.monitor()
    assert ids[0] in br.closed and ids[1] not in br.closed and ids[1] in br.pos


def test_unexpected_error_after_sending_is_unclear_not_nothing():
    a, tg, br = make()
    a.unlocked = True
    a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001})

    def boom(*x, **k):
        raise KeyError("raspuns ciudat")
    br.open = boom
    press(a, "open:1")
    assert a.adopt and a.adopt[0]["name"] == "EURUSD"
    assert any("eroare neașteptată după trimitere" in t for t in tg.texts) and not any("Nu am deschis nimic" in t for t in tg.texts)


def test_day_is_counted_in_romanian_time():
    late = datetime(2026, 10, 20, 22, 30, tzinfo=timezone.utc)       # 01:30 ora Romaniei, miercuri 21
    a, tg, br = make(late)
    a.add_realized(-4.0)
    assert a.day == "2026-10-21" and a.day_pnl_today() == -4.0
