"""Buget separat pentru petrol (cerere proprietar, test o saptamana pe real): 105 $ rezervati doar pentru petrol; forexul nu-i poate folosi."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_assistant import CFG, make, make_real  # noqa: E402


def test_config_reserves_105_for_oil():
    assert CFG["oil_reserve_usd"] == 105


def test_oil_gets_its_own_budget_and_forex_shares_the_rest():
    a, tg, br = make_real(278.18)
    a.cfg = {**a.cfg, "max_positions": 4}                                         # ca in modul agresiv de pe real (4 poziții, una e a petrolului)
    assert a.oil_reserve() == 105.0
    m_oil, lev_oil, ex_oil = a.sizing(a.inst["OIL"])
    assert m_oil == 105.0 and lev_oil == 10 and ex_oil == 1050.0                 # toata rezerva, expunere peste minimul eToro (1.000 $)
    m_fx, lev_fx, _ = a.sizing(a.inst["EURUSD"])
    assert abs(m_fx - 57.72) < 0.01 and lev_fx == 30                              # (278,18 - 105) / 3 pozitii de forex


def test_forex_cannot_touch_the_oil_reserve_but_oil_can_use_everything_it_needs():
    a, tg, br = make_real(278.18)
    assert abs(a.free_margin("EURUSD") - 173.18) < 0.01                           # forexul vede doar ce ramane dupa rezerva
    assert abs(a.free_margin("OIL") - 278.18) < 0.01                              # petrolul vede tot
    a.known["x"] = {"id": "x", "name": "EURUSD", "amount": 173.0, "side": 1}      # forexul si-a luat toata partea lui
    a.real_balance = 278.18 - 173.0
    assert a.free_margin("GBPUSD") < 1.0                                          # nu mai incape niciun forex nou
    assert a.free_margin("OIL") > 100.0                                           # dar petrolul are inca banii lui


def test_open_oil_position_or_proposal_uses_up_the_reserve():
    a, tg, br = make_real(278.18)
    a.known["o"] = {"id": "o", "name": "OIL", "amount": 105.0, "side": 1}
    a.real_balance = 278.18 - 105.0
    assert abs(a.free_margin("EURUSD") - 173.18) < 0.01                           # rezerva e consumata de pozitia de petrol, forexul vede restul
    a.known.clear()
    a.real_balance = 278.18
    a.pending[1] = {"name": "OIL", "amount": 105.0, "side": 1}
    assert abs(a.free_margin("EURUSD") - 173.18) < 0.01                           # propunerea pe petrol tine rezerva ocupata


def test_small_or_demo_accounts_keep_the_old_behavior():
    small, _, _ = make_real(150.0)                                                # prea putin pentru rezerva + 2 pozitii
    assert small.oil_reserve() == 0.0 and abs(small.free_margin("EURUSD") - 150.0) < 0.01
    assert small.sizing(small.inst["OIL"])[0] == 101.0 or small.sizing(small.inst["OIL"])[0] > 100.0
    demo, _, _ = make()
    assert demo.oil_reserve() == 0.0                                              # doar pe cont real


def test_status_tells_about_the_oil_reserve():
    a, tg, br = make_real(278.18)
    a.unlocked = True
    a.status()
    assert "Rezervat pentru petrol" in tg.texts[-1] and "$105.00" in tg.texts[-1]
