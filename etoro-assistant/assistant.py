#!/usr/bin/env python3
"""Asistent de trading eToro DEMO.

- porneste doar cand il pornesti tu (GitHub Actions -> Run workflow) si se opreste la /stop sau la sfarsitul sesiunii;
- scaneaza semnale la 15 minute si te intreaba pe Telegram (OK / NU); NU deschide nimic fara OK;
- singurul lucru automat: daca ai mai multe pozitii deschise si impreuna ating tinta comuna, le inchide;
- poti inchide oricand, din eToro sau cu /inchide.
"""
from __future__ import annotations

import json
import math
import os
import signal as sig_mod
import time
from datetime import datetime, timezone
from pathlib import Path

import messages as msg
import signals
import ta
from etoro import EToroError

HERE = Path(__file__).parent
USD_QUOTE_FACTOR_ONE = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "OIL"}   # P&L deja in USD; la USDJPY/USDCAD/USDCHF se imparte la pret


MAX_RUN_HOURS = 5.5          # GitHub opreste orice job dupa 6 ore: sesiunile lungi se inlantuie


def plan_session(hours: float) -> tuple[float, float]:
    """(ore de rulat acum, ore ramase pentru sesiunea urmatoare)."""
    this = min(hours, MAX_RUN_HOURS)
    return this, max(0.0, hours - this)


def digits_for(name: str, px: float) -> int:
    return 2 if name == "OIL" else 5 if px < 20 else 3


