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


def frame(prices, end="2026-10-07 12:00"):
    p = np.asarray(prices, dtype=float)
    idx = pd.date_range(end=pd.Timestamp(end, tz="UTC") - pd.Timedelta(hours=1), periods=len(p), freq="h")
    return pd.DataFrame({"open": p, "high": p + 0.2, "low": p - 0.2, "close": p}, index=idx)


def crash(n=200):
    x = np.concatenate([np.full(n - 30, 80.0) + np.sin(np.arange(n - 30)) * 0.3, np.linspace(80, 72, 30)])
    return frame(x)


def test_sizing_respects_margin_and_leverage_caps():
    z = trader.size_position(140, 80.0, 0.5, P, 10)
    assert z["leverage"] <= 10 and z["amount"] <= 140 * 0.4 * 1.5
    assert z["risk_usd"] > 0


def test_signal_buy_after_crash():
    s = trader.compute_signal(crash(), P)
    assert s["side"] == 1 and s["rsi"] < 20


def test_paper_open_then_tp_close_updates_equity(monkeypatch):
    notes = []
    monkeypatch.setattr(trader.notify, "send", lambda t: notes.append(t))
    state = {}
    broker = trader.PaperBroker(state)
    monkeypatch.setattr(broker, "price", lambda inst: 72.0)
    cfg = json.loads(json.dumps(CFG))
    cfg["instruments"] = cfg["instruments"][:1]
    now = datetime(2026, 10, 7, 12, 5, tzinfo=timezone.utc)
    df = crash()
    trader.run_once(cfg, state, broker, {"WTI": df}, now)
    assert "WTI" in state["open"] and any("BUY" in n for n in notes)
    tr = state["open"]["WTI"]
    # pretul sare peste TP dupa deschidere
    up = pd.DataFrame({"open": [tr["tp"] + 1], "high": [tr["tp"] + 2], "low": [tr["tp"]], "close": [tr["tp"] + 1]},
                      index=[pd.Timestamp(now) + pd.Timedelta(hours=1)])
    trader.run_once(cfg, state, broker, {"WTI": pd.concat([df, up])}, now + pd.Timedelta(hours=2))
    assert "WTI" not in state["open"] and state["equity"] > 140
    assert any("închis" in n for n in notes)


def test_no_trading_on_weekend(monkeypatch):
    monkeypatch.setattr(trader.notify, "send", lambda t: None)
    state, cfg = {}, json.loads(json.dumps(CFG))
    cfg["instruments"] = cfg["instruments"][:1]
    broker = trader.PaperBroker(state)
    trader.run_once(cfg, state, broker, {"WTI": crash()}, datetime(2026, 10, 10, 12, 5, tzinfo=timezone.utc))
    assert not state.get("open")


def test_demo_only_guard():
    import etoro
    api = etoro.EToroDemo("k", "u", verbose=False)
    try:
        api._req("POST", "/api/v1/trading/execution/market-open-orders/by-amount", body={}, trading=True)
        assert False
    except etoro.EToroError as e:
        assert "REFUZ" in str(e)
