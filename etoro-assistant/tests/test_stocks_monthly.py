"""Planul pe actiuni (Eugen, 19 oct): o data pe luna, verdictul regulii pe fondul Nasdaq-100 (peste/sub media pe 200 de zile), doar mesaj."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import state  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG  # noqa: E402

MON_NOV2 = datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc)        # luni 2 nov, prima zi lucratoare


def daily(last_close, n=260, end="2026-11-02", base=100.0):
    """Preturi zilnice pana la `end` inclusiv; ultima zi din octombrie are `last_close`; 2 nov (luna noua) are un pret care nu trebuie folosit."""
    idx = pd.bdate_range(end=end, periods=n, tz="UTC") + pd.Timedelta(hours=13, minutes=30)
    s = pd.Series(base, index=idx)
    s[s.index.month == 10] = base
    s.iloc[-2] = last_close                                          # 30 oct (vineri), ultima zi a lunii trecute
    s.iloc[-1] = 1.0 if last_close > base else 10_000.0              # 2 nov: daca ar fi folosit, ar inversa verdictul
    return pd.DataFrame({"open": s, "high": s, "low": s, "close": s})


def make(now, df, calls=None):
    tg, br = FakeTG(), FakeBroker()

    def fetch(sym, interval, rng):
        if calls is not None:
            calls.append((sym, interval, rng))
        if isinstance(df, Exception):
            raise df
        return df
    return A.Assistant(CFG, tg, br, fetch=fetch, now_fn=lambda: now, sleep=lambda s: None), tg


def test_above_average_says_hold_once_per_month_no_orders():
    calls = []
    a, tg = make(MON_NOV2, daily(130.0), calls)
    a.stocks_monthly(MON_NOV2)
    a.stocks_monthly(MON_NOV2)
    assert calls == [("QQQ", "1d", "2y")]                            # o singura citire, un singur mesaj
    assert len(tg.texts) == 1
    t = tg.texts[0]
    assert "30.10.2026" in t and "PESTE medie" in t and "ȚII" in t and "CNDX.L" in t and "nu pun niciun ordin" in t
    assert not a.broker.pos and not a.pending
    assert state.load().get("stocks_month") == "2026-11"             # tinut minte si dupa o repornire


def test_below_average_says_sell_even_at_a_loss():
    a, tg = make(MON_NOV2, daily(70.0))
    a.stocks_monthly(MON_NOV2)
    t = tg.texts[0]
    assert "SUB medie" in t and "VINZI" in t and "chiar dacă e pe minus" in t


def test_not_on_weekend_not_before_hour_not_twice_after_restart():
    sat = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
    early = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)
    for now in (sat, early):
        a, tg = make(now, daily(130.0))
        a.stocks_monthly(now)
        assert not tg.texts
    a, tg = make(MON_NOV2, daily(130.0))
    a.stocks_month = "2026-11"                                       # deja trimis luna asta (citit din starea salvata)
    a.stocks_monthly(MON_NOV2)
    assert not tg.texts


def test_price_error_reports_and_retries_later_not_every_loop():
    calls = []
    a, tg = make(MON_NOV2, RuntimeError("yahoo jos"), calls)
    a.stocks_monthly(MON_NOV2)
    a.stocks_monthly(MON_NOV2)
    assert len(calls) == 1 and a.stocks_month == ""                  # nu bombardeaza; reincearca dupa 30 de minute
    a.stocks_try -= 1801
    a.stocks_monthly(MON_NOV2)
    assert len(calls) == 2


def test_too_little_history_is_an_error_not_a_verdict():
    a, tg = make(MON_NOV2, daily(130.0, n=50))
    a.stocks_monthly(MON_NOV2)
    assert a.stocks_month == "" and not any("Regula zice" in t for t in tg.texts)


def test_disabled_in_config_sends_nothing():
    a, tg = make(MON_NOV2, daily(130.0))
    a.cfg = {**a.cfg, "stocks_monthly": {**a.cfg["stocks_monthly"], "enabled": False}}
    a.stocks_monthly(MON_NOV2)
    assert not tg.texts