class Assistant:
    def __init__(self, cfg: dict, tg, broker, fetch=ta.fetch_ohlc, now_fn=None, sleep=time.sleep):
        self.cfg, self.tg, self.broker, self.fetch = cfg, tg, broker, fetch
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep
        self.inst = {i["name"]: i for i in cfg["instruments"]}
        self.pending: dict[int, dict] = {}
        self.seen_bar: dict[str, str] = {}
        self.known: dict[str, dict] = {}        # pozitii urmarite: pid -> {..., last_pnl}
        self.expecting: dict[str, str] = {}      # pid -> motiv (YOU / BASKET) cand inchid eu
        self.sid = 0
        self.scans, self.last_scan = 0, "-"
        self.realized, self.n_closed = 0.0, 0
        self.stop_reason: str | None = None
        self.last_err: tuple[str, float] = ("", 0.0)

    # ------------------------------------------------------------------ calcule
    def pnl(self, pos: dict, price: float) -> float:
        raw = pos["side"] * pos["units"] * (price - pos["open_rate"])
        usd = raw if pos["name"] in USD_QUOTE_FACTOR_ONE else raw / price
        half_spread = self.inst[pos["name"]]["cost"] / 2 / 100 * pos["amount"] * pos["leverage"]
        return usd - half_spread                    # estimare dupa costul de iesire (spread)

    def used_margin(self) -> float:
        return sum(p["amount"] for p in self.known.values())

    def free_margin(self) -> float:
        return self.cfg["budget_usd"] - self.used_margin()

    def sizing(self, inst: dict) -> tuple[float, int, float]:
        c = self.cfg
        lev = min(inst["lev_cap"], c["max_leverage"])
        margin = math.floor(c["budget_usd"] / c["max_positions"] * 100) / 100
        if margin * lev < c["min_notional"] * 1.005:
            margin = math.ceil(c["min_notional"] * 1.01 / lev * 100) / 100       # minimul eToro pentru expunere
        return margin, lev, margin * lev

    def levels(self, side: int, px: float, notional: float) -> tuple[float, float]:
        c = self.cfg
        return px - side * c["sl_usd"] / notional * px, px + side * c["tp_usd"] / notional * px

    def market_open(self, now: datetime) -> bool:
        return not (now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 20) or now.hour in (21, 22))

    # ------------------------------------------------------------------ scanare
    def scan(self, manual: bool = False) -> None:
        now = self.now_fn()
        self.scans += 1
        self.last_scan = now.strftime("%H:%M")
        if not self.market_open(now):
            if manual:
                self.tg.send("😴 Piața e închisă sau prea aproape de închidere, nu caut semnale acum.")
            return
        found, overflow, report = 0, [], []
        open_names = {p["name"] for p in self.known.values()}
        for name, inst in self.inst.items():
            if name in open_names or any(p["name"] == name for p in self.pending.values()):
                continue
            try:
                s = signals.scan(self.fetch(inst["yahoo"], "1h", "30d"), inst["signals"])
            except Exception as e:  # noqa: BLE001
                self.report_error(f"nu pot citi datele pentru {msg.pair(name)} ({type(e).__name__})")
                continue
            if os.getenv("QUIET_LOGS") != "1":                   # in repo public nu afisam semnalele/pozitiile in loguri
                print(f"{name}: semnal={s['side']:+d} rsi={s['rsi']:.0f}")
            thr = next((int(n[7:]) for n in inst["signals"] if n.startswith("rsi_rev")), 25)
            report.append({"name": name, "rsi": s["rsi"], "thr": thr, "asia": s.get("asia_pos"), "bar": msg.hour_range(s["bar"])})
            if s["side"] == 0 or self.seen_bar.get(name) == s["bar"]:
                continue
            self.seen_bar[name] = s["bar"]
            if len(self.known) + len(self.pending) >= self.cfg["max_positions"]:
                overflow.append(name)
                continue
            if self.propose(name, s):
                found += 1
        if overflow:
            self.tg.send(f"ℹ️ Mai sunt semnale pe {', '.join(msg.pair(n).split(' ')[0] for n in overflow)}, dar am deja "
                         f"{self.cfg['max_positions']} poziții/semnale în așteptare. Dacă te interesează, spune-mi /scan după ce se eliberează un loc.")
            for n in overflow:
                self.seen_bar.pop(n, None)               # le re-evaluam la urmatoarea scanare
        if manual and not found:
            for n in sorted(open_names | {p["name"] for p in self.pending.values()}):
                report.append({"name": n, "rsi": 50.0, "thr": 25, "bar": report[0]["bar"] if report else "?", "note": "ai deja poziție/semnal"})
            self.tg.send(msg.scan_report(report) if report else "🔎 Am scanat acum: nu am putut citi datele, încerc din nou.")

    def propose(self, name: str, s: dict) -> bool:
        inst = self.inst[name]
        try:
            px = self.broker.price(name)
        except Exception:  # noqa: BLE001
            px = s["price"]
        side = s["side"]
        amount, lev, notional = self.sizing(inst)
        sl_px, tp_px = self.levels(side, px, notional)
        d = digits_for(name, px)
        free = self.free_margin()
        can = amount <= free + 0.001
        reason = msg.no_free_margin(amount, free)
        text = msg.signal(name, side, s["why"], px, d, amount, lev, notional, tp_px, self.cfg["tp_usd"], sl_px, self.cfg["sl_usd"], free, can, reason)
        if not can:
            self.tg.send(text)
            return False
        self.sid += 1
        sid = self.sid
        mid = self.tg.send(text, [[("✅ OK, deschide", f"open:{sid}"), ("❌ NU", f"skip:{sid}")]])
        self.pending[sid] = {"name": name, "side": side, "created": self.now_fn(), "msg_id": mid, "amount": amount}
        ok = [k for k, v in self.pending.items()]
        if len(ok) >= 2:
            ids = ",".join(str(k) for k in ok)
            self.tg.send(f"📦 Ai {len(ok)} semnale în așteptare. Le deschid pe toate dintr-o dată?",
                         [[(f"✅ OK la toate ({len(ok)})", f"openall:{ids}"), ("❌ NU la toate", f"skipall:{ids}")]])
        return True

    # ------------------------------------------------------------------ executie (doar la OK)
    def open_pending(self, sid: int) -> None:
        p = self.pending.pop(sid, None)
        if not p:
            self.tg.send(msg.expired())
            return
        self.tg.clear_buttons(p["msg_id"])
        age = (self.now_fn() - p["created"]).total_seconds() / 60
        if age > self.cfg["signal_valid_min"]:
            self.tg.send(msg.expired())
            return
        name, side, inst = p["name"], p["side"], self.inst[p["name"]]
        amount, lev, notional = self.sizing(inst)
        if amount > self.free_margin() + 0.001:
            self.tg.send(f"🚫 Nu mai am buget liber pentru {msg.pair(name)}: {msg.no_free_margin(amount, self.free_margin())}.")
            return
        try:
            px = self.broker.price(name)
            sl, tp = self.levels(side, px, notional)
            d = digits_for(name, px)
            pid = self.broker.open(name, side, amount, lev, round(sl, d), round(tp, d))
        except (EToroError, Exception) as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Ordinul pe {msg.pair(name)} n-a mers: {str(e)[:200]}\nNu am deschis nimic.")
            return
        fill = getattr(self.broker, "last", None) or {}
        amount, lev = fill.get("amount", amount), fill.get("leverage", lev)
        notional = amount * lev
        sl, tp = self.levels(side, px, notional)
        self.known[pid] = {"id": pid, "name": name, "side": side, "open_rate": px, "units": notional / px if name in USD_QUOTE_FACTOR_ONE else notional,
                           "amount": amount, "leverage": lev, "sl": sl, "tp": tp, "last_pnl": 0.0}
        self.tg.send(msg.opened(name, side, px, d, amount, lev, notional, tp, self.cfg["tp_usd"], sl, self.cfg["sl_usd"]))

    def close_one(self, pid: str, kind: str) -> None:
        pos = self.known.get(pid)
        if not pos:
            return
        self.expecting[pid] = kind
        try:
            self.broker.close(pid, pos["name"])
        except Exception as e:  # noqa: BLE001
            self.expecting.pop(pid, None)
            self.tg.send(f"⚠️ N-am reușit să închid {msg.pair(pos['name'])}: {str(e)[:150]}\nÎncearcă din eToro dacă e urgent.")
            return
        self.sleep(3)
        self.monitor(check_basket=False)                # confirma inchiderea si anunta

    # ------------------------------------------------------------------ urmarire pozitii
    def monitor(self, check_basket: bool = True) -> None:
        try:
            current = {p["id"]: p for p in self.broker.positions() if p["name"] in self.inst}
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")
            return
        rows = []
        for pid, pos in current.items():
            try:
                pos["last_pnl"] = self.pnl(pos, self.broker.price(pos["name"]))
            except Exception:  # noqa: BLE001
                pos["last_pnl"] = self.known.get(pid, {}).get("last_pnl", 0.0)
            rows.append(pos)
        # pozitii care au disparut: inchise (TP / SL / de tine / de mine)
        for pid in [k for k in self.known if k not in current]:
            old = self.known.pop(pid)
            kind = self.expecting.pop(pid, None)
            pnl = old.get("last_pnl", 0.0)
            if kind is None:
                kind = "TP" if pnl >= 0.6 * self.cfg["tp_usd"] else "SL" if pnl <= -0.6 * self.cfg["sl_usd"] else "OTHER"
            self.realized += pnl
            self.n_closed += 1
            self.tg.send(msg.closed(old["name"], kind, pnl, self.realized))
        for pid, pos in current.items():
            self.known[pid] = pos
        total = sum(r["last_pnl"] for r in rows)
        c = self.cfg
        if check_basket and len(rows) >= c["basket_min_positions"] and total >= c["basket_target_usd"]:
            self.tg.send(msg.basket(len(rows), total))
            for pid in list(self.known):
                self.close_one(pid, "BASKET")

    def status(self) -> None:
        self.monitor()
        rows = [{"name": p["name"], "side": p["side"], "pnl": p["last_pnl"]} for p in self.known.values()]
        total = sum(r["pnl"] for r in rows)
        buttons = [[(f"🔒 Închide {msg.pair(r['name']).split(' ')[0]}", f"close:{p['id']}")] for r, p in zip(rows, self.known.values())]
        if len(rows) >= 2:
            buttons.append([("🔒🔒 Închide tot", "closeall")])
        self.tg.send(msg.status(rows, total, self.free_margin(), self.cfg["budget_usd"], self.realized, self.n_closed), buttons or None)

    # ------------------------------------------------------------------ comenzi
    def handle(self, ev: dict) -> None:
        if ev["kind"] == "button":
            self.tg.answer(ev["id"])
            d = ev["data"]
            if d.startswith("open:"):
                self.open_pending(int(d[5:]))
            elif d.startswith("skip:"):
                p = self.pending.pop(int(d[5:]), None)
                if p:
                    self.tg.clear_buttons(p["msg_id"])
                self.tg.send(msg.skipped())
            elif d.startswith("openall:"):
                for k in [int(x) for x in d[8:].split(",")]:
                    self.open_pending(k)
                self.tg.clear_buttons(ev["msg_id"])
            elif d.startswith("skipall:"):
                for k in [int(x) for x in d[8:].split(",")]:
                    p = self.pending.pop(k, None)
                    if p:
                        self.tg.clear_buttons(p["msg_id"])
                self.tg.clear_buttons(ev["msg_id"])
                self.tg.send(msg.skipped())
            elif d.startswith("close:"):
                self.close_one(d[6:], "YOU")
            elif d == "closeall":
                self.tg.clear_buttons(ev["msg_id"])
                for pid in list(self.known):
                    self.close_one(pid, "YOU")
            elif d == "stopnow":
                self.tg.clear_buttons(ev["msg_id"])
                self.stop_reason = "la cererea ta"
            elif d == "cancel":
                self.tg.clear_buttons(ev["msg_id"])
                self.tg.send(msg.cancelled())
            return
        t = ev["text"].lower().replace("î", "i").replace("â", "a").replace("ă", "a").replace("ș", "s").replace("ț", "t")
        if t.startswith("/status") or "status" in t:
            self.status()
        elif t.startswith("/scan") or "cauta semnale" in t:
            self.scan(manual=True)
        elif not t.startswith("/") and "inchide tot" in t:          # butonul din meniu: cerem confirmare
            if self.known:
                self.tg.send(msg.confirm_close_all(len(self.known)), [[("✅ Da, închide tot", "closeall"), ("❌ Nu", "cancel")]])
            else:
                self.tg.send("📭 Nu ai nicio poziție deschisă.")
        elif not t.startswith("/") and "opreste" in t:
            self.tg.send(msg.confirm_stop(len(self.known)), [[("✅ Da, oprește-te", "stopnow"), ("❌ Nu", "cancel")]])
        elif t.startswith("/stop"):
            self.stop_reason = "la cererea ta"
        elif t.startswith("/inchide") or t.startswith("inchide"):
            arg = t.split(maxsplit=1)[1].strip().upper() if len(t.split(maxsplit=1)) > 1 else ""
            targets = [p["id"] for p in self.known.values() if arg in ("", "TOT", "TOATE") or p["name"] == arg.replace("/", "")]
            if not self.known:
                self.tg.send("📭 Nu ai nicio poziție deschisă.")
            elif not targets or arg == "":
                self.status()                           # fara argument: arata pozitiile cu butoane de inchidere
            else:
                for pid in targets:
                    self.close_one(pid, "YOU")
        elif t.startswith("/ajutor") or t.startswith("/help") or t.startswith("/start") or "ajutor" in t:
            self.tg.send(msg.HELP)

    def expire_pending(self) -> None:
        now = self.now_fn()
        for sid in [k for k, p in self.pending.items() if (now - p["created"]).total_seconds() / 60 > self.cfg["signal_valid_min"]]:
            p = self.pending.pop(sid)
            self.tg.clear_buttons(p["msg_id"])

    def report_error(self, txt: str) -> None:
        last, ts = self.last_err
        if txt != last or time.time() - ts > 3600:
            self.tg.send(msg.error(txt))
            self.last_err = (txt, time.time())

    # ------------------------------------------------------------------ bucla
    def run(self, hours: float) -> None:
        c = self.cfg
        self.tg.drain()
        if os.getenv("CONTINUED") == "1":
            self.tg.send(msg.continued(hours), menu=msg.MENU)
        else:
            self.tg.send(msg.started(hours, c["budget_usd"], c["scan_every_min"], c["tp_usd"], c["basket_target_usd"]), menu=msg.MENU)
        try:
            for p in self.broker.positions():
                if p["name"] in self.inst:
                    self.known[p["id"]] = dict(p, last_pnl=0.0)
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")
        if self.known:
            self.tg.send(f"👀 Am găsit {len(self.known)} poziții deja deschise pe eToro; le urmăresc și pe ele.")
            self.monitor()
        this_run, remaining = plan_session(hours)
        start = time.time()
        end = start + this_run * 3600
        t_scan = t_mon = t_upd = 0.0
        t_hb = time.time()
        warned = False
        sig_mod.signal(sig_mod.SIGTERM, lambda *a: setattr(self, "stop_reason", "GitHub a oprit sesiunea"))
        sig_mod.signal(sig_mod.SIGINT, lambda *a: setattr(self, "stop_reason", "GitHub a oprit sesiunea"))
        while not self.stop_reason:
            try:
                for ev in self.tg.poll(timeout=15):
                    self.handle(ev)
                now = time.time()
                if now - t_scan >= c["scan_every_min"] * 60:
                    t_scan = now
                    self.scan()
                if now - t_mon >= c["pl_check_every_sec"]:
                    t_mon = now
                    self.monitor()
                if now - t_upd >= c["scan_every_min"] * 60 and self.known:
                    t_upd = now
                    self.tg.send(msg.update([{"name": p["name"], "pnl": p["last_pnl"]} for p in self.known.values()],
                                            sum(p["last_pnl"] for p in self.known.values())))
                if now - t_hb >= 3600:
                    t_hb = now
                    n = self.now_fn()
                    self.tg.send(msg.heartbeat(n.strftime("%H:%M"), self.scans, self.last_scan, len(self.known), self.market_open(n)), silent=True)
                self.expire_pending()
                if not warned and remaining <= 0 and end - now < 20 * 60:
                    warned = True
                    self.tg.send(msg.ending_soon(int((end - now) / 60)))
                if now >= end:
                    self.stop_reason = "handover" if remaining > 0.01 else "s-a terminat sesiunea"
            except Exception as e:  # noqa: BLE001 - nu lasam asistentul sa cada pentru o eroare trecatoare
                self.report_error(f"{type(e).__name__}: {str(e)[:150]}")
                self.sleep(10)
        if self.stop_reason == "handover":
            (HERE / "handover.txt").write_text(f"{remaining:g}")          # pasul urmator din workflow porneste sesiunea noua
            self.tg.send(msg.handover(remaining, len(self.known)), silent=True)
        else:
            self.tg.send(msg.stopped(self.stop_reason, len(self.known)))


def main() -> int:
    from broker import EToroBroker
    from etoro import EToroDemo
    from telegram_bot import Telegram
    cfg = json.loads((HERE / "config.json").read_text())
    hours = float(os.getenv("SESSION_HOURS", "5"))
    tg, api = Telegram(), EToroDemo()
    ids = {}
    for inst in cfg["instruments"]:
        ids[inst["name"]] = api.find_instrument_id(inst["etoro"])
    Assistant(cfg, tg, EToroBroker(api, ids)).run(hours)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
