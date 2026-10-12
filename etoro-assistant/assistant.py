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
import pandas as pd
import signals
import state as state_mod
import ta
from broker import OrderUnconfirmed
from etoro import EToroError

HERE = Path(__file__).parent
EUR_QUOTE = {"GER40"}          # cotat in EUR: castigul/pierderea in $ = valoarea in EUR x EURUSD
USD_QUOTE_FACTOR_ONE = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "OIL", "GOLD", "SPX500", "NSDQ100", "DJ30", "GER40"}   # P&L deja in USD; la USDJPY/USDCAD/USDCHF se imparte la pret


INDICES = {"SPX500", "NSDQ100", "DJ30", "GER40"}
MAX_RUN_HOURS = 5.5          # GitHub opreste orice job dupa 6 ore: sesiunile lungi se inlantuie


def plan_session(hours: float) -> tuple[float, float]:
    """(ore de rulat acum, ore ramase pentru sesiunea urmatoare)."""
    this = min(hours, MAX_RUN_HOURS)
    return this, max(0.0, hours - this)


def digits_for(name: str, px: float) -> int:
    return 1 if name in INDICES else 2 if name in ("OIL", "GOLD") else 5 if px < 20 else 3


def parse_time(txt) -> datetime | None:
    """Ora deschiderii de la eToro (ISO, uneori cu fractii de secunda si 'Z'); None daca nu o pot citi."""
    try:
        t = datetime.fromisoformat(str(txt).replace("Z", "+00:00")[:32].split(".")[0] + ("+00:00" if "+" not in str(txt) and "Z" not in str(txt) else ""))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class Assistant:
    def __init__(self, cfg: dict, tg, broker, fetch=ta.fetch_ohlc, now_fn=None, sleep=time.sleep, real: bool = False):
        self.cfg, self.tg, self.broker, self.fetch = cfg, tg, broker, fetch
        self.real = real                          # cont REAL (bani adevarati): decizia utilizatorului, TRADING_MODE=real
        self.unlocked = not real                  # pe real, nimic nu se deschide pana nu confirmi din Telegram
        self.adopt: list[dict] = []               # ordine trimise dar neconfirmate: daca pozitia apare mai tarziu, o preiau
        self.bot_pids: set[str] = set()           # pozitiile deschise de asistent (pe real le urmarim doar pe acestea)
        self.real_balance: float | None = None    # bani disponibili pe contul real, cititi de la eToro
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep
        self.inst = {i["name"]: i for i in cfg["instruments"]}
        self.pending: dict[int, dict] = {}
        self.report_hour = ""            # ora la care am trimis ultimul raport orar de scanare
        self.seen_bar: dict[str, str] = {}
        self.known: dict[str, dict] = {}        # pozitii urmarite: pid -> {..., last_pnl}
        self.expecting: dict[str, str] = {}      # pid -> motiv (YOU / BASKET) cand inchid eu
        self.sid = 0
        self.scans, self.last_scan = 0, "-"
        self.realized, self.n_closed = 0.0, 0
        self.autotrade = False                   # pornit doar de tine, din buton
        self.day, self.day_pnl = "", 0.0
        self.hold_alerted: set[str] = set()
        self.eurusd = 1.08                       # actualizat din eToro la fiecare verificare a pozitiilor
        self.last_slot = None                    # ultimul sfert de ora scanat
        self.stop_reason: str | None = None
        self.last_err: tuple[str, float] = ("", 0.0)

    # ------------------------------------------------------------------ calcule
    def pnl(self, pos: dict, price: float) -> float:
        raw = pos["side"] * pos["units"] * (price - pos["open_rate"])
        usd = raw * self.fx(pos["name"]) if pos["name"] in USD_QUOTE_FACTOR_ONE else raw / price
        half_spread = self.inst[pos["name"]]["cost"] / 2 / 100 * pos["amount"] * pos["leverage"]
        return usd - half_spread                    # estimare dupa costul de iesire (spread)

    def scale(self) -> float:
        """Limitele in $ (TP/SL/pierdere zilnica) cresc proportional cu bugetul fata de cel de baza (150$): fara plafon,
        dar cu aceleasi procente, ca tinta sa ramana o miscare realista a pietei."""
        return max(1.0, self.equity() / self.cfg["budget_usd"])

    def refresh_real(self) -> None:
        if not self.real:
            return
        try:
            c = self.broker.credit()
            if c is not None:
                self.real_balance = c
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi soldul real ({type(e).__name__})")

    def fx(self, name: str) -> float:
        """Cursul pentru a trece in $ valoarea unui instrument cotat in EUR (altfel 1)."""
        return self.eurusd if name in EUR_QUOTE else 1.0

    def used_margin(self) -> float:
        return sum(p["amount"] for p in self.known.values())

    def equity(self) -> float:
        """Bugetul de lucru: cel de baza plus castigul realizat (cresc pozitiile cand castigi, scad cand pierzi, minim 50%)."""
        c = self.cfg
        if self.real:                               # fara plafon: tot ce e disponibil pe cont (poti adauga bani oricand)
            return (self.real_balance or 0.0) + self.used_margin()
        if not c.get("progressive"):
            return c["budget_usd"]
        return max(c["budget_usd"] * c.get("min_budget_frac", 0.5), c["budget_usd"] + self.realized)

    def free_margin(self) -> float:
        return self.equity() * (1.0 if self.real else 1.015) - self.used_margin()       # demo: 1.5% toleranta (3 pozitii de ~50.5$ in 150$)

    def max_pos(self) -> int:
        """Cate pozitii deschise odata: 2 cat timp bugetul e sub 150$, 3 de la 150$ in sus (eToro cere minim 50$ pe pozitie)."""
        c = self.cfg
        return c["max_positions"] if self.equity() >= c["small_account_usd"] else c["max_positions_small"]

    def sizing(self, inst: dict) -> tuple[float, int, float]:
        """(marja $, levier, expunere $). Impart bugetul la nr. de pozitii posibile (minim 50$ pe pozitie, expunere minima 1.000$);
        daca felia nu mai incape din banii liberi, folosesc tot ce e liber, cat timp ramane peste minimele eToro."""
        c = self.cfg
        lev = min(inst["lev_cap"], c["max_leverage"])
        eq, mm = self.equity(), c["min_margin_usd"]
        n = max(1, min(self.max_pos(), int(eq // mm)))
        margin = max(math.floor(eq / n * 100) / 100, mm)
        if margin * lev < c["min_notional"] * 1.005:
            margin = math.ceil(c["min_notional"] * 1.01 / lev * 100) / 100       # minimul eToro pentru expunere
        free = self.free_margin()
        if margin > free + 0.001:
            fit = math.floor(free * 100) / 100
            if fit >= mm and fit * lev >= c["min_notional"] * 1.001:
                margin = fit
        return margin, lev, margin * lev

    def pcts(self, notional: float, atr_pct: float | None = None) -> tuple[float, float]:
        """(distanta TP, distanta SL) ca fractie din pret. TP mic din volatilitatea orara (atins in 1-2 ore),
        SL larg (de cateva ori volatilitatea orara), ambele limitate in $."""
        c = self.cfg
        if not atr_pct:
            return c["tp_usd"] / notional, c["sl_usd"] / notional
        k = self.scale()
        tp = min(max(c["tp_atr"] * atr_pct, k * c["min_tp_usd"] / notional), k * c["max_tp_usd"] / notional)
        sl = min(max(c["sl_atr"] * atr_pct, c["min_sl_pct"] / 100), k * c["max_sl_usd"] / notional)
        return tp, sl

    def levels(self, side: int, px: float, notional: float, atr_pct: float | None = None) -> tuple[float, float, float, float]:
        """(pret SL, pret TP, TP in $, SL in $)"""
        tp, sl = self.pcts(notional, atr_pct)
        return px * (1 - side * sl), px * (1 + side * tp), tp * notional, sl * notional

    def add_realized(self, pnl: float) -> None:
        today = self.now_fn().strftime("%Y-%m-%d")
        if self.day != today:
            self.day, self.day_pnl = today, 0.0
        self.realized += pnl
        self.day_pnl += pnl
        self.n_closed += 1
        self.save_state()

    def save_state(self) -> None:
        state_mod.save({"realized": self.realized, "n_closed": self.n_closed, "autotrade": self.autotrade,
                        "day": self.day, "day_pnl": self.day_pnl, "seen": self.seen_bar,
                        "bot_pids": sorted(self.bot_pids), "unlocked": self.unlocked and self.real})

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
        self.refresh_real()
        t_scan0 = time.time()
        found, overflow, report = 0, [], []
        open_names = {p["name"] for p in self.known.values()}
        for name, inst in self.inst.items():
            if name in open_names or any(p["name"] == name for p in self.pending.values()):
                continue
            lo, hi = inst.get("hours_utc", (0, 24))
            if not lo <= now.hour < hi:                                   # indicii: doar in programul lor
                report.append({"name": name, "rsi": 50.0, "thr": 25, "bar": "?", "note": "în afara programului de tranzacționare", "skip": True})
                continue
            try:
                s = signals.scan(self.fetch(inst["yahoo"], "1h", "90d"), inst["signals"], pd.Timestamp(now))
            except Exception as e:  # noqa: BLE001
                self.report_error(f"nu pot citi datele pentru {msg.pair(name)} ({type(e).__name__})")
                continue
            if s.get("age_min", 0) > self.cfg.get("max_bar_age_min", 100):          # ultima bara e veche: piata lui e inchisa / date blocate
                report.append({"name": name, "rsi": s["rsi"], "thr": 25, "bar": msg.hour_range(s["bar"]), "note": "date vechi, piața lui pare închisă", "skip": True})
                continue
            if os.getenv("QUIET_LOGS") != "1":                   # in repo public nu afisam semnalele/pozitiile in loguri
                print(f"{name}: semnal={s['side']:+d} rsi={s['rsi']:.0f}")
            thr = next((int(n[7:]) for n in inst["signals"] if n.startswith("rsi_rev")), 25)
            report.append({"name": name, "rsi": s["rsi"], "thr": thr, "asia": s.get("asia_pos"), "bar": msg.hour_range(s["bar"]),
                           "trend": s.get("trend"), "rsi_live": s.get("rsi_live"), "tick": s.get("tick"),
                           "rsi_rule": any(n.startswith("rsi_rev") for n in inst["signals"])})
            if s["side"] == 0 or self.seen_bar.get(name) == s["bar"]:
                continue
            if not self.unlocked:                        # cont real neconfirmat: doar urmaresc, nu propun si nu deschid nimic
                continue
            self.seen_bar[name] = s["bar"]
            self.save_state()
            if len(self.known) + len(self.pending) >= self.max_pos():
                overflow.append(name)
                continue
            if self.propose(name, s):
                found += 1
        if overflow:
            self.tg.send(f"ℹ️ Mai sunt semnale pe {', '.join(msg.pair(n).split(' ')[0] for n in overflow)}, dar am deja "
                         f"{self.max_pos()} poziții/semnale în așteptare. Dacă te interesează, spune-mi /scan după ce se eliberează un loc.")
            for n in overflow:
                self.seen_bar.pop(n, None)               # le re-evaluam la urmatoarea scanare
        hour_key = now.strftime("%Y%m%d%H")
        hourly = hour_key != self.report_hour
        if hourly:
            self.report_hour = hour_key
        if (manual or hourly) and not found:
            for n in sorted(open_names | {p["name"] for p in self.pending.values()}):
                report.append({"name": n, "rsi": 50.0, "thr": 25, "bar": report[0]["bar"] if report else "?", "note": "ai deja poziție/semnal"})
            self.tg.send(msg.scan_report(report, time.time() - t_scan0) if report else "🔎 Am scanat acum: nu am putut citi datele, încerc din nou.",
                         silent=not manual)

    ALIASES = {"AUR": "GOLD", "PETROL": "OIL", "SP500": "SPX500", "SP": "SPX500", "SPX": "SPX500", "NASDAQ": "NSDQ100", "NSDQ": "NSDQ100",
               "NDX": "NSDQ100", "DOW": "DJ30", "DJ": "DJ30", "DAX": "GER40", "GER": "GER40"}

    def resolve_name(self, arg: str) -> str | None:
        key = "".join(ch for ch in arg.upper() if ch.isalnum())
        if not key:
            return None
        key = self.ALIASES.get(key, key)
        if key in self.inst:
            return key
        hits = [n for n in self.inst if n.startswith(key)]
        return hits[0] if len(hits) == 1 else None

    def manual_open(self, name: str, side: int) -> None:
        """Deschidere ceruta de tine (ex. «vinde nzd»): calculez marja din banii liberi si te intreb cu OK/NU."""
        if not self.unlocked:
            self.tg.send("🔒 Mai întâi confirmă contul real din mesajul de la pornire (butonul „Confirm”).")
            return
        if any(p["name"] == name for p in self.known.values()):
            self.tg.send(f"ℹ️ Ai deja o poziție deschisă pe {msg.pair(name)}.")
            return
        self.refresh_real()
        atr = None
        try:
            atr = signals.scan(self.fetch(self.inst[name]["yahoo"], "1h", "90d"), self.inst[name]["signals"], pd.Timestamp(self.now_fn())).get("atr_pct")
        except Exception:  # noqa: BLE001
            pass
        try:
            px = self.broker.price(name)
        except Exception as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Nu pot citi prețul pentru {msg.pair(name)}: {str(e)[:120]}")
            return
        self.propose(name, {"side": side, "why": "la cererea ta", "price": px, "atr_pct": atr})

    def adopt_existing(self, name: str) -> None:
        """«preia nzdusd»: pozitiile deschise pe eToro pe acest instrument incep sa fie urmarite de asistent (TP/SL ramase ale eToro)."""
        try:
            found = [p for p in self.broker.positions() if p["name"] == name and str(p["id"]) not in self.bot_pids]
        except Exception as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Nu pot citi pozițiile: {str(e)[:150]}")
            return
        if not found:
            self.tg.send(f"ℹ️ Nu găsesc o poziție {msg.pair(name)} pe care s-o preiau (sau o urmăresc deja).")
            return
        for p in found:
            notional = p["amount"] * p["leverage"]
            tp_usd = abs(p["tp"] - p["open_rate"]) / p["open_rate"] * notional if p.get("tp") and p["open_rate"] else self.cfg["tp_usd"]
            sl_usd = abs(p["sl"] - p["open_rate"]) / p["open_rate"] * notional if p.get("sl") and p["open_rate"] else self.cfg["sl_usd"]
            self.bot_pids.add(str(p["id"]))
            self.known[p["id"]] = {**p, "last_pnl": 0.0, "tp_usd": tp_usd, "sl_usd": sl_usd, "opened_at": self.now_fn()}
        self.save_state()
        self.tg.send(f"✅ Am preluat {len(found)} poziții {msg.pair(name)}. De acum le urmăresc, le văd la 📊 Status și le pot închide de aici.")

    def propose(self, name: str, s: dict) -> bool:
        inst = self.inst[name]
        try:
            px = self.broker.price(name)
        except Exception:  # noqa: BLE001
            px = s["price"]
        side = s["side"]
        amount, lev, notional = self.sizing(inst)
        atr_pct = s.get("atr_pct")
        sl_px, tp_px, tp_usd, sl_usd = self.levels(side, px, notional, atr_pct)
        d = digits_for(name, px)
        free = self.free_margin()
        can = amount <= free + 0.001
        reason = (f"eToro cere minim {msg.usd(self.cfg['min_margin_usd'])} pe poziție și ai doar {msg.usd(free)} liber"
                  if free < self.cfg["min_margin_usd"] else msg.no_free_margin(amount, free))
        text = msg.signal(name, side, s["why"], px, d, amount, lev, notional, tp_px, tp_usd, sl_px, sl_usd, free, can, reason)
        if not can:
            self.tg.send(text)
            return False
        self.sid += 1
        sid = self.sid
        if self.autotrade and self.day_pnl_today() <= -self.cfg["autotrade_daily_loss_usd"] * self.scale():
            self.autotrade = False
            self.save_state()
            self.tg.send(msg.autotrade_limit(self.cfg["autotrade_daily_loss_usd"] * self.scale()))
        if self.autotrade:
            self.pending[sid] = {"name": name, "side": side, "created": self.now_fn(), "msg_id": None, "amount": amount,
                                 "last_msg": self.now_fn(), "reminders": 0, "atr_pct": atr_pct}
            self.tg.send(msg.auto_signal(name, side, s["why"], px, d))
            self.open_pending(sid)
            return True
        mid = self.tg.send(text, [[("✅ OK, deschide", f"open:{sid}"), ("❌ NU", f"skip:{sid}")]])
        self.pending[sid] = {"name": name, "side": side, "created": self.now_fn(), "msg_id": mid, "amount": amount,
                             "last_msg": self.now_fn(), "reminders": 0, "atr_pct": atr_pct}
        ok = [k for k, v in self.pending.items()]
        if len(ok) >= 2:
            ids = ",".join(str(k) for k in ok)
            self.tg.send(f"📦 Ai {len(ok)} semnale în așteptare. Le deschid pe toate dintr-o dată?",
                         [[(f"✅ OK la toate ({len(ok)})", f"openall:{ids}"), ("❌ NU la toate", f"skipall:{ids}")]])
        return True

    def day_pnl_today(self) -> float:
        return self.day_pnl if self.day == self.now_fn().strftime("%Y-%m-%d") else 0.0

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
        if not self.unlocked:
            self.tg.send("🔒 Contul real nu e confirmat în sesiunea asta, nu deschid nimic.")
            return
        self.refresh_real()
        amount, lev, notional = self.sizing(inst)
        if amount > self.free_margin() + 0.001:
            self.tg.send(f"🚫 Nu mai am buget liber pentru {msg.pair(name)}: {msg.no_free_margin(amount, self.free_margin())}.")
            return
        try:
            px = self.broker.price(name)
            sl, tp, _, _ = self.levels(side, px, notional, p.get("atr_pct"))
            d = digits_for(name, px)
            pid = self.broker.open(name, side, amount, lev, round(sl, d), round(tp, d))
        except OrderUnconfirmed as e:
            self.adopt.append({"name": name, "side": side, "before": set(e.before), "at": self.now_fn(), "atr_pct": p.get("atr_pct"),
                               "sl": sl, "tp": tp, "px": px})
            self.tg.send(f"⏳ Ordinul pe {msg.pair(name)} a fost TRIMIS la eToro, dar nu l-am văzut încă în portofoliu "
                         f"(poate fi în curs de execuție). NU repet ordinul.\nRăspuns eToro: {str(e.response)[:250]}\n"
                         f"Cauză frecventă: sold prea mic (eToro cere minim {msg.usd(self.cfg['min_margin_usd'])} pe poziție). "
                         f"Verifică în eToro. Dacă poziția apare, o preiau automat în următoarele 15 minute și o urmăresc.")
            return
        except (EToroError, Exception) as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Ordinul pe {msg.pair(name)} n-a mers (respins): {str(e)[:250]}\nNu am deschis nimic.")
            return
        self.bot_pids.add(str(pid))
        fill = getattr(self.broker, "last", None) or {}
        amount, lev = fill.get("amount", amount), fill.get("leverage", lev)
        if self.real and self.real_balance is not None:
            self.real_balance = max(0.0, self.real_balance - amount)         # banii liberi scad imediat (citirea de la eToro vine la urmatoarea verificare)
        notional = amount * lev
        sl, tp, tp_usd, sl_usd = self.levels(side, px, notional, p.get("atr_pct"))
        self.known[pid] = {"id": pid, "name": name, "side": side, "open_rate": px, "units": notional / (px * self.fx(name)) if name in USD_QUOTE_FACTOR_ONE else notional,
                           "amount": amount, "leverage": lev, "sl": sl, "tp": tp, "last_pnl": 0.0,
                           "tp_usd": tp_usd, "sl_usd": sl_usd, "opened_at": self.now_fn()}
        self.tg.send(("🔴 CONT REAL\n" if self.real else "") + msg.opened(name, side, px, d, amount, lev, notional, tp, tp_usd, sl, sl_usd))
        self.save_state()

    def close_one(self, pid: str, kind: str) -> None:
        pos = self.known.get(pid)
        if not pos:
            return
        self.expecting[pid] = kind
        try:
            pos["last_pnl"] = self.pnl(pos, self.broker.price(pos["name"]))         # rezultat proaspat la momentul inchiderii
        except Exception:  # noqa: BLE001
            pass
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
        self.refresh_real()                               # soldul liber real, proaspat la fiecare verificare
        self.try_adopt()                                  # inainte de citirea pozitiilor, ca cele preluate sa fie incluse
        try:
            current = {p["id"]: p for p in self.broker.positions()
                       if p["name"] in self.inst and (not self.real or str(p["id"]) in self.bot_pids)}
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")
            return
        rows = []
        if any(p["name"] in EUR_QUOTE for p in current.values()):
            try:
                self.eurusd = self.broker.price("EURUSD")
            except Exception:  # noqa: BLE001
                pass
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
                kind, pnl = self.classify_vanished(old, pnl)
            self.bot_pids.discard(str(pid))
            self.add_realized(pnl)
            self.refresh_real()
            self.tg.send(msg.closed(old["name"], kind, pnl, self.realized, self.equity() if self.cfg.get("progressive") else None))
        for pid, pos in current.items():
            self.known[pid] = {**self.known.get(pid, {}), **pos}          # pastram tinta/plasa in $ si ora deschiderii
            if not self.known[pid].get("opened_at"):
                self.known[pid]["opened_at"] = parse_time(pos.get("time")) or self.now_fn()
        self.hold_alert()
        total = sum(r["last_pnl"] for r in rows)
        c = self.cfg
        if check_basket and len(rows) >= c["basket_min_positions"] and total >= c["basket_target_usd"]:
            self.tg.send(msg.basket(len(rows), total))
            for pid in list(self.known):
                self.close_one(pid, "BASKET")

    def try_adopt(self) -> None:
        """Pozitii pentru care ordinul a fost trimis dar neconfirmat: daca apar in portofoliu (in 15 min), le preiau."""
        if not self.adopt:
            return
        now = self.now_fn()
        try:
            allpos = self.broker.positions()
        except Exception:  # noqa: BLE001
            return
        for rec in list(self.adopt):
            hit = next((p for p in allpos if p["id"] not in rec["before"] and p["name"] == rec["name"] and p["side"] == rec["side"]), None)
            if hit:
                self.adopt.remove(rec)
                self.bot_pids.add(str(hit["id"]))
                notional = hit["amount"] * hit["leverage"]
                sl, tp, tp_usd, sl_usd = self.levels(rec["side"], hit["open_rate"] or rec["px"], notional, rec["atr_pct"])
                self.known[hit["id"]] = {**hit, "last_pnl": 0.0, "tp_usd": tp_usd, "sl_usd": sl_usd, "opened_at": now}
                self.save_state()
                self.tg.send(f"✅ Poziția pe {msg.pair(rec['name'])} a apărut în eToro (preț {hit['open_rate']}). O urmăresc acum.")
            elif (now - rec["at"]).total_seconds() > 15 * 60:
                self.adopt.remove(rec)
                self.tg.send(f"⌛ Ordinul pe {msg.pair(rec['name'])} nu a apărut în portofoliu în 15 minute. Probabil n-a fost executat; "
                             f"verifică în eToro (ordine în așteptare).")

    def classify_vanished(self, old: dict, last_pnl: float) -> tuple[str, float]:
        """O pozitie a disparut fara sa o fi inchis eu: a atins TP, SL sau a inchis-o altcineva? Rezultatul ultimei verificari
        poate avea 30 de secunde, deci pentru TP/SL folosesc valorile $ ale nivelurilor, nu ultima citire."""
        tp_usd, sl_usd = old.get("tp_usd", self.cfg["tp_usd"]), old.get("sl_usd", self.cfg["sl_usd"])
        try:
            px = self.broker.price(old["name"])
            side = old["side"]
            if old.get("tp") and side * (px - old["tp"]) >= 0 or last_pnl >= 0.6 * tp_usd:
                return "TP", max(tp_usd, last_pnl) if last_pnl > 0 else tp_usd
            if old.get("sl") and side * (old["sl"] - px) >= 0 or last_pnl <= -0.6 * sl_usd:
                return "SL", min(-sl_usd, last_pnl)
        except Exception:  # noqa: BLE001
            if last_pnl >= 0.6 * tp_usd:
                return "TP", last_pnl
            if last_pnl <= -0.6 * sl_usd:
                return "SL", last_pnl
        return "OTHER", last_pnl

    def hold_alert(self) -> None:
        """O pozitie care nu si-a atins ținta in ~2 ore: te intreb daca vrei sa o inchizi tu."""
        now = self.now_fn()
        for pid, p in self.known.items():
            age = (now - p["opened_at"]).total_seconds() / 60 if p.get("opened_at") else 0
            if age >= self.cfg.get("hold_alert_min", 120) and pid not in self.hold_alerted:
                self.hold_alerted.add(pid)
                self.tg.send(msg.hold_alert(p["name"], int(age // 60), p.get("last_pnl", 0.0)),
                             [[(f"🔒 Închide {msg.pair(p['name']).split(' ')[0]}", f"close:{pid}"), ("👍 Las-o", "cancel")]])

    def status(self) -> None:
        self.monitor()
        self.refresh_real()
        rows = [{"name": p["name"], "side": p["side"], "pnl": p["last_pnl"]} for p in self.known.values()]
        total = sum(r["pnl"] for r in rows)
        buttons = [[(f"🔒 Închide {msg.pair(r['name']).split(' ')[0]}", f"close:{p['id']}")] for r, p in zip(rows, self.known.values())]
        if len(rows) >= 2:
            buttons.append([("🔒🔒 Închide tot", "closeall")])
        self.tg.send(msg.status(rows, total, self.free_margin(), self.equity(), self.realized, self.n_closed, self.autotrade), buttons or None)

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
            elif d == "realok":
                self.tg.clear_buttons(ev["msg_id"])
                self.unlocked = True
                self.save_state()
                self.tg.send("🔓 Confirmat: tranzacționez cu bani REALI, doar cu OK-ul tău la fiecare semnal. "
                             "Poți porni și 🤖 Autotrading din meniu.")
            elif d == "autoon":
                self.tg.clear_buttons(ev["msg_id"])
                self.autotrade = True
                self.save_state()
                self.tg.send(msg.autotrade_on(self.max_pos(), self.cfg["autotrade_daily_loss_usd"] * self.scale()))
            elif d == "stopnow":
                self.tg.clear_buttons(ev["msg_id"])
                self.stop_reason = "la cererea ta"
            elif d == "cancel":
                self.tg.clear_buttons(ev["msg_id"])
                self.tg.send(msg.cancelled())
            return
        t = ev["text"].lower().replace("î", "i").replace("â", "a").replace("ă", "a").replace("ș", "s").replace("ț", "t")
        words = t.replace("/", " ").split()
        if words and words[0] in ("preia", "adopta"):
            name = self.resolve_name(" ".join(words[1:]))
            if name is None:
                self.tg.send("🤔 Pe ce instrument? Scrie de exemplu: preia nzdusd.")
            elif not self.unlocked:
                self.tg.send("🔒 Mai întâi confirmă contul real din mesajul de la pornire.")
            else:
                self.adopt_existing(name)
        elif words and words[0] in ("vinde", "vand", "sell", "cumpara", "cumpar", "buy"):
            name = self.resolve_name(" ".join(words[1:]))
            if name is None:
                self.tg.send("🤔 Nu știu pe ce instrument. Scrie de exemplu: vinde nzdusd, cumpără eurusd, vinde aur, cumpără dax.")
            else:
                self.manual_open(name, -1 if words[0] in ("vinde", "vand", "sell") else 1)
        elif "autotrading" in t or t.startswith("/auto"):
            if not self.unlocked:
                self.tg.send("🔒 Mai întâi confirmă contul real din mesajul de la pornire (butonul „Confirm”).")
            elif self.autotrade:
                self.autotrade = False
                self.save_state()
                self.tg.send(msg.autotrade_off())
            else:
                self.tg.send(msg.confirm_autotrade(self.max_pos(), self.cfg["autotrade_daily_loss_usd"] * self.scale()),
                             [[("✅ Da, pornește autotrading", "autoon"), ("❌ Nu", "cancel")]])
        elif t.startswith("/reset"):
            self.realized, self.n_closed = 0.0, 0
            self.save_state()
            self.tg.send(f"♻️ Am resetat câștigul realizat. Bugetul de lucru e din nou {msg.usd(self.cfg['budget_usd'])}.")
        elif "porne" in t:
            self.tg.send("✅ Sunt deja pornit și scanez. Spune-mi dacă vrei Status sau Caută semnale.")
        elif t.startswith("/status") or "status" in t:
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

    def remind_pending(self) -> None:
        """Cat timp nu ai raspuns la un semnal, il repet (cu sunet) la cateva minute, ca sa nu pierzi ocazia."""
        now = self.now_fn()
        every = self.cfg.get("remind_every_min", 3)
        for sid, p in list(self.pending.items()):
            if p.get("reminders", 0) >= self.cfg.get("max_reminders", 6) or (now - p.get("last_msg", p["created"])).total_seconds() / 60 < every:
                continue
            left = int(self.cfg["signal_valid_min"] - (now - p["created"]).total_seconds() / 60)
            if left <= 0:
                continue
            self.tg.clear_buttons(p["msg_id"])
            p["msg_id"] = self.tg.send(msg.reminder(p["name"], p["side"], p.get("reminders", 0) + 1, left),
                                       [[("✅ OK, deschide", f"open:{sid}"), ("❌ NU", f"skip:{sid}")]])
            p["last_msg"] = now
            p["reminders"] = p.get("reminders", 0) + 1

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
        st = state_mod.load()
        self.realized, self.n_closed = st.get("realized", 0.0), st.get("n_closed", 0)
        self.day, self.day_pnl = st.get("day", ""), st.get("day_pnl", 0.0)
        self.seen_bar = {k: v for k, v in st.get("seen", {}).items() if k in self.inst}      # nu re-propun aceeasi bara dupa o repornire
        cont = os.getenv("CONTINUED") == "1"
        self.autotrade = bool(st.get("autotrade")) and cont                               # sesiune noua pornita de tine: autotrading oprit
        self.bot_pids = set(st.get("bot_pids", [])) if self.real else set()
        self.unlocked = (bool(st.get("unlocked")) and cont) if self.real else True        # pe real: confirmare la fiecare pornire noua
        self.refresh_real()
        if os.getenv("CONTINUED") == "1":
            self.tg.send(msg.continued(hours), menu=msg.MENU)
        else:
            self.tg.send(msg.started(hours, self.equity(), c["scan_every_min"], c["basket_target_usd"], real=self.real), menu=msg.MENU)
        if self.real and not self.unlocked:
            bal = "necunoscut (nu pot citi soldul!)" if self.real_balance is None else msg.usd(self.real_balance)
            mm = c["min_margin_usd"]
            can_n = 0 if self.real_balance is None else min(self.max_pos(), int(self.real_balance // mm))
            self.tg.send(f"🔴 CONT REAL. Sold disponibil: {bal}.\neToro cere minim {msg.usd(mm)} pe poziție. Deschid acum maxim {can_n} poziții "
                         f"(maxim {self.max_pos()} odată cât bugetul e {'sub' if self.equity() < c['small_account_usd'] else 'peste'} {msg.usd(c['small_account_usd'])}).\n"
                         f"Nu deschid nimic până nu confirmi că vrei să tranzacționez cu bani adevărați.",
                         [[("✅ Confirm: cont real", "realok"), ("❌ Nu, oprește", "stopnow")]])
        self.save_state()
        try:
            for p in self.broker.positions():
                if p["name"] in self.inst and (not self.real or str(p["id"]) in self.bot_pids):
                    self.known[p["id"]] = dict(p, last_pnl=0.0)
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")
        if self.known:
            self.tg.send(f"👀 Am găsit {len(self.known)} poziții deschise {'de mine' if self.real else 'pe eToro'}; le urmăresc și pe ele.")
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
                utc = self.now_fn()
                slot = (utc.date(), utc.hour, utc.minute // 15)
                if slot != self.last_slot and (self.last_slot is None or utc.second >= 20):   # la :00/:15/:30/:45 (+20s), cand apare ora noua
                    self.last_slot = slot
                    self.scan()
                if now - t_mon >= c["pl_check_every_sec"]:
                    t_mon = now
                    self.monitor()
                if now - t_upd >= c["scan_every_min"] * 60 and self.known:
                    t_upd = now
                    self.tg.send(msg.update([{"name": p["name"], "pnl": p["last_pnl"]} for p in self.known.values()],
                                            sum(p["last_pnl"] for p in self.known.values())))
                if now - t_hb >= 3600 and not self.market_open(self.now_fn()):
                    t_hb = now
                    n = self.now_fn()
                    self.tg.send(msg.heartbeat(n.strftime("%H:%M"), self.scans, self.last_scan, len(self.known), self.market_open(n)), silent=True)
                self.remind_pending()
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
    real = os.getenv("TRADING_MODE") == "real"
    tg, api = Telegram(), EToroDemo(real=real)
    ids = {}
    for inst in cfg["instruments"]:
        ids[inst["name"]] = api.find_instrument_id(inst["etoro"])
    Assistant(cfg, tg, EToroBroker(api, ids), real=real).run(hours)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
