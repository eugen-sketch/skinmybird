#!/usr/bin/env python3
"""Bot de semnale BUY/SELL pentru petrol (WTI / Brent) - pentru tranzactionare manuala pe eToro.

Nu plaseaza ordine. Trimite notificari Telegram cu intrare, Stop Loss si Take Profit in $,
apoi te anunta cand SL sau TP a fost atins. Include si backtest (--backtest) pe 2 ani de date.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"

DEFAULTS = {
    "interval": "1h",
    "range": "60d",
    "strategy": "rsi_reversion",  # sau "score" (strategia veche, pe scor)
    "rsi_extreme": 20,      # BUY sub 20, SELL peste 80
    "sl_pct": 2.0,          # Stop Loss in % din pret (None = foloseste ATR)
    "tp_pct": 1.5,          # Take Profit in % din pret
    "min_score": 4,
    "adx_min": 18,
    "trend_filter": True,   # BUY doar peste EMA200, SELL doar sub EMA200
    "atr_sl_mult": 1.5,
    "atr_tp_mult": 3.0,
    "max_bars": 48,         # iesire fortata dupa N ore daca nu atinge nici SL nici TP
    "position_usd": 400,    # pentru estimarea castigului/pierderii in $
}


# ---------------------------------------------------------------- date
def fetch_ohlc(symbol: str, interval: str = "1h", rng: str = "60d") -> pd.DataFrame:
    r = requests.get(
        YAHOO.format(sym=symbol),
        params={"interval": interval, "range": rng},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    return pd.DataFrame(
        {k: q[k] for k in ("open", "high", "low", "close")},
        index=pd.to_datetime(res["timestamp"], unit="s", utc=True),
    ).dropna()


# ---------------------------------------------------------- indicatori
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).fillna(50)  # dn=0 -> RSI 100; 0/0 -> neutru


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift()
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up, dn = df["high"].diff(), -df["low"].diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Adauga indicatorii si scorul brut (-6..+6) pentru fiecare bara."""
    c = df["close"]
    out = df.copy()
    e20, e50 = ema(c, 20), ema(c, 50)
    out["ema200"] = ema(c, 200)
    macd = ema(c, 12) - ema(c, 26)
    hist = macd - ema(macd, 9)
    out["rsi"] = rsi(c)
    out["atr"] = atr(df)
    out["adx"] = adx(df)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()

    trend = np.sign(e20 - e50)
    cross = trend.diff().fillna(0)
    recent_up = (cross > 0).rolling(3, min_periods=1).max() > 0
    recent_dn = (cross < 0).rolling(3, min_periods=1).max() > 0
    rs, rp = out["rsi"], out["rsi"].shift()

    s = trend.copy()                                   # +-1 trend EMA20/50
    s += recent_up.astype(int) - recent_dn.astype(int)  # incrucisare recenta
    s += np.where((hist > 0) & (hist > hist.shift()), 1, np.where((hist < 0) & (hist < hist.shift()), -1, 0))
    s += np.where((rs < 35) & (rs > rp), 2, np.where((rs > 65) & (rs < rp), -2,
          np.where((rs > 50) & (rs <= 65), 1, np.where((rs >= 35) & (rs < 50), -1, 0))))
    s += np.where(c <= mid - 2 * sd, 1, np.where(c >= mid + 2 * sd, -1, 0))
    out["score"] = s
    return out


def signals(ind: pd.DataFrame, cfg: dict) -> pd.Series:
    """+1 BUY, -1 SELL, 0 nimic."""
    if cfg.get("strategy") == "rsi_reversion":
        ext = cfg["rsi_extreme"]
        return pd.Series(np.where(ind["rsi"] < ext, 1, np.where(ind["rsi"] > 100 - ext, -1, 0)), index=ind.index)
    buy = ind["score"] >= cfg.get("min_score")
    sell = ind["score"] <= -cfg.get("min_score")
    ok = ind["adx"] >= cfg["adx_min"]
    if cfg["trend_filter"]:
        buy &= ind["close"] > ind["ema200"]
        sell &= ind["close"] < ind["ema200"]
    return pd.Series(np.where(buy & ok, 1, np.where(sell & ok, -1, 0)), index=ind.index)


def levels(side: int, price: float, atr_v: float, cfg: dict) -> tuple[float, float]:
    if cfg.get("strategy") == "rsi_reversion":
        return price * (1 - side * cfg["sl_pct"] / 100), price * (1 + side * cfg["tp_pct"] / 100)
    return price - side * cfg["atr_sl_mult"] * atr_v, price + side * cfg["atr_tp_mult"] * atr_v


