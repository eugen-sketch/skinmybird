"""Custodie / WTI1 (Eugen, 22 oct): pe contul real botul nu deschide nimic; pune pe eToro tinta si plasa pe pozitiile lui Eugen si verifica."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import custody as C  # noqa: E402
from test_assistant import CFG, T0, FakeTG, fake_scan, press  # noqa: E402

TARGETS = {"targets": [{"pid": "11", "tp": 95.0, "sl": 107.8}, {"pid": "12", "tp": 94.0, "sl": 105.8}, {"pid": "13", "tp": 0.826}]}


class Br:
    """Ca eToro: 2 vanzari pe petrol + o cumparare USD/CHF; editarea se aplica dupa un apel de citire (asincron)."""

    def __init__(self, apply_edits=True, refuse=None):
        self.pos = {"11": {"id": "11", "name": "OIL", "side": -1, "open_rate": 98.07, "sl": 102.97, "tp": 0.01, "amount": 99.99},
                    "12": {"id": "12", "name": "OIL", "side": -1, "open_rate": 96.26, "sl": 101.05, "tp": 91.43, "amount": 100.0},
                    "13": {"id": "13", "name": "USDCHF", "side": 1, "open_rate": 0.82576, "sl": 0.81223, "tp": 0.83951, "amount": 60.0}}
        self.q = {"OIL": {"bid": 99.52, "ask": 99.56}, "USDCHF": {"bid": 0.8212, "ask": 0.82122}}
        self.edits, self.pending, self.opened, self.closed = [], [], [], []
        self.apply_edits, self.refuse = apply_edits, refuse or set()

    def credit(self):
        return 0.78

    def outside_invested(self):
        return 0.0

    def positions(self, fresh=False):
        if self.apply_edits:
            for pid, sl, tp in self.pending:
                if sl is not None:
                    self.pos[pid]["sl"] = sl
                if tp is not None:
                    self.pos[pid]["tp"] = tp
            self.pending = []
        return [dict(p) for p in self.pos.values()]

    def quotes(self, names):
        return {n: self.q[n] for n in names if n in self.q}

    def price(self, name):
        return self.q[name]["bid"]

    def edit_levels(self, pid, sl, tp):
        if pid in self.refuse:
            raise RuntimeError("refuzat")
        self.edits.append((pid, sl, tp))
        self.pending.append((pid, sl, tp))

    def open(self, *a, **k):
        self.opened.append(a)
        return "999"

    def close(self, pid, name):
        self.closed.append(pid)


def make(monkeypatch, br=None, targets=TARGETS):
    monkeypatch.setenv("CUSTODY_JSON", json.dumps(targets))
    tg, br = FakeTG(), br or Br()
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None, real=True)
    a.custody = C.load_targets(json.dumps(targets))
    return a, tg, br


def test_load_targets_ignores_bad_input():
    assert C.load_targets(None) == [] and C.load_targets("nu e json") == [] and C.load_targets('{"targets": [{"pid": "1"}]}') == []
    assert C.load_targets(json.dumps(TARGETS))[2] == {"pid": "13", "tp": 0.826, "sl": None}


def test_check_wrong_side_is_refused():
    assert C.check({"tp": 95.0, "sl": 107.8}, -1, 99.52, 99.56) is None                 # vanzare: tinta sub, plasa peste
    assert C.check({"tp": 101.0}, -1, 99.52, 99.56)                                       # tinta peste pret la vanzare: gresit
    assert C.check({"sl": 99.0}, -1, 99.52, 99.56)                                        # plasa sub pret la vanzare: gresit
    assert C.check({"tp": 0.826}, 1, 0.8212, 0.82122) is None and C.check({"tp": 0.82}, 1, 0.8212, 0.82122)


def test_prompt_then_ok_sets_exactly_the_levels_and_verifies(monkeypatch):
    a, tg, br = make(monkeypatch)
    a.custody_prompt()
    text, buttons, _ = tg.sent[-1]
    assert "custodie" in text and "ținta 95" in text and "plasa 107.8" in text and buttons[0][0][1] == "custody:ok"
    press(a, "custody:ok")
    assert br.edits == [("11", 107.8, 95.0), ("12", 105.8, 94.0), ("13", None, 0.826)]
    assert br.pos["11"]["tp"] == 95.0 and br.pos["12"]["sl"] == 105.8 and br.pos["13"]["tp"] == 0.826
    assert br.pos["13"]["sl"] == 0.81223                                                 # plasa USD/CHF neatinsa
    rep = tg.texts[-1]
    assert rep.count("✅") == 3 and "verificat pe eToro" in rep
    assert a.custody_done == C.signature(a.custody)
    assert not br.opened and not br.closed                                                # nu deschide si nu inchide nimic


def test_no_new_trades_in_custody(monkeypatch):
    fake_scan(monkeypatch, {("london_breakout", "rsi_rev30", "pullback45", "donchian24_trend"): 1})
    a, tg, br = make(monkeypatch)
    a.unlocked = a.autotrade = True
    a.scan()
    assert not a.pending and not br.opened


def test_not_applied_on_eToro_is_reported_and_not_marked_done(monkeypatch):
    a, tg, br = make(monkeypatch, Br(apply_edits=False))
    a.apply_custody()
    assert "încă nu văd nivelurile" in tg.texts[-1] and a.custody_done == ""


def test_refused_and_closed_positions_are_reported(monkeypatch):
    br = Br(refuse={"12"})
    del br.pos["13"]
    a, tg, br = make(monkeypatch, br)
    a.apply_custody()
    rep = tg.texts[-1]
    assert "eToro a refuzat" in rep and "poziția 13 nu mai e deschisă" in rep and a.custody_done == ""
    assert br.pos["11"]["tp"] == 95.0                                                     # cea buna s-a aplicat


def test_stale_quotes_fall_back_to_hourly_price(monkeypatch):
    """22 oct seara: cotatia eToro venea cu ~44 min intarziere si botul refuza («nu am pret proaspat»)."""
    br = Br()
    br.quotes = lambda names: {}
    a, tg, br = make(monkeypatch, br)
    a.apply_custody()
    assert br.pos["11"]["tp"] == 95.0 and br.pos["13"]["tp"] == 0.826 and "verificat pe eToro" in tg.texts[-1]
    assert C.check({"tp": 99.3}, -1, 99.52, 99.52, margin=0.005)                         # prea aproape de un pret aproximativ: nu


class Api:
    def find_instrument_id(self, s):
        return {"BTC": 100000, "BNB": 100030}[s]


def make_open(monkeypatch, opens, br=None):
    raw = json.dumps({"open": opens})
    monkeypatch.setenv("CUSTODY_JSON", raw)
    tg, br = FakeTG(), br or Br()
    br.api, br.ids, br.rev = Api(), {}, {}
    br.q.update({"BTC": {"bid": 81000.0, "ask": 81050.0}, "BNB": {"bid": 747.0, "ask": 747.5}})
    br.opened_args = []
    br.open = lambda *a, **k: (br.opened_args.append(a), f"9{len(br.opened_args)}")[1]
    a = A.Assistant(CFG, tg, br, fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None, real=True)
    a.custody, a.custody_open = [], C.load_opens(raw)
    return a, tg, br


def test_load_opens_only_small_buys():
    raw = json.dumps({"open": [{"symbol": "btc", "amount": 32, "tp_pct": 5}, {"symbol": "X", "amount": 500, "tp_pct": 5},
                               {"symbol": "Y", "amount": 20, "tp_pct": 5, "lev": 10}, {"symbol": "Z"}]})
    assert C.load_opens(raw) == [{"symbol": "BTC", "amount": 32.0, "tp_pct": 5.0, "lev": 1}]
    assert C.load_opens(json.dumps(TARGETS)) == [] and C.load_targets(raw) == []


def test_opens_after_ok_once_with_tp_and_wide_net(monkeypatch):
    a, tg, br = make_open(monkeypatch, [{"symbol": "BTC", "amount": 32, "tp_pct": 5}, {"symbol": "BNB", "amount": 32, "tp_pct": 5}])
    a.custody_prompt()
    assert "deschid BTC" in tg.sent[-1][0] and tg.sent[-1][1][0][0][1] == "custody:ok"
    press(a, "custody:ok")
    assert br.opened_args == [("BTC", 1, 32.0, 1, 40525.0, 85102.5), ("BNB", 1, 32.0, 1, 373.75, 784.88)]
    assert tg.texts[-1].count("✅") == 2
    a.apply_custody()                                                                   # a doua oara: nimic nou
    assert len(br.opened_args) == 2
    a.custody_prompt()
    assert "deja pus" in tg.texts[-1]


def test_unconfirmed_open_is_never_resent(monkeypatch):
    a, tg, br = make_open(monkeypatch, [{"symbol": "BTC", "amount": 32, "tp_pct": 5}])

    def boom(*a_, **k):
        raise A.OrderUnconfirmed("neclar", set(), None, None)
    br.open = boom
    a.apply_custody()
    assert "NU îl trimit a doua oară" in tg.texts[-1] and a.custody_opened == ["BTC:32:5:1"]


def test_already_done_is_not_asked_again(monkeypatch):
    a, tg, br = make(monkeypatch)
    a.custody_done = C.signature(a.custody)
    a.custody_prompt()
    assert "deja pus" in tg.texts[-1] and not tg.sent[-1][1]


def test_demo_never_reads_custody(monkeypatch):
    monkeypatch.setenv("CUSTODY_JSON", json.dumps(TARGETS))
    a = A.Assistant(CFG, FakeTG(), Br(), fetch=lambda *x, **k: None, now_fn=lambda: T0, sleep=lambda s: None, real=False)
    assert a.custody == []
