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


def frame(prices, end="2026-10-07 12:00", noise=0.0004):
    p = np.asarray(prices, dtype=float)
    idx = pd.date_range(end=pd.Timestamp(end, tz="UTC") - pd.Timedelta(hours=1), periods=len(p), freq="h")
    return pd.DataFrame({"open": p, "high": p + noise, "low": p - noise, "close": p}, index=idx)


def breakout_day(direction=1):
    """~3 zile plate, apoi azi: interval asiatic 1.1000±, spargere la 08:00 UTC."""
    base = np.full(24 * 3, 1.1000) + np.sin(np.arange(24 * 3)) * 0.0002
    today = np.full(8, 1.1000)                      # 00:00-07:00
    today[-1] = 1.1000 + direction * 0.0030         # bara 07:00 sparge... (ultima bara completa = 07:00)
    prices = np.concatenate([base, today])
    return frame(prices, end="2026-10-07 08:00")


def crash(n=200):
    x = np.concatenate([np.full(n - 30, 80.0) + np.sin(np.arange(n - 30)) * 0.3, np.linspace(80, 72, 30)])
    return frame(x, noise=0.2)


def test_london_breakout_buy_and_sell():
    assert trader.london_breakout(breakout_day(+1)) == 1
    assert trader.london_breakout(breakout_day(-1)) == -1


def test_london_breakout_only_first_breakout_of_day():
    df = breakout_day(+1)
    ts = df.index[-1] + pd.Timedelta(hours=1)
    df.loc[ts] = [1.103, 1.1035, 1.1025, 1.1032]   # a doua bara peste interval: nu mai e semnal
    assert trader.london_breakout(df) == 0


def test_three_equal_slots_with_dollar_targets():
    z = trader.size_slots(140, 1.10, P, 30)
    assert z["leverage"] == 30 and abs(z["amount"] * 3 - 140) < 0.05 and z["notional"] >= 1000
    gain = z["tp_dist"] / 1.10 * z["notional"]
    assert abs(gain - P["tp_usd"]) < 0.01
    assert trader.size_slots(140, 1.10, P, 20) is None          # 3 x 46.66 x 20 = 933$ < minim eToro 1000$


def test_union_signals_conflict_gives_no_trade():
    df = breakout_day(+1)        # London: BUY, dar RSI foarte mare -> rsi25 zice SELL => conflict => nimic
    assert trader.compute_signal(df, {**P, "signals": ["london_breakout", "rsi_rev25"]})["side"] == 0
    assert trader.compute_signal(df, {**P, "signals": ["london_breakout"]})["side"] == 1


def test_rsi_strategy_still_works():
    p = {**P, "strategy": "rsi_reversion"}
    s = trader.compute_signal(crash(), p)
    assert s["side"] == 1 and s["rsi"] < 20


def _cfg(names):
    cfg = json.loads(json.dumps(CFG))
    cfg["instruments"] = [i for i in cfg["instruments"] if i["name"] in names]
    cfg["params"]["signals"] = ["london_breakout"]       # testele de flux folosesc doar spargerea Londrei
    return cfg


def test_paper_buy_then_tp_updates_equity(monkeypatch):
    notes = []
    monkeypatch.setattr(trader.notify, "send", lambda t: notes.append(t))
    state = {}
    broker = trader.PaperBroker(state)
    monkeypatch.setattr(broker, "price", lambda inst: 1.1030)
    cfg = _cfg(["EURUSD"])
    now = datetime(2026, 10, 7, 8, 5, tzinfo=timezone.utc)
    df = breakout_day(+1)
    trader.run_once(cfg, state, broker, {"EURUSD": df}, now)
    assert "EURUSD" in state["open"] and any("BUY" in n for n in notes)
    tr = state["open"]["EURUSD"]
    up = pd.DataFrame({"open": [tr["tp"]], "high": [tr["tp"] + 0.001], "low": [tr["tp"] - 0.0001], "close": [tr["tp"]]},
                      index=[df.index[-1] + pd.Timedelta(hours=2)])
    trader.run_once(cfg, state, broker, {"EURUSD": pd.concat([df, up])}, now + pd.Timedelta(hours=2))
    assert "EURUSD" not in state["open"] and state["equity"] > 140
    assert any("închis" in n for n in notes)


def test_margin_budget_limits_parallel_positions(monkeypatch):
    monkeypatch.setattr(trader.notify, "send", lambda t: None)
    state = {}
    broker = trader.PaperBroker(state)
    monkeypatch.setattr(broker, "price", lambda inst: 1.1030)
    names = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"]
    cfg = _cfg(names)
    now = datetime(2026, 10, 7, 8, 5, tzinfo=timezone.utc)
    trader.run_once(cfg, state, broker, {n: breakout_day(+1) for n in names}, now)
    used = sum(o["amount"] for o in state["open"].values())
    assert 1 <= len(state["open"]) < len(names) and len(state["open"]) == 3 and used <= 140.0


def test_no_trading_on_weekend(monkeypatch):
    monkeypatch.setattr(trader.notify, "send", lambda t: None)
    state = {}
    broker = trader.PaperBroker(state)
    monkeypatch.setattr(broker, "price", lambda inst: 1.1030)
    trader.run_once(_cfg(["EURUSD"]), state, broker, {"EURUSD": breakout_day(+1)},
                    datetime(2026, 10, 10, 8, 5, tzinfo=timezone.utc))
    assert not state.get("open")


def test_demo_only_guard():
    import etoro
    api = etoro.EToroDemo("k", "u", verbose=False)
    try:
        api._req("POST", "/api/v1/trading/execution/market-open-orders/by-amount", body={}, trading=True)
        assert False
    except etoro.EToroError as e:
        assert "REFUZ" in str(e)