# ------------------------------------------------------------ backtest
def simulate(ind: pd.DataFrame, cfg: dict) -> list[dict]:
    sig = signals(ind, cfg).to_numpy()
    hi, lo, cl, at = (ind[k].to_numpy() for k in ("high", "low", "close", "atr"))
    trades, i, n = [], 210, len(ind)  # primele bare = incalzire indicatori
    while i < n - 1:
        side = int(sig[i])
        if side == 0:
            i += 1
            continue
        entry = cl[i]
        sl, tp = levels(side, entry, at[i], cfg)
        exit_px, j = cl[min(i + cfg["max_bars"], n - 1)], min(i + cfg["max_bars"], n - 1)
        for k in range(i + 1, min(i + cfg["max_bars"], n - 1) + 1):
            hit_sl = lo[k] <= sl if side == 1 else hi[k] >= sl
            hit_tp = hi[k] >= tp if side == 1 else lo[k] <= tp
            if hit_sl:  # presupunem SL primul daca ambele in aceeasi bara (conservator)
                exit_px, j = sl, k
                break
            if hit_tp:
                exit_px, j = tp, k
                break
        trades.append({"side": side, "pnl": side * (exit_px - entry), "pct": side * (exit_px / entry - 1) * 100 - 0.06,  # minus cost estimat (spread)
                       "time": ind.index[i]})
        i = j + 1
    return trades


def stats(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "win": 0, "pf": 0, "avg_pct": 0, "total_pct": 0, "max_dd_pct": 0}
    p = np.array([t["pct"] for t in trades])
    gain, loss = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    return {"n": len(p), "win": (p > 0).mean() * 100, "pf": gain / loss if loss else float("inf"),
            "avg_pct": p.mean(), "total_pct": p.sum(), "max_dd_pct": (np.maximum.accumulate(eq) - eq).max()}


def fmt_stats(name: str, s: dict, cfg: dict | None = None) -> str:
    tag = f" [RSI<{cfg['rsi_extreme']} SL{cfg['sl_pct']}% TP{cfg['tp_pct']}%]" if cfg and "rsi_extreme" in cfg else ""
    return (f"{name}{tag}: {s['n']} tranzactii | câștigătoare {s['win']:.0f}% | profit factor {s['pf']:.2f} | "
            f"medie {s['avg_pct']:+.2f}%/tranz. | total {s['total_pct']:+.1f}% | cădere max {s['max_dd_pct']:.1f}%")


def run_backtest(cfg: dict) -> None:
    lines = ["📊 BACKTEST (ultimii 2 ani, bare de 1 oră)"]
    for name, sym in cfg["symbols"].items():
        df = fetch_ohlc(sym, "1h", "730d")
        ind = build(df)
        lines.append(f"\n{name}: {len(df)} bare")
        lines.append("Setări curente → " + fmt_stats("", stats(simulate(ind, cfg)))[2:])
        grid = []
        for ext, sl, tp in itertools.product([15, 20, 25], [1.2, 2.0, 3.0], [1.0, 1.5, 2.2]):
            c = {**cfg, "rsi_extreme": ext, "sl_pct": sl, "tp_pct": tp}
            s_ = stats(simulate(ind, c))
            if s_["n"] >= 30:
                grid.append((s_["pf"], s_, c))
        grid.sort(key=lambda x: -x[0])
        lines.append("Cele mai bune 3 combinații (atenție: pot fi potrivite pe trecut):")
        lines += ["  " + fmt_stats("", s, c)[2:] for _, s, c in grid[:3]]
    notify("\n".join(lines))


# ------------------------------------------------------------ notificari
def usd(x: float) -> str:
    return f"${x:,.2f}"


def entry_msg(name: str, side: int, price: float, atr_v: float, score: int, rsi_v: float, adx_v: float, cfg: dict) -> str:
    sl, tp = levels(side, price, atr_v, cfg)
    pos = cfg["position_usd"]
    risk, gain = abs(price - sl), abs(tp - price)
    head = "🟢 CUMPĂRĂ (BUY)" if side == 1 else "🔴 VINDE (SELL)"
    return (
        f"{head} — {name}\n"
        f"Intrare: {usd(price)}\n"
        f"Stop Loss: {usd(sl)}  (−{usd(risk)} / baril, −{risk / price * 100:.1f}%)\n"
        f"Take Profit: {usd(tp)}  (+{usd(gain)} / baril, +{gain / price * 100:.1f}%)\n"
        f"La ${pos:,.0f} investiți: risc ≈ {usd(pos * risk / price)}, câștig țintă ≈ {usd(pos * gain / price)}\n"
        f"RSI {rsi_v:.0f} ({'supravândut' if side == 1 else 'supracumpărat'}) — așteptăm revenirea prețului\n"
        f"Ieși automat dacă nu se atinge nimic în {cfg['max_bars']}h."
    )


