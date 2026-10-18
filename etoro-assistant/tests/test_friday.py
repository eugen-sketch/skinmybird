"""Vineri seara (T009, ales pe simulare): fara intrari noi dupa 18:00 ora Romaniei; la 22:00 lista pozitiilor care raman peste weekend."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import fake_scan, make, press  # noqa: E402

FRI_1830 = datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc)      # vineri 18:30 ora Romaniei
FRI_1700 = datetime(2026, 10, 23, 14, 0, tzinfo=timezone.utc)       # vineri 17:00
SIGS = ("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend")


def test_no_new_entries_friday_after_18_romania(monkeypatch):
    fake_scan(monkeypatch, {SIGS: 1})
    a, tg, br = make(FRI_1830)
    a.unlocked = True
    assert a.friday_cut(FRI_1830) and not a.friday_cut(FRI_1700)
    a.scan()
    assert not a.pending and not any("Semnal pe" in t for t in tg.texts)
    b, tg2, br2 = make(FRI_1700)
    b.unlocked = True
    b.scan()
    assert b.pending or any("Semnal pe" in t for t in tg2.texts)


def test_weekend_list_once_with_close_buttons():
    fri_22 = datetime(2026, 10, 23, 19, 5, tzinfo=timezone.utc)      # vineri 22:05 ora Romaniei
    a, tg, br = make(fri_22)
    a.unlocked = True
    a.propose("EURUSD", {"side": 1, "why": "test", "price": 1.1, "atr_pct": 0.001})
    press(a, "open:1")
    a.weekend_alert(fri_22)
    a.weekend_alert(fri_22)
    msgs = [(t, b) for t, b, _ in tg.sent if "Vine weekendul" in t]
    assert len(msgs) == 1 and any("close:" in d for row in msgs[0][1] for _, d in row)
    assert br.pos                                                      # nu inchide nimic singur
