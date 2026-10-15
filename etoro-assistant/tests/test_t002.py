"""T002: cazul USD/JPY din 15.10 – cotatie eToro veche => tinta reala +0,67 $ in loc de +2,99 $, dar mesajul spunea „ținta atinsă”."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import broker as B  # noqa: E402
from test_assistant import CFG, FakeTG, T0  # noqa: E402
from test_spec_audit import HistBroker  # noqa: E402


class FakeApi:
    def __init__(self, rates):
        self._r = rates

    def rates(self, ids):
        return self._r


def _rate(bid, age_s):
    d = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%S.123456Z")
    return {"bid": bid, "ask": bid + 0.001, "date": d, "conversionRateBid": 0.0063, "conversionRateAsk": 0.0063}


def test_stale_etoro_quote_is_ignored_fresh_one_is_kept():
    api = FakeApi({5: _rate(157.90, 41 * 60), 1: _rate(1.1200, 5)})        # USD/JPY vechi de 41 min, EUR/USD proaspat
    b = B.EToroBroker(api, {"USDJPY": 5, "EURUSD": 1})
    q = b.quotes(["USDJPY", "EURUSD"])
    assert "USDJPY" not in q and q["EURUSD"]["bid"] == 1.12                # apelantii trec pe lumanarea orara, la zi


JPY_TRADE = {"net": 0.67, "close_rate": 158.188, "close_time": "2026-10-15T15:06:14Z", "open_rate": 158.123,
             "sl": 156.983, "tp": 158.188, "side": 1, "fees": 0.0}


def _position(plan_tp_usd):
    real = {"id": "77", "name": "USDJPY", "side": 1, "open_rate": 158.123, "units": 1635.3, "amount": 54.51, "leverage": 30,
            "sl": 156.983, "tp": 158.188, "time": ""}
    known = {**real, "last_pnl": 0.0, "tp_usd": plan_tp_usd, "sl_usd": 11.8}
    return real, known


def _assistant(trade):
    tg, br = FakeTG(), HistBroker({"77": trade})
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None)
    return a, tg, br


def test_displayed_target_matches_real_etoro_target_and_warns_once():
    a, tg, br = _assistant(JPY_TRADE)
    real, known = _position(2.99)                                           # planul spunea +2,99 $
    br.pos["77"], a.known["77"] = real, known
    a.monitor(check_basket=False)
    a.monitor(check_basket=False)
    assert abs(a.known["77"]["tp_usd"] - 0.67) < 0.02 and a.known["77"]["tp_usd_plan"] == 2.99     # Status arata cifra reala
    warn = [t for t in tg.texts if "ținta reală pe eToro" in t]
    assert len(warn) == 1 and "$0.67" in warn[0] and "$2.99" in warn[0]


def test_close_far_below_target_is_not_called_target_reached():
    a, tg, br = _assistant(JPY_TRADE)
    real, known = _position(2.99)
    br.pos["77"], a.known["77"] = real, known
    a.monitor(check_basket=False)
    br.pos.clear()                                                          # poziția s-a închis singură la nivelul de pe eToro
    a.monitor(check_basket=False)
    a.monitor(check_basket=False)
    txt = [t for t in tg.texts if "Poziția e închisă" in t]
    assert len(txt) == 1
    assert "ținta a fost atinsă" not in txt[0] and "ieșit la nivelul de profit setat" in txt[0]
    assert "+$0.67" in txt[0] and "$2.99" in txt[0]                         # rezultatul și ținta planificată, ambele cinstit


def test_normal_target_hit_still_says_target_reached():
    trade = {**JPY_TRADE, "net": 2.60}
    a, tg, br = _assistant(trade)
    real, known = _position(2.60)                                           # planul = ce se întâmplă real
    real["tp"] = 158.123 + 0.2552                                           # nivelul real corespunde planului
    trade["close_rate"] = trade["tp"] = real["tp"]
    br.pos["77"], a.known["77"] = real, known
    a.monitor(check_basket=False)
    br.pos.clear()
    a.monitor(check_basket=False)
    a.monitor(check_basket=False)
    txt = [t for t in tg.texts if "Poziția e închisă" in t]
    assert len(txt) == 1 and "ținta a fost atinsă" in txt[0]
    assert not [t for t in tg.texts if "ținta reală pe eToro" in t]         # fără avertisment când planul = realitatea