def notify(text: str) -> None:
    print(text, "\n" + "-" * 50)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    for part in [text[i:i + 3900] for i in range(0, len(text), 3900)]:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": part}, timeout=15).raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Telegram a esuat: {e}")


# ---------------------------------------------------------------- live
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def check_open_trade(name: str, tr: dict, df: pd.DataFrame, cfg: dict) -> bool:
    """True daca tranzactia s-a inchis (si a trimis notificare)."""
    after = df[df.index > pd.Timestamp(tr["time"])]
    side, entry = tr["side"], tr["entry"]
    for ts, row in after.iterrows():
        sl_hit = row["low"] <= tr["sl"] if side == 1 else row["high"] >= tr["sl"]
        tp_hit = row["high"] >= tr["tp"] if side == 1 else row["low"] <= tr["tp"]
        if sl_hit or tp_hit:
            px = tr["sl"] if sl_hit else tr["tp"]
            d = side * (px - entry)
            notify(f"{'✅ TAKE PROFIT atins' if not sl_hit else '❌ STOP LOSS lovit'} — {name}\n"
                   f"Ieșire {usd(px)} (intrare {usd(entry)}): {'+' if d >= 0 else '−'}{usd(abs(d))} / baril "
                   f"({side * (px / entry - 1) * 100:+.1f}% ≈ {'+' if d >= 0 else '−'}{usd(abs(d) / entry * cfg['position_usd'])} la {usd(cfg['position_usd'])})")
            return True
    age_h = (datetime.now(timezone.utc) - pd.Timestamp(tr["time"]).to_pydatetime()).total_seconds() / 3600
    if age_h >= cfg["max_bars"]:
        px = float(df["close"].iloc[-1])
        d = side * (px - entry)
        notify(f"⏱ TIMP EXPIRAT — {name}: închide poziția acum la ~{usd(px)} "
               f"({'+' if d >= 0 else '−'}{usd(abs(d))} / baril față de intrare {usd(entry)}).")
        return True
    return False


def run_once(cfg: dict, state: dict) -> None:
    for name, sym in cfg["symbols"].items():
        try:
            df = fetch_ohlc(sym, cfg["interval"], cfg["range"])
            if len(df) < 250:
                raise ValueError("prea putine date")
        except Exception as e:  # noqa: BLE001 - nu oprim botul pentru o eroare de retea
            print(f"[!] {name}: {e}")
            continue
        st = state.get(sym) or {}
        if st.get("open") and check_open_trade(name, st["open"], df, cfg):
            st["open"] = None
        # semnal doar pe ultima bara COMPLETA (ultima poate fi inca in formare)
        done = df if df.index[-1] + timedelta(hours=1) <= pd.Timestamp.now(tz="UTC") else df.iloc[:-1]
        ind = build(done)
        side = int(signals(ind, cfg).iloc[-1])
        last = ind.iloc[-1]
        print(f"{name}: semnal={side:+d} scor={int(last['score']):+d} adx={last['adx']:.0f} pret={last['close']:.2f}")
        cur = (st.get("open") or {}).get("side")
        if side != 0 and side != cur and st.get("last_bar") != ind.index[-1].isoformat():
            if cur:
                notify(f"🔄 Semnal opus pe {name}: închide poziția veche și deschide cea nouă.")
            price, a = float(last["close"]), float(last["atr"])
            notify(entry_msg(name, side, price, a, int(last["score"]), float(last["rsi"]), float(last["adx"]), cfg))
            sl, tp = levels(side, price, a, cfg)
            st["open"] = {"side": side, "entry": price, "sl": sl, "tp": tp, "time": ind.index[-1].isoformat()}
            st["last_bar"] = ind.index[-1].isoformat()
        state[sym] = st
    STATE_FILE.write_text(json.dumps(state))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="o singura verificare (pentru cron)")
    ap.add_argument("--test", action="store_true", help="trimite o notificare de test")
    ap.add_argument("--backtest", action="store_true", help="testeaza strategia pe 2 ani de date")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    a = ap.parse_args()
    env = HERE / ".env"
    if env.exists():
        for ln in env.read_text().splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    if a.test:
        notify("✅ Oil Signal Bot funcționează. Vei primi aici semnale BUY/SELL.")
        return
    cfg = {**DEFAULTS, **json.loads(Path(a.config).read_text())}
    if a.backtest:
        run_backtest(cfg)
        return
    state = load_state()
    while True:
        run_once(cfg, state)
        if a.once:
            break
        time.sleep(cfg.get("check_every_minutes", 15) * 60)


if __name__ == "__main__":
    main()
