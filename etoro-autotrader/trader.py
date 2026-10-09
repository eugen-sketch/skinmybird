#!/usr/bin/env python3
"""Autotrader pe eToro DEMO (sau 'hartie' daca lipsesc cheile): semnal -> ordin cu SL/TP -> gestionare -> notificare.

Rulat periodic (GitHub Actions, la ~10 min). Starea (pozitii urmarite, echitate virtuala) in state.json.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import notify
import ta
from etoro import EToroDemo, EToroError

HERE = Path(__file__).parent
STATE_FILE = Path(os.getenv("STATE_FILE", HERE / "state.json"))


# ------------------------------------------------------------------ semnal
def london_breakout(df: pd.DataFrame) -> int:
    """+1/-1 daca ULTIMA bara completa este PRIMA bara (07-10 UTC) care inchide peste/sub intervalul asiatic (00-07 UTC) al zilei."""
    day = df.index[-1].normalize()
    today = df[df.index >= day]
    asia = today.between_time("00:00", "06:59")
    if len(asia) < 5:
        return 0
    hi, lo = asia["high"].max(), asia["low"].min()
    for ts, row in today.between_time("07:00", "10:59").iterrows():
        side = 1 if row["close"] > hi else -1 if row["close"] < lo else 0
        if side:
            return side if ts == df.index[-1] else 0
    return 0


def compute_signal(df: pd.DataFrame, p: dict) -> dict:
    """Semnal pe ultima bara COMPLETA: +1 BUY / -1 SELL / 0, plus ATR si RSI."""
    if df.index[-1] + timedelta(hours=1) > pd.Timestamp.now(tz="UTC"):
        df = df.iloc[:-1]
    r = ta.rsi(df["close"], p["rsi_period"])
    a = ta.atr(df)
    if p.get("strategy") == "london_breakout":
        side = london_breakout(df)
    else:
        ext = p["rsi_extreme"]
        side = 1 if r.iloc[-1] < ext else -1 if r.iloc[-1] > 100 - ext else 0
    return {"side": side, "rsi": float(r.iloc[-1]), "atr": float(a.iloc[-1]), "price": float(df["close"].iloc[-1]),
            "bar": df.index[-1].isoformat()}


def size_position(equity: float, price: float, atr_v: float, p: dict, lev_cap: int) -> dict | None:
    """Marja si levier. eToro cere expunere (marja x levier) >= min_notional (1000$). Folosim levierul maxim permis
    (marja mai mica => mai multe pozitii in paralel); plafon de marja per pozitie = max_margin_pct din cont."""
    sl_frac = p["sl_atr"] * atr_v / price
    if sl_frac <= 0:
        return None
    lev = min(lev_cap, p["max_leverage"])
    floor = p["min_notional"] * 1.01
    notional = max(equity * p["risk_pct"] / 100 / sl_frac, floor)
    notional = min(notional, equity * p["max_margin_pct"] / 100 * lev)
    if notional < floor:
        return None
    margin = math.ceil(notional / lev * 100) / 100
    notional = margin * lev
    return {"amount": margin, "leverage": lev, "notional": notional, "risk_usd": notional * sl_frac}


# ------------------------------------------------------------------ brokeri
class PaperBroker:
    """Simulare locala (fara eToro)."""
    paper = True

    def __init__(self, state: dict):
        self.store = state.setdefault("paper", {})

    def price(self, inst) -> float:
        return float(ta.fetch_ohlc(inst["yahoo"], "1h", "5d")["close"].iloc[-1])

    def positions(self) -> list[dict]:
        return [dict(v, id=k) for k, v in self.store.items()]

    def open(self, inst, side, amount, lev, sl, tp, price) -> str:
        pid = f"P{int(time.time())}{inst['name']}"
        self.store[pid] = {"instrument": inst["name"], "side": side, "entry": price, "amount": amount, "leverage": lev}
        return pid

    def close(self, pid, inst) -> None:
        self.store.pop(pid, None)

    remove = close


class EToroBroker:
    paper = False

    def __init__(self, api: EToroDemo, ids: dict):
        self.api, self.ids = api, ids

    def price(self, inst) -> float:
        return self.api.last_price(self.ids[inst["name"]])

    def positions(self) -> list[dict]:
        out = []
        rev = {v: k for k, v in self.ids.items()}
        for p in self.api.positions():
            iid = int(p.get("instrumentID") or p.get("InstrumentID") or p.get("instrumentId") or 0)
            pid = p.get("positionID") or p.get("PositionID") or p.get("positionId")
            if not pid or iid not in rev:
                continue
            buy = p.get("isBuy", p.get("IsBuy"))
            out.append({"id": str(pid), "instrument": rev[iid], "side": 1 if buy else -1,
                        "entry": float(p.get("openRate") or p.get("OpenRate") or 0),
                        "amount": float(p.get("amount") or p.get("Amount") or 0),
                        "leverage": int(p.get("leverage") or p.get("Leverage") or 1)})
        return out

    def open(self, inst, side, amount, lev, sl, tp, price) -> str:
        try:
            pid = self._open(inst, side, amount, lev, sl, tp)
            self.last = {"amount": amount, "leverage": lev}
            return pid
        except EToroError as e:
            if lev <= 20:
                raise
            lev2, amount2 = 20, math.ceil(amount * lev / 20 * 100) / 100   # aceeasi expunere, levier 20
            notify.send(f"ℹ️ {inst['name']}: levier {lev} refuzat ({str(e)[:120]}), reîncerc cu 20.")
            pid = self._open(inst, side, amount2, lev2, sl, tp)
            self.last = {"amount": amount2, "leverage": lev2}
            return pid

    def _open(self, inst, side, amount, lev, sl, tp) -> str:
        before = {p["id"] for p in self.positions()}
        r = self.api.open_market(self.ids[inst["name"]], side == 1, amount, lev, sl, tp)
        oid = r.get("orderId") if isinstance(r, dict) else None
        for _ in range(8):
            time.sleep(3)
            if oid:
                st = self.api.order_status(oid)
                if st.get("statusID") == 4:
                    raise EToroError(f"Ordin respins: {st.get('errorMessage')}")
            new = [p for p in self.positions() if p["id"] not in before and p["instrument"] == inst["name"]]
            if new:
                return new[0]["id"]
        raise EToroError("Ordinul trimis, dar pozitia nu apare in portofoliu dupa 24s (verifica manual pe eToro).")

    def close(self, pid, inst) -> None:
        self.api.close_position(int(pid), self.ids[inst["name"]])


# ------------------------------------------------------------------ util
def usd(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def touched(df: pd.DataFrame, tr: dict) -> tuple[str, float] | None:
    """Prima atingere SL/TP dupa deschidere, pe barele 1h."""
    after = df[df.index > pd.Timestamp(tr["time"]).floor("h")]
    for _, row in after.iterrows():
        if tr["side"] == 1:
            if row["low"] <= tr["sl"]:
                return "SL", tr["sl"]
            if row["high"] >= tr["tp"]:
                return "TP", tr["tp"]
        else:
            if row["high"] >= tr["sl"]:
                return "SL", tr["sl"]
            if row["low"] <= tr["tp"]:
                return "TP", tr["tp"]
    return None


def pnl_usd(tr: dict, exit_px: float, cost_pct: float) -> float:
    return tr["side"] * (exit_px / tr["entry"] - 1) * tr["notional"] - cost_pct / 100 * tr["notional"]


def can_open_now(now: datetime, p: dict) -> bool:
    if now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 20) or (now.weekday() == 6):
        return False
    return now.hour not in p.get("blackout_hours_utc", [21, 22])


# ------------------------------------------------------------------ ciclu
def run_once(cfg: dict, state: dict, broker, dfs: dict | None = None, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    p = cfg["params"]
    eq = state.setdefault("equity", cfg["virtual_equity"])
    opened = state.setdefault("open", {})
    day = now.strftime("%Y-%m-%d")
    if state.get("day") != day:
        state["day"], state["day_pnl"] = day, 0.0

    for inst in cfg["instruments"]:
        name = inst["name"]
        try:
            df = (dfs or {}).get(name)
            if df is None:
                df = ta.fetch_ohlc(inst["yahoo"], "1h", "30d")
            if len(df) < 40:
                raise ValueError("prea putine date")
        except Exception as e:  # noqa: BLE001
            print(f"[!] {name}: date indisponibile: {e}")
            continue

        # 1) gestionare pozitie existenta
        tr = opened.get(name)
        if tr:
            hit = touched(df, tr)
            if broker.paper and hit:
                broker.remove(tr["id"], inst)
            live = {x["id"] for x in broker.positions()}
            age_h = (now - pd.Timestamp(tr["time"]).to_pydatetime()).total_seconds() / 3600
            if tr["id"] in live and age_h >= p["max_hours"]:
                try:
                    broker.close(tr["id"], inst)
                    notify.send(f"⏱ {name}: au trecut {p['max_hours']}h fără Stop Loss sau Take Profit, închid poziția la piață.")
                    time.sleep(2)
                except EToroError as e:
                    notify.send(f"⚠️ Nu am putut închide {name}: {e}")
                live = {x["id"] for x in broker.positions()}
            if tr["id"] not in live:
                kind, px = hit if hit else ("MANUAL/TIMP", float(df["close"].iloc[-1]))
                res = pnl_usd(tr, px, inst["cost"])
                eq += res
                state["day_pnl"] += res
                state.setdefault("history", []).append({"name": name, "kind": kind, "pnl": round(res, 2), "time": now.isoformat()})
                why = {"TP": "Take Profit atins", "SL": "Stop Loss lovit", "MANUAL/TIMP": "închis la piață / după timp"}.get(kind, kind)
                notify.send(f"{'✅' if res > 0 else '❌'} Am închis {name} — {why}: {'+' if res > 0 else ''}{usd(res)}\n"
                            f"• Echitate virtuală {usd(eq)} (start {usd(cfg['virtual_equity'])})")
                opened.pop(name)
            continue

        # 2) semnal nou
        sig = compute_signal(df, p)
        print(f"{name}: semnal={sig['side']:+d} rsi={sig['rsi']:.1f} pret={sig['price']:.4f}")
        if sig["side"] == 0 or state.get("last_bar", {}).get(name) == sig["bar"]:
            continue
        used = sum(o.get("amount", 0) for o in opened.values())
        if not can_open_now(now, p):
            print(f"{name}: semnal {sig['side']:+d}, dar acum nu deschid (weekend / ore fără lichiditate)")
            continue
        if len(opened) >= p["max_open"]:
            continue
        if state["day_pnl"] <= -eq * p["daily_loss_stop_pct"] / 100 or eq < cfg["virtual_equity"] * p["kill_equity_frac"]:
            notify.send(f"🛑 Oprit pentru azi (limită de pierdere). Echitate virtuală {usd(eq)}.")
            continue
        try:
            px = broker.price(inst)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {name}: nu pot lua pretul eToro: {e}")
            continue
        sz = size_position(eq, px, sig["atr"], p, inst["lev_cap"])
        if not sz:
            continue
        if used + sz["amount"] > eq * p["max_total_margin_pct"] / 100:
            notify.send(f"⏭ {name}: semnal {'BUY' if sig['side'] == 1 else 'SELL'}, dar nu mai am marjă liberă "
                        f"({usd(used)} din {usd(eq * p['max_total_margin_pct'] / 100)} folosit), sar peste.")
            state.setdefault("last_bar", {})[name] = sig["bar"]
            continue
        side = sig["side"]
        sl = px - side * p["sl_atr"] * sig["atr"]
        tp = px + side * p["tp_atr"] * sig["atr"]
        digits = 5 if px < 20 else 3 if px < 1000 else 2
        notify.send(f"📤 {name}: semnal {'BUY' if side == 1 else 'SELL'}, trimit ordinul pe eToro DEMO "
                    f"({usd(sz['amount'])} × levier {sz['leverage']}) cu SL {sl:.{digits}f} și TP {tp:.{digits}f}…")
        try:
            pid = broker.open(inst, side, sz["amount"], sz["leverage"], round(sl, digits), round(tp, digits), px)
        except EToroError as e:
            notify.send(f"⚠️ DEMO: ordinul pentru {name} a eșuat: {e}")
            state.setdefault("last_bar", {})[name] = sig["bar"]
            continue
        state.setdefault("last_bar", {})[name] = sig["bar"]
        fill = getattr(broker, "last", None)
        if fill:
            sz["amount"], sz["leverage"] = fill["amount"], fill["leverage"]
            sz["notional"] = fill["amount"] * fill["leverage"]
        opened[name] = {"id": pid, "side": side, "entry": px, "sl": sl, "tp": tp, "time": now.isoformat(),
                        "notional": sz["notional"], "amount": sz["amount"]}
        gain = abs(tp - px) / px * sz["notional"]
        verb = "Am cumpărat (LONG)" if side == 1 else "Am făcut short (vânzare)"
        notify.send(
            f"{'🟢 BUY' if side == 1 else '🔴 SELL'} — {verb} {name} la {px:.{digits}f}\n"
            f"• Investit {usd(sz['amount'])} × levier {sz['leverage']} = expunere {usd(sz['notional'])}\n"
            f"• Am pus Stop Loss la {sl:.{digits}f} (dacă pierde, ≈ -{usd(sz['risk_usd'])})\n"
            f"• Am pus Take Profit la {tp:.{digits}f} (dacă câștigă, ≈ +{usd(gain)})\n"
            f"• Ies oricum după {p['max_hours']}h dacă nu se atinge nimic\n"
            f"• Echitate virtuală {usd(eq)}{' | MOD HÂRTIE' if broker.paper else ''}")
    state["equity"] = eq
    if now.hour >= 20 and state.get("summary_day") != day and state.get("history") is not None:
        h = state["history"]
        wins = [x["pnl"] for x in h if x["pnl"] > 0]
        loss = -sum(x["pnl"] for x in h if x["pnl"] < 0)
        pf = (sum(wins) / loss) if loss else float("inf")
        notify.send(f"📊 Rezumat DEMO: {len(h)} tranzacții, {len(wins)} câștigătoare, profit factor "
                    f"{pf:.2f}, echitate virtuală {usd(eq)} (start {usd(cfg['virtual_equity'])}).")
        state["summary_day"] = day


def build_broker(cfg: dict, state: dict):
    if os.getenv("ETORO_API_KEY") and os.getenv("ETORO_USER_KEY") and os.getenv("PAPER") != "1":
        api = EToroDemo()
        ids = state.setdefault("ids", {})
        missing = state.setdefault("missing", [])
        for inst in list(cfg["instruments"]):
            if inst["name"] in missing:
                cfg["instruments"].remove(inst)
            elif inst["name"] not in ids:
                try:
                    ids[inst["name"]] = api.find_instrument_id(inst["etoro"])
                except EToroError as e:
                    notify.send(f"⚠️ Nu găsesc {inst['name']} ({inst['etoro']}) pe eToro, îl sar: {str(e)[:200]}")
                    missing.append(inst["name"])
                    cfg["instruments"].remove(inst)
        return EToroBroker(api, ids)
    return PaperBroker(state)


def main() -> int:
    cfg = json.loads(Path(os.getenv("CONFIG", HERE / "config.json")).read_text())
    try:
        state = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        state = {}
    try:
        broker = build_broker(cfg, state)
        run_once(cfg, state, broker)
        state.pop("last_err", None)
    except Exception as e:  # noqa: BLE001 - nu lasam jobul sa "pice" (GitHub trimite mail la fiecare esec)
        msg = f"{type(e).__name__}: {e}"[:300]
        last = state.get("last_err") or {}
        if last.get("msg") != msg or time.time() - last.get("ts", 0) > 6 * 3600:   # aceeasi eroare: cel mult o data la 6h
            notify.send(f"⚠️ Autotrader: {msg}")
            state["last_err"] = {"msg": msg, "ts": time.time()}
        print(f"[!] {msg}")
    finally:
        STATE_FILE.write_text(json.dumps(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
