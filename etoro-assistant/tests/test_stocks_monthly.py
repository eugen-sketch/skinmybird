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


ON = {**CFG, "stocks_monthly": {**CFG["stocks_monthly"], "enabled": True}}    # oprit in config (Eugen, 19 oct); testele il pornesc local


def make(now, df, calls=None):
    tg, br = FakeTG(), FakeBroker()

    def fetch(sym, interval, rng):
        if calls is not None:
            calls.append((sym, interval, rng))
        if isinstance(df, Exception):
            raise df
        return df
    return A.Assistant(ON, tg, br, fetch=fetch, now_fn=lambda: now, sleep=lambda s: None), tg


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
    a.cfg = CFG                                                      # configul real: oprit
    a.stocks_monthly(MON_NOV2)
    assert not tg.texts


# ---- fondul Nasdaq cumparat pe acelasi cont: botul de forex nu-l socoteste pierdere si nu-l amesteca in profit
from test_assistant import RealBroker, T0  # noqa: E402
import broker as broker_mod  # noqa: E402


class FundBroker(RealBroker):
    def __init__(self, balance, fund=0.0):
        super().__init__(balance)
        self.fund = fund

    def credit(self):
        return super().credit() - self.fund

    def outside_invested(self):
        return self.fund


def test_moving_half_into_the_fund_does_not_trigger_the_account_alarm():
    tg, br = FakeTG(), FundBroker(274.0)
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None, real=True)
    a.refresh_real()
    a.account_alarm()
    br.fund = 137.0                                                    # Eugen pune jumatate in fond
    a.refresh_real()
    a.account_alarm()
    assert not any("Contul a coborât" in t for t in tg.texts)
    assert a.equity() == 137.0 and a.max_pos() == CFG["max_positions_small"]   # forexul lucreaza doar cu jumatatea lui
    br.fund, br.balance = 0.0, 274.0 - 60.0                             # pierdere reala de 60 $ pe forex (fondul vandut, bani inapoi)
    a.refresh_real()
    a.account_alarm()
    assert any("Contul a coborât" in t for t in tg.texts)               # alarma ramane pentru pierderi adevarate


def test_fund_sale_is_not_counted_as_forex_profit():
    class TB(FakeBroker):
        def closed_trades(self, d):
            return [{"id": "1", "net": 3.0, "close_time": "2026-10-09T10:00:00Z", "name": "EURUSD"},
                    {"id": "2", "net": -12.0, "close_time": "2026-10-09T11:00:00Z", "name": None}]   # fondul Nasdaq vandut
    a = A.Assistant(CFG, FakeTG(), TB(), fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None, real=True)
    a.since = "2026-10-09"
    assert a.reconcile()
    assert a.total_pnl == 3.0 and a.n_total == 1


def test_broker_counts_only_positions_outside_the_bot_list():
    class Api:
        def positions(self, fresh=False):
            return [{"instrumentID": 1, "amount": 55.0}, {"instrumentID": 8015, "amount": 137.0}]
    b = broker_mod.EToroBroker(Api(), {"EURUSD": 1})
    assert b.outside_invested() == 137.0 and [p["name"] for p in b.positions()] == []   # pozitia EURUSD fara id e ignorata oricum
