#!/usr/bin/env python3
"""Bot de semnale BUY/SELL pentru petrol (WTI / Brent) - pentru tranzactionare manuala pe eToro.

Nu plaseaza ordine. Trimite doar notificari (Telegram + consola) cand indicatorii
tehnici dau un semnal nou. Date: Yahoo Finance (futures CL=F, BZ=F).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"


# ---------------------------------------------------------------- date
def fetch_ohlc(symbol: str, interval: str = "1h", rng: str = "60d") -> pd.DataFrame:
    r = requests.get(
        YAHOO.format(sym=symbol),
        params={"interval": interval, "range": rng},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame(
        {k: q[k] for k in ("open", "high", "low", "close")},
        index=pd.to_datetime(res["timestamp"], unit="s", utc=True),
    ).dropna()
    return df


# ---------------------------------------------------------- indicatori
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def analyze(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    """Calculeaza scorul (-5..+5) pe ultima bara inchisa. >=min_score => BUY, <=-min_score => SELL."""
    cfg = cfg or {}
    min_score = cfg.get("min_score", 3)
    c = df["close"]
    e20, e50 = ema(c, 20), ema(c, 50)
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    hist = macd - sig
    r = rsi(c)
    a = atr(df)
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    lo_bb, up_bb = mid - 2 * sd, mid + 2 * sd

    i = -1
    price = float(c.iloc[i])
    reasons: list[str] = []
    score = 0

    def add(points: int, why: str):
        nonlocal score
        score += points
        reasons.append(f"{'+' if points > 0 else ''}{points} {why}")

    # trend
    if e20.iloc[i] > e50.iloc[i]:
        add(1, "trend ascendent (EMA20 > EMA50)")
    else:
        add(-1, "trend descendent (EMA20 < EMA50)")
    # incrucisare EMA recenta (ultimele 3 bare)
    cross = np.sign(e20 - e50).diff().iloc[-3:]
    if (cross > 0).any():
        add(1, "EMA20 a taiat EMA50 in sus")
    elif (cross < 0).any():
        add(-1, "EMA20 a taiat EMA50 in jos")
    # momentum MACD
    if hist.iloc[i] > 0 and hist.iloc[i] > hist.iloc[i - 1]:
        add(1, "MACD bullish, in crestere")
    elif hist.iloc[i] < 0 and hist.iloc[i] < hist.iloc[i - 1]:
        add(-1, "MACD bearish, in scadere")
    # RSI (revenire din extrem sau zona de forta)
    rv = float(r.iloc[i])
    if rv < 35 and r.iloc[i] > r.iloc[i - 1]:
        add(2, f"RSI {rv:.0f} supravandut, revine")
    elif rv > 65 and r.iloc[i] < r.iloc[i - 1]:
        add(-2, f"RSI {rv:.0f} supracumparat, se intoarce")
    elif 50 < rv <= 65:
        add(1, f"RSI {rv:.0f} (forta cumparatorilor)")
    elif 35 <= rv < 50:
        add(-1, f"RSI {rv:.0f} (forta vanzatorilor)")
    # Bollinger
    if price <= lo_bb.iloc[i]:
        add(1, "pret la banda Bollinger inferioara")
    elif price >= up_bb.iloc[i]:
        add(-1, "pret la banda Bollinger superioara")

    action = "BUY" if score >= min_score else "SELL" if score <= -min_score else "HOLD"
    atr_v = float(a.iloc[i])
    sl_m, tp_m = cfg.get("atr_sl_mult", 1.5), cfg.get("atr_tp_mult", 3.0)
    d = 1 if action == "BUY" else -1
    return {
        "action": action,
        "score": score,
        "price": price,
        "rsi": rv,
        "atr": atr_v,
        "stop_loss": price - d * sl_m * atr_v if action != "HOLD" else None,
        "take_profit": price + d * tp_m * atr_v if action != "HOLD" else None,
        "reasons": reasons,
        "bar_time": df.index[i].isoformat(),
    }


# ------------------------------------------------------------ notificari
def format_msg(name: str, s: dict) -> str:
    icon = {"BUY": "🟢 CUMPĂRĂ (BUY)", "SELL": "🔴 VINDE (SELL)", "HOLD": "⚪ AȘTEAPTĂ"}[s["action"]]
    lines = [f"{icon} — {name}", f"Preț: {s['price']:.2f} | Scor: {s['score']:+d} | RSI {s['rsi']:.0f}"]
    if s["stop_loss"] is not None:
        lines.append(f"Stop Loss: {s['stop_loss']:.2f} | Take Profit: {s['take_profit']:.2f}")
    lines += ["• " + x for x in s["reasons"]]
    lines.append("Deschide eToro → Commodities → OIL și setează manual ordinul. Nu e sfat financiar.")
    return "\n".join(lines)


def notify(text: str) -> None:
    print(text, "\n" + "-" * 50)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text},
            timeout=15,
        ).raise_for_status()
    except requests.RequestException as e:
        print(f"[!] Telegram a esuat: {e}")


# ---------------------------------------------------------------- bucla
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def run_once(cfg: dict, state: dict) -> None:
    for name, sym in cfg["symbols"].items():
        try:
            df = fetch_ohlc(sym, cfg.get("interval", "1h"), cfg.get("range", "60d"))
            if len(df) < 60:
                raise ValueError("prea putine date")
            res = analyze(df, cfg)
        except Exception as e:  # noqa: BLE001 - nu oprim botul pentru o eroare de retea
            print(f"[!] {name}: {e}")
            continue
        prev = state.get(sym, "HOLD")
        print(f"{name}: {res['action']} (scor {res['score']:+d}, pret {res['price']:.2f})")
        # notificam doar la schimbarea semnalului (evitam spam)
        if res["action"] != prev and (res["action"] != "HOLD" or prev != "HOLD"):
            notify(format_msg(name, res) if res["action"] != "HOLD"
                   else f"⚪ {name}: semnalul {prev} s-a încheiat. Preț {res['price']:.2f}")
        state[sym] = res["action"]
    STATE_FILE.write_text(json.dumps(state))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="o singura verificare (pentru cron)")
    ap.add_argument("--test", action="store_true", help="trimite o notificare de test")
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
    cfg = json.loads(Path(a.config).read_text())
    state = load_state()
    while True:
        run_once(cfg, state)
        if a.once:
            break
        time.sleep(cfg.get("check_every_minutes", 15) * 60)


if __name__ == "__main__":
    main()
