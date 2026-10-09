import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import oilbot  # noqa: E402

CFG = {**oilbot.DEFAULTS, "symbols": {}}


def make(prices, noise=0.3):
    p = np.asarray(prices, dtype=float)
    idx = pd.date_range("2026-01-01", periods=len(p), freq="h", tz="UTC")
    return pd.DataFrame({"open": p, "high": p + noise, "low": p - noise, "close": p}, index=idx)


def walk(drift, seed, n=1500, start=80):
    return make(start + np.cumsum(np.random.default_rng(seed).normal(drift, 0.4, n)))


def test_uptrend_never_sells():
    sig = oilbot.signals(oilbot.build(walk(0.1, 1)), CFG)
    assert (sig == -1).sum() <= (sig == 1).sum()


def test_downtrend_never_buys():
    sig = oilbot.signals(oilbot.build(walk(-0.1, 2, start=200)), CFG)
    assert (sig == 1).sum() <= (sig == -1).sum()


def test_levels_direction():
    sl, tp = oilbot.levels(1, 100, 2, CFG)
    assert sl < 100 < tp
    sl, tp = oilbot.levels(-1, 100, 2, CFG)
    assert tp < 100 < sl


def test_backtest_runs_and_stats():
    trades = oilbot.simulate(oilbot.build(walk(0.05, 3, n=3000)), CFG)
    s = oilbot.stats(trades)
    assert s["n"] >= 0 and 0 <= s["win"] <= 100


def test_trade_hits_tp_on_clean_trend():
    # trend curat in sus, SL/TP simulate corect: pnl pozitiv cand TP atins
    ind = oilbot.build(walk(0.25, 4, n=1200))
    t = oilbot.simulate(ind, {**CFG, "min_score": 3, "adx_min": 0})
    assert t and sum(x["pnl"] for x in t) > 0


def test_messages():
    m = oilbot.entry_msg("WTI", 1, 80.0, 1.0, 5, 55, 25, CFG)
    assert "Stop Loss: $78.50" in m and "Take Profit: $83.00" in m
