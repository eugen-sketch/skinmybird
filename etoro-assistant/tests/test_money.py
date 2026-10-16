"""Autoverificare: botul observă singur banii intrați sau ieșiți din cont și te anunță o singură dată; profitul și deschiderile nu dau alarme false."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import make_real  # noqa: E402


def texts(tg, word):
    return [t for t in tg.texts if word in t]


def test_deposit_is_announced_once_after_two_confirmations():
    a, tg, br = make_real(150.0)
    a.monitor()                                   # prima citire: doar punctul de plecare
    br.balance += 100.0                           # au intrat 100 $
    a.monitor()                                   # prima dată: așteaptă confirmarea (poate fi o citire greșită)
    assert not texts(tg, "bani noi")
    a.monitor()                                   # a doua oară: confirmat
    msgs = texts(tg, "Au intrat bani noi")
    assert len(msgs) == 1 and "+$100.00" in msgs[0] and "$250.00" in msgs[0]
    a.monitor()
    a.monitor()
    assert len(texts(tg, "Au intrat bani noi")) == 1          # nu se repetă


def test_withdrawal_is_announced():
    a, tg, br = make_real(300.0)
    a.monitor()
    br.balance -= 80.0
    a.monitor()
    a.monitor()
    msgs = texts(tg, "Au ieșit bani")
    assert len(msgs) == 1 and "-$80.00" in msgs[0]


def test_a_single_wrong_reading_gives_no_alarm():
    a, tg, br = make_real(150.0)
    a.monitor()
    br.balance += 100.0
    a.monitor()                                   # o citire ciudată
    br.balance -= 100.0                           # a doua citire revine la normal
    a.monitor()
    a.monitor()
    assert not texts(tg, "bani") and not texts(tg, "Au ieșit")


def test_small_changes_and_trading_profit_are_not_deposits():
    a, tg, br = make_real(150.0)
    a.monitor()
    br.balance += 3.5                             # un profit mic, nu o depunere
    for _ in range(3):
        a.monitor()
    assert not texts(tg, "Au intrat bani")


def test_opening_and_closing_a_position_with_profit_gives_no_alarm():
    a, tg, br = make_real(166.0)
    a.monitor()
    br.pos["1"] = {"id": "1", "name": "EURUSD", "side": 1, "open_rate": 1.1, "units": 1600.0, "amount": 55.0, "leverage": 30,
                   "sl": 1.09, "tp": 1.11, "time": ""}
    a.bot_pids.add("1")
    a.monitor()                                   # poziție nouă: banii liberi scad cu marja, totalul rămâne
    a.monitor()
    br.pos.pop("1")                               # închisă la țintă: banii liberi cresc cu marja + profit
    br.balance += 2.5
    for _ in range(4):
        a.monitor()
    assert not texts(tg, "Au intrat bani") and not texts(tg, "Au ieșit bani")
