import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import trader  # noqa: E402

CFG = json.loads((Path(__file__).parent.parent / "config.json").read_text())
P = CFG["params"]


def daily(path, end="2026-10-08"):
    p = np.asarray(path, dtype=float)
    idx = pd.bdate_range(end=pd.Timestamp(end, tz="UTC"), periods=len(p))
    return pd.DataFrame({"open": p, "high": p * 1.004, "low": p * 0.996, "close": p}, index=idx)


def uptrend_then_dip(extra=()):
    base = 4000 * np.exp(np.cumsum(np.full(260, 0.0016) + np.sin(np.arange(260)) * 0.0006))
    dip = base[-1] * np.cumprod([0.988, 0.985, 0.984])
    end = pd.Timestamp("2026-10-08") + pd.offsets.BDay(len(extra))      # barele noi vin DUPA ultima bara de baza
    return daily(np.concatenate([base, dip, np.asarray(extra, dtype=float)]), end=end.strftime("%Y-%m-%d"))


def _cfg(names=("SP500",)):
    cfg = json.loads(json.dumps(CFG))
    cfg["instruments"] = [i for i in cfg["instruments"] if i["name"] in names]
    return cfg


NOW = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)


def test_buy_signal_on_sharp_dip_in_uptrend():
    s = trader.daily_signal(uptrend_then_dip(), P, NOW)
    assert s["side"] == 1 and s["rsi2"] < 5


def test_incomplete_todays_bar_is_ignored():
    df = uptrend_then_dip()
    today = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}, index=[pd.Timestamp("2026-10-09 00:00", tz="UTC")])
    s = trader.daily_signal(pd.concat([df, today]), P, NOW)
    assert s["price"] > 100 and s["side"] == 1


def test_no_signal_in_downtrend():
    df = daily(4000 * np.exp(np.cumsum(np.full(300, -0.0008) + np.sin(np.arange(300)) * 0.0006)))
    assert trader.daily_signal(df, P, NOW)["side"] == 0


def test_open_then_close_on_recovery(monkeypatch):
    notes = []
    monkeypatch.setattr(trader.notify, "send", lambda t: notes.append(t))
    monkeypatch.setattr(trader.time, "sleep", lambda s: None)
    state = {}
    broker = trader.PaperBroker(state)
    df = uptrend_then_dip()
    monkeypatch.setattr(broker, "price", lambda inst: float(df["close"].iloc[-1]))
    cfg = _cfg()
    trader.run_daily(cfg, state, broker, {"SP500": df}, NOW)
    tr = state["open"]["SP500"]
    assert tr["notional"] >= 1000 and tr["amount"] <= 140 / 2 and any("Am cumpărat" in n for n in notes)
    rec = uptrend_then_dip([df["close"].iloc[-1] * 1.015, df["close"].iloc[-1] * 1.03])
    monkeypatch.setattr(broker, "price", lambda inst: float(rec["close"].iloc[-1]))
    trader.run_daily(cfg, state, broker, {"SP500": rec}, datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc))
    assert "SP500" not in state["open"] and any("vândut" in n or "închisă" in n for n in notes)


def test_stop_loss_in_paper_mode(monkeypatch):
    notes = []
    monkeypatch.setattr(trader.notify, "send", lambda t: notes.append(t))
    state = {}
    broker = trader.PaperBroker(state)
    df = uptrend_then_dip()
    monkeypatch.setattr(broker, "price", lambda inst: float(df["close"].iloc[-1]))
    cfg = _cfg()
    trader.run_daily(cfg, state, broker, {"SP500": df}, NOW)
    sl = state["open"]["SP500"]["sl"]
    crash = uptrend_then_dip([sl * 1.02, sl * 0.97])
    trader.run_daily(cfg, state, broker, {"SP500": crash}, datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc))
    assert "SP500" not in state["open"] and state["equity"] < 140 and any("plasa de siguranță" in n for n in notes)


def test_only_two_slots_for_140(monkeypatch):
    monkeypatch.setattr(trader.notify, "send", lambda t: None)
    state = {}
    broker = trader.PaperBroker(state)
    df = uptrend_then_dip()
    monkeypatch.setattr(broker, "price", lambda inst: float(df["close"].iloc[-1]))
    names = ["SP500", "NASDAQ", "DOW", "DAX", "FTSE"]
    trader.run_daily(_cfg(names), state, broker, {n: df for n in names}, NOW)
    assert len(state["open"]) == 2 and sum(o["amount"] for o in state["open"].values()) <= 140


def test_no_action_before_morning_or_weekend(monkeypatch):
    monkeypatch.setattr(trader.notify, "send", lambda t: None)
    for when in (datetime(2026, 10, 9, 5, 0, tzinfo=timezone.utc), datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)):
        state = {}
        broker = trader.PaperBroker(state)
        df = uptrend_then_dip()
        monkeypatch.setattr(broker, "price", lambda inst: float(df["close"].iloc[-1]))
        trader.run_daily(_cfg(), state, broker, {"SP500": df}, when)
        assert not state.get("open")
