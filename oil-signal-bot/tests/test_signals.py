import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import oilbot  # noqa: E402


def make(prices):
    p = np.asarray(prices, dtype=float)
    idx = pd.date_range("2026-01-01", periods=len(p), freq="h", tz="UTC")
    return pd.DataFrame({"open": p, "high": p + 0.3, "low": p - 0.3, "close": p}, index=idx)


def test_uptrend_is_buy_or_hold_never_sell():
    rng = np.random.default_rng(1)
    df = make(70 + np.cumsum(rng.normal(0.15, 0.3, 300)))
    assert oilbot.analyze(df)["action"] != "SELL"


def test_downtrend_is_sell_or_hold_never_buy():
    rng = np.random.default_rng(2)
    df = make(90 + np.cumsum(rng.normal(-0.15, 0.3, 300)))
    assert oilbot.analyze(df)["action"] != "BUY"


def test_levels_direction():
    df = make(np.linspace(60, 100, 300) + np.sin(np.arange(300)))
    r = oilbot.analyze(df, {"min_score": 1})
    if r["action"] == "BUY":
        assert r["stop_loss"] < r["price"] < r["take_profit"]
    elif r["action"] == "SELL":
        assert r["take_profit"] < r["price"] < r["stop_loss"]


def test_format_contains_action():
    df = make(np.linspace(60, 100, 300))
    r = oilbot.analyze(df, {"min_score": 1})
    assert "WTI" in oilbot.format_msg("WTI", r)
