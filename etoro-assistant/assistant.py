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
import re
import signal as sig_mod
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import advisor
import channel
import chart as chart_mod
import messages as msg
import news as news_mod
import pandas as pd
import signals
import state as state_mod
import ta
from broker import OrderRejected, OrderUnconfirmed, parse_time
from etoro import EToroError

HERE = Path(__file__).parent
EUR_QUOTE = {"GER40"}          # cotat in EUR: castigul/pierderea in $ = valoarea in EUR x EURUSD
USD_QUOTE_FACTOR_ONE = {"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "OIL", "GOLD", "SPX500", "NSDQ100", "DJ30", "GER40"}   # P&L deja in USD; la USDJPY/USDCAD/USDCHF se imparte la pret


INDICES = {"SPX500", "NSDQ100", "DJ30", "GER40"}
MAX_RUN_HOURS = 5.5          # GitHub opreste orice job dupa 6 ore: sesiunile lungi se inlantuie


def plan_session(hours: float) -> tuple[float, float]:
    """(ore de rulat acum, ore ramase pentru sesiunea urmatoare). hours <= 0 = fara limita: mereu mai ramane o sesiune (se relanseaza singur,
    pana apesi «Opreste»)."""
    if hours <= 0:
        return MAX_RUN_HOURS, float("inf")
    this = min(hours, MAX_RUN_HOURS)
    return this, max(0.0, hours - this)


def digits_for(name: str, px: float) -> int:
    return 1 if name in INDICES else 2 if name in ("OIL", "GOLD") else 5 if px < 20 else 3


class Assistant:
    def __init__(self, cfg: dict, tg, broker, fetch=ta.fetch_ohlc, now_fn=None, sleep=time.sleep, real: bool = False):
        self.cfg, self.tg, self.broker, self.fetch = cfg, tg, broker, fetch
        self.aggr = bool(cfg.get("_aggressive"))  # AGGRESSIVE_MODE activ (vezi modes.py)
        self.wave_n: dict[tuple, int] = {}        # cate propuneri a primit deja fiecare val (instrument, cheie val)
        self.last_prop: dict[str, datetime] = {}  # cand am propus ultima oara pe fiecare instrument (pauza intre propuneri)
        self.real = real                          # cont REAL (bani adevarati): decizia utilizatorului, TRADING_MODE=real
        self.unlocked = not real                  # pe real, nimic nu se deschide pana nu confirmi din Telegram
        self.miss: dict[str, int] = {}            # de cate ori la rand o pozitie urmarita lipseste din portofoliu
        self.last_ok: float | None = None         # ultima citire reusita a soldului real
        self.adopt: list[dict] = []               # ordine trimise dar neconfirmate: daca pozitia apare mai tarziu, o preiau
        self.bot_pids: set[str] = set()           # pozitiile deschise de asistent (pe real le urmarim doar pe acestea)
        self.blocked: dict[str, dict] = {}        # semnale propuse care nu s-au putut deschide (bani liberi): raportul de scanare nu le contrazice
        self.acct_eq: float | None = None         # totalul contului la ultima verificare (bani liberi + marja pozitiilor): se schimba doar cu profitul/pierderea si cu banii intrati/iesiti
        self.realized_acc = 0.0                   # profitul/pierderea inchise de la ultima verificare
        self.money_cand: tuple[float, float] | None = None   # o schimbare mare de total, asteptata sa se confirme la urmatoarea verificare
        self.time_stop_tried: dict[str, datetime] = {}   # cand am incercat ultima oara sa inchid o pozitie dupa limita de timp
        self.counter_pids: set[str] = set()       # pozitiile deschise pe revenire (contra trendului orar), planificat: sfatul le judeca dupa plan
        self.real_balance: float | None = None    # bani disponibili pe contul real, cititi de la eToro
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep
        self.inst = {i["name"]: i for i in cfg["instruments"]}
        self.pending: dict[int, dict] = {}
        self.total_pnl, self.history, self.since, self.report_day, self.n_total = 0.0, {}, "", "", 0
        self.report_hour = ""            # ora la care am trimis ultimul raport orar de scanare
        self.seen_bar: dict[str, str] = {}
        self.known: dict[str, dict] = {}        # pozitii urmarite: pid -> {..., last_pnl}
        self.expecting: dict[str, str] = {}      # pid -> motiv (YOU / BASKET) cand inchid eu
        self.sid = 0
        self.scans, self.last_scan = 0, "-"
        self.realized, self.n_closed = 0.0, 0
        self.total_pnl, self.history, self.since, self.report_day = 0.0, {}, "", ""     # câștig total de la început, pe zile
        self.autotrade = False                   # pornit doar de tine, din buton
        self.day, self.day_pnl = "", 0.0
        self.profit_lock_day = ""                # ziua in care am anuntat blocajul de profit
        self.news = news_mod.NewsFeed(cfg.get("news"))   # calendar economic: pauza in jurul stirilor importante
        self.hold_alerted: set[str] = set()
        self.advice_sent: dict[str, float] = {}   # cand ti-am dat ultima oara sfatul "inchide" pentru fiecare pozitie
        self.advice_last: dict[str, tuple] = {}   # (verdict, motiv), ora ultimului sfat trimis: un sfat identic nu se repeta
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
                self.last_ok = time.time()
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi soldul real ({type(e).__name__}{' ' + str(e.status) if getattr(e, 'status', None) else ''})")

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

    def oil_reserve(self) -> float:
        """Banii rezervati DOAR pentru petrol (doar pe real si doar cand bugetul ajunge pentru rezerva + 2 pozitii de forex): forexul nu-i poate folosi."""
        r = self.cfg.get("oil_reserve_usd", 0)
        if not (self.real and r):
            return 0.0
        return float(r) if self.equity() >= r + 2 * self.cfg["min_margin_usd"] else 0.0

    def free_margin(self, name: str | None = None) -> float:
        """Banii liberi. Pentru un instrument care NU e petrol se scade rezerva petrolului, cat timp nu e folosita de o pozitie sau o propunere pe petrol."""
        free = self.equity() * (1.0 if self.real else 1.015) - self.used_margin()       # demo: 1.5% toleranta (3 pozitii de ~50.5$ in 150$)
        if name and name != "OIL":
            oil_used = sum(p["amount"] for p in self.known.values() if p["name"] == "OIL")      # marja petrolului deschis e deja scazuta din `free`
            free -= max(0.0, self.oil_reserve() - oil_used)                                      # o propunere pe petrol inca neexecutata tine rezerva ocupata
        return free

    def max_pos(self) -> int:
        """Cate pozitii deschise odata: 2 cat timp bugetul e sub 150$, 3 de la 150$ in sus (eToro cere minim 50$ pe pozitie)."""
        c = self.cfg
        return c["max_positions"] if self.equity() >= c["small_account_usd"] else c["max_positions_small"]

    def sizing(self, inst: dict, boost: bool = False) -> tuple[float, int, float]:
        """(marja $, levier, expunere $). Impart bugetul la nr. de pozitii posibile (minim 50$ pe pozitie, expunere minima 1.000$);
        daca felia nu mai incape din banii liberi, folosesc tot ce e liber, cat timp ramane peste minimele eToro."""
        c = self.cfg
        lev = min(inst["lev_cap"], c["max_leverage"])
        eq, mm = self.equity(), c["min_margin_usd"]
        name, reserve = inst.get("name"), self.oil_reserve()
        if reserve and name == "OIL":                                             # petrolul: toata rezerva lui (minim: expunerea de 1.000 $ ceruta de eToro)
            margin = max(reserve, math.ceil(c["min_notional"] * 1.01 / lev * 100) / 100)
            free = self.free_margin(name)
            if margin > free + 0.001:
                fit = math.floor(free * 100) / 100
                if fit >= mm and fit * lev >= c["min_notional"] * 1.001:
                    margin = fit
            return margin, lev, margin * lev
        if reserve:                                                               # restul instrumentelor impart bugetul fara rezerva petrolului
            eq -= reserve
        n = max(1, min(self.max_pos() - (1 if reserve else 0), int(eq // mm)))
        margin = max(math.floor(eq / n * 100) / 100, mm)
        if boost and c.get("boost_alloc"):                                       # AGGRESSIVE: val + RSI extrem => pana la 40% din cont
            margin = max(margin, math.floor(eq * c["boost_alloc"] * 100) / 100)
        if margin * lev < c["min_notional"] * 1.005:
            margin = math.ceil(c["min_notional"] * 1.01 / lev * 100) / 100       # minimul eToro pentru expunere
        free = self.free_margin(name)
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
        self.realized_acc += pnl
        self.day_pnl += pnl
        self.n_closed += 1
        self.total_pnl += pnl
        self.n_total += 1
        h = self.history.setdefault(msg.ro_dt(self.now_fn()).strftime("%Y-%m-%d"), {"pnl": 0.0, "n": 0})   # ziua dupa ora Romaniei
        h["pnl"] = round(h["pnl"] + pnl, 2)
        h["n"] += 1
        self.save_state()

    def save_state(self) -> None:
        state_mod.save({"realized": self.realized, "n_closed": self.n_closed, "autotrade": self.autotrade,
                        "day": self.day, "day_pnl": self.day_pnl, "seen": self.seen_bar,
                        "total_pnl": self.total_pnl, "n_total": self.n_total, "history": self.history, "since": self.since, "report_day": self.report_day,
                        "bot_pids": sorted(self.bot_pids), "counter_pids": sorted(self.counter_pids), "unlocked": self.unlocked and self.real,
                        "adopt": [{"name": r["name"], "side": r["side"], "before": sorted(r["before"]), "at": r["at"].isoformat(),
                                   "atr_pct": r.get("atr_pct"), "px": r.get("px")} for r in self.adopt]})

    def market_open(self, now: datetime) -> bool:
        return not (now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 20) or now.hour in (21, 22))

    # ------------------------------------------------------------------ scanare
    def scan(self, manual: bool = False) -> None:
        now = self.now_fn()
        self.scans += 1
        self.last_scan = msg.ro_hm(now)
        if not self.market_open(now):
            if manual:
                self.tg.send("😴 Piața e închisă sau prea aproape de închidere, nu caut semnale acum.")
            return
        self.sync()                                      # sold si pozitii la zi, inainte de orice calcul
        t_scan0 = time.time()
        found, overflow, report = 0, [], []
        open_names = {p["name"] for p in self.known.values()}
        self.refresh_blocked(now)
        self.news_heads_up(now, open_names)
        for name, inst in self.inst.items():
            if name in open_names or any(p["name"] == name for p in self.pending.values()):
                continue
            ev = self.news.blocking(name, now)
            if ev:                                                        # stire importanta chiar acum: nu propunem pe aceasta moneda
                report.append({"name": name, "rsi": 50.0, "thr": 25, "bar": "?", "note": f"pauză știri: {ev['title']}", "skip": True})
                continue
            lo, hi = inst.get("hours_utc", (0, 24))
            if not lo <= now.hour < hi:                                   # indicii: doar in programul lor
                report.append({"name": name, "rsi": 50.0, "thr": 25, "bar": "?", "note": "în afara programului de tranzacționare", "skip": True})
                continue
            try:
                s = signals.scan(self.fetch(inst["yahoo"], "1h", "90d"), inst["signals"], pd.Timestamp(now),
                                 self.cfg.get("wave_atr", 1.6), self.cfg.get("wave_bars", 3), self.cfg.get("wave_opts"))
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
                           "trend": s.get("trend"), "rsi_live": s.get("rsi_live"), "tick": s.get("tick"), "move_atr": s.get("move_atr", 0.0),
                           "side": s["side"],
                           "rsi_rule": any(n.startswith("rsi_rev") for n in inst["signals"])})
            key = s.get("sig_key", s["bar"])
            is_wave = str(key).startswith("wave")
            if s["side"] == 0:
                continue
            rej = signals.gate(s, self.cfg.get("entry_gate"))
            if rej:                                      # nu e „semnal”, e doar o părere: nu propunem nimic
                report[-1].update(note=msg.gate_reason(*rej, self.cfg["entry_gate"]), skip=True)
                continue
            if self.cfg.get("entry_gate", {}).get("enabled") and not is_wave:
                s["quality_note"] = msg.gate_ok(s)
            if is_wave:                                  # un val poate primi cel mult N propuneri (1 normal, 2 in modul agresiv)
                if self.wave_n.get((name, key), 0) >= self.cfg.get("wave_max_proposals", 1):
                    continue
            elif self.seen_bar.get(name) == key:
                continue
            if not self.unlocked:                        # cont real neconfirmat: doar urmaresc, nu propun si nu deschid nimic
                continue
            if self.profit_locked():                     # profitul zilei a atins tinta: nu mai deschidem nimic pana maine
                continue
            cool =self.cfg.get("signal_cooldown_min", 0)
            last = self.last_prop.get(name)
            if cool and last and (now - last).total_seconds() < cool * 60:
                continue                                 # pauza intre propuneri pe acelasi instrument (modul agresiv)
            self.seen_bar[name] = key
            if is_wave:
                self.wave_n[(name, key)] = self.wave_n.get((name, key), 0) + 1
            self.save_state()
            if len(self.known) + len(self.pending) >= self.max_pos():
                overflow.append((name, key, is_wave))
                continue
            if self.propose(name, s):
                self.last_prop[name] = now
                found += 1
        if overflow:
            self.tg.send(f"ℹ️ Mai sunt semnale pe {', '.join(msg.pair(n).split(' ')[0] for n, _, _ in overflow)}, dar am deja "
                         f"{self.max_pos()} poziții/semnale în așteptare. Dacă te interesează, spune-mi /scan după ce se eliberează un loc.")
            for n, k, w in overflow:
                self.seen_bar.pop(n, None)               # le re-evaluam la urmatoarea scanare
                if w:
                    self.wave_n[(n, k)] = max(0, self.wave_n.get((n, k), 1) - 1)
        every = int(self.cfg.get("radar_every_h", 4))
        slot_key = f"{now:%Y%m%d}-{now.hour // every}"
        radar = slot_key != self.report_hour and not found
        if radar:
            self.report_hour = slot_key
        if manual and not found:
            valid = timedelta(minutes=self.cfg["signal_valid_min"])
            active = [{"name": p["name"], "side": p["side"], "until": p["created"] + valid, "status": "așteaptă OK-ul tău pe butoanele de mai sus"}
                      for p in self.pending.values() if now - p["created"] <= valid]
            active += [{**b, "until": b["at"] + valid} for n, b in self.blocked.items()
                       if n not in open_names and now - b["at"] <= valid and all(a["name"] != n for a in active)]
            have = {a["name"] for a in active}
            for n in sorted(open_names - have):
                report.append({"name": n, "rsi": 50.0, "thr": 25, "bar": "?", "note": "ai deja poziție", "skip": True})
            self.tg.send(msg.scan_report(report, time.time() - t_scan0, active) if report or active
                         else "🔎 Am scanat acum: nu am putut citi datele, încerc din nou.")
        elif radar and report:
            self.tg.send(msg.radar(report, msg.ro_hm(now)), silent=True)

    def reconcile(self) -> bool:
        """Recalculeaza profitul pe zile si totalul din istoricul REAL al pozitiilor inchise de la eToro (nu din estimari). Doar pe real."""
        if not (self.real and hasattr(self.broker, "closed_trades")):
            return False
        since = self.since or msg.ro_dt(self.now_fn()).strftime("%Y-%m-%d")
        try:
            trades = self.broker.closed_trades((datetime.fromisoformat(since) - timedelta(days=1)).strftime("%Y-%m-%d"))
        except Exception:  # noqa: BLE001
            return False
        hist: dict[str, dict] = {}
        for t in trades:
            d = msg.ro_dt(t["close_time"])
            day = d.strftime("%Y-%m-%d") if d else None
            if day is None or day < since:
                continue
            h = hist.setdefault(day, {"pnl": 0.0, "n": 0})
            h["pnl"] = round(h["pnl"] + t["net"], 2)
            h["n"] += 1
        if not hist and self.history:                     # raspuns gol (eroare/intarziere): nu stergem ce stim
            return False
        self.history = hist
        self.total_pnl = round(sum(v["pnl"] for v in hist.values()), 2)
        self.n_total = sum(v["n"] for v in hist.values())
        self.save_state()
        return True

    def profit_text(self) -> str:
        """Aceleasi doua randuri peste tot: profit AZI (data Romaniei) si profit TOTAL de la inceput."""
        today = msg.ro_dt(self.now_fn()).strftime("%Y-%m-%d")
        d = self.history.get(today, {"pnl": 0.0, "n": 0})
        return msg.profit_block(today, d["pnl"], d["n"], self.total_pnl, self.n_total, self.since or today)

    def report_due(self, now: datetime) -> bool:
        """Raportul zilei: cu ~30 min inainte de inchiderea pietei (vineri 20:00 UTC, in rest 21:00 UTC), o data pe zi (data Romaniei)."""
        if now.weekday() >= 5:
            return False
        cutoff = (19, 30) if now.weekday() == 4 else (20, 30)
        return (now.hour, now.minute) >= cutoff and msg.ro_dt(now).strftime("%Y-%m-%d") != self.report_day and now.hour < 23

    def daily_report(self, final: bool = True) -> None:
        self.reconcile()                                  # cifrele din raport vin din istoricul real eToro
        now = self.now_fn()
        today = msg.ro_dt(now).strftime("%Y-%m-%d")
        d = self.history.get(today, {"pnl": 0.0, "n": 0})
        unreal = sum(p.get("last_pnl", 0.0) for p in self.known.values())
        days = [(k, v) for k, v in sorted(self.history.items()) if k != today][-5:]
        open_rows = [{"name": p["name"], "side": p["side"], "pnl": p.get("last_pnl", 0.0), "tp_usd": p.get("tp_usd", self.cfg["tp_usd"]),
                      "sl_usd": p.get("sl_usd", self.cfg["sl_usd"])} for p in self.known.values()]
        self.tg.send(msg.daily_report(today, d["pnl"], d["n"], unreal, open_rows, days, self.total_pnl, self.since, self.n_total, final))
        if final:
            self.report_day = today
            self.save_state()

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
        self.sync()
        if any(p["name"] == name for p in self.known.values()):
            self.tg.send(f"ℹ️ Ai deja o poziție deschisă pe {msg.pair(name)}.")
            return
        if any(p["name"] == name for p in self.pending.values()):
            self.tg.send(f"ℹ️ Ai deja o propunere în așteptare pe {msg.pair(name)}; răspunde-i mai întâi.")
            return
        if len(self.known) + len(self.pending) >= self.max_pos():
            self.tg.send(f"ℹ️ Ai deja {len(self.known) + len(self.pending)} poziții/propuneri; maxim acum: {self.max_pos()}. "
                         f"Închide una sau răspunde la propuneri.")
            return
        info: dict = {}
        try:
            info = signals.scan(self.fetch(self.inst[name]["yahoo"], "1h", "90d"), self.inst[name]["signals"], pd.Timestamp(self.now_fn()))
        except Exception:  # noqa: BLE001
            pass
        atr = info.get("atr_pct")
        try:
            px = self.broker.price(name)
        except Exception as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Nu pot citi prețul pentru {msg.pair(name)}: {str(e)[:120]}")
            return
        self.propose(name, {**info, "side": side, "why": "la cererea ta", "price": px, "atr_pct": atr})

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
            self.bot_pids.add(str(p["id"]))
            self.track(p)
        self.save_state()
        self.tg.send(f"✅ Am preluat {len(found)} poziții {msg.pair(name)}. De acum le urmăresc, le văd la 📊 Status și le pot închide de aici.")

    def propose(self, name: str, s: dict) -> bool:
        inst = self.inst[name]
        try:
            px = self.broker.price(name)
        except Exception:  # noqa: BLE001
            px = s["price"]
        side = s["side"]
        boost = self.is_boost(name, s)
        amount, lev, notional = self.sizing(inst, boost)
        atr_pct = s.get("atr_pct")
        sl_px, tp_px, tp_usd, sl_usd = self.levels(side, px, notional, atr_pct)
        d = digits_for(name, px)
        free = self.free_margin(name)
        can = amount <= free + 0.001
        reason = (f"eToro cere minim {msg.usd(self.cfg['min_margin_usd'])} pe poziție și ai doar {msg.usd(free)} liber"
                  if free < self.cfg["min_margin_usd"] else msg.no_free_margin(amount, free))
        counter = advisor.against_trend(side, s.get("trend"))                 # intrare pe revenire, contra trendului orar (planificata)
        why_full = s["why"] + (f". Mă aștept la revenire, deși trendul orar e în {'jos' if s.get('trend') == 'jos' else 'sus'}" if counter else "")
        if s.get("quality_note"):
            why_full += ". " + s["quality_note"]
        ctx = self.context_line(s)
        text = msg.signal(name, side, why_full + ctx, px, d, amount, lev, notional, tp_px, tp_usd, sl_px, sl_usd, free, can, reason)
        tag = self.aggr_tag(name, s, boost)
        if tag:
            text = tag + "\n" + text
        if not can:
            self.blocked[name] = {"name": name, "side": side, "at": self.now_fn(), "status": reason}
            self.tg.send(text)
            return False
        self.blocked.pop(name, None)
        self.sid += 1
        sid = self.sid
        if self.autotrade and self.day_pnl_today() <= -self.cfg["autotrade_daily_loss_usd"] * self.scale():
            self.autotrade = False
            self.save_state()
            self.tg.send(msg.autotrade_limit(self.cfg["autotrade_daily_loss_usd"] * self.scale()))
        if self.autotrade:
            self.pending[sid] = {"name": name, "side": side, "created": self.now_fn(), "msg_id": None, "amount": amount,
                                 "last_msg": self.now_fn(), "reminders": 0, "atr_pct": atr_pct, "boost": boost, "counter": counter}
            self.send_chart(name, s, side, px, tp_px, sl_px, f"{msg.pair(name)}: autotrading, intrare, țintă și plasă")
            self.tg.send((tag + " " if tag else "") + msg.auto_signal(name, side, why_full, px, d))
            self.open_pending(sid)
            return True
        self.send_chart(name, s, side, px, tp_px, sl_px, f"{msg.pair(name)}: așa arată piața acum și unde ar sta ținta și plasa")
        buttons = [[("✅ OK, deschide", f"open:{sid}"), ("❌ NU", f"skip:{sid}")]]
        ok = [*self.pending, sid]
        if len(ok) >= 2:                                   # un singur mesaj: semnalul + butoanele „la toate”, nu un al doilea mesaj separat
            ids = ",".join(str(k) for k in ok)
            buttons.append([(f"✅ OK la toate ({len(ok)})", f"openall:{ids}"), ("❌ NU la toate", f"skipall:{ids}")])
        mid = self.tg.send(text, buttons)
        self.pending[sid] = {"name": name, "side": side, "created": self.now_fn(), "msg_id": mid, "amount": amount,
                             "last_msg": self.now_fn(), "reminders": 0, "atr_pct": atr_pct, "boost": boost, "counter": counter}
        return True

    def is_boost(self, name: str, s: dict) -> bool:
        """AGGRESSIVE: val (surfer) SI RSI extrem in aceeasi directie => alocare mai mare (pana la 40% din cont, cat incape din banii liberi)."""
        if not (self.aggr and str(s.get("sig_key", "")).startswith("wave")) or s.get("rsi_live") is None:
            return False
        thr = next((int(n[7:]) for n in self.inst[name]["signals"] if n.startswith("rsi_rev")), None)
        if thr is None:
            return False
        r = s["rsi_live"]
        return (s["side"] == 1 and r >= 100 - thr) or (s["side"] == -1 and r <= thr)

    def aggr_tag(self, name: str, s: dict, boost: bool) -> str:
        """Prefix pentru mesajele din modul agresiv, ex. «[AGGRESSIVE] RSI 64 + SURFER 1.3×»."""
        if not self.aggr:
            return ""
        parts = []
        thr = next((int(n[7:]) for n in self.inst[name]["signals"] if n.startswith("rsi_rev")), None)
        r = s.get("rsi_live", s.get("rsi"))
        if thr is not None and r is not None and (r <= thr or r >= 100 - thr):
            parts.append(f"RSI {r:.0f}")
        if str(s.get("sig_key", "")).startswith("wave"):
            parts.append(f"SURFER {abs(s.get('move_atr', 0)):.1f}×")
        return "[AGGRESSIVE] " + (" + ".join(parts) if parts else "reguli clasice") + (" · alocare mărită" if boost else "")

    def day_pnl_today(self) -> float:
        return self.day_pnl if self.day == self.now_fn().strftime("%Y-%m-%d") else 0.0

    def news_heads_up(self, now: datetime, open_names: set[str]) -> None:
        """Cu ~1 ora inainte de o stire importanta pentru instrumentele urmarite: un singur mesaj pe eveniment."""
        try:
            relevant = [e for e in self.news.ahead(now) if any(e["cur"] in news_mod.currencies_for(n) for n in self.inst)]
            if not relevant:
                return
            held = sorted(n for n in open_names if any(e["cur"] in news_mod.currencies_for(n) for e in relevant))
            self.tg.send(msg.news_ahead(relevant, int(self.news.before.total_seconds() // 60), int(self.news.after.total_seconds() // 60), held))
        except Exception as e:  # noqa: BLE001
            print(f"[!] Anunt stiri: {type(e).__name__}")

    def profit_locked(self) -> bool:
        """Blocaj de profit: cand profitul REALIZAT de azi atinge `daily_profit_lock_usd` (scalat cu bugetul), nu mai propunem si nu mai
        deschidem nimic pana maine. Pozitiile deschise isi pastreaza tinta si plasa. 0 = oprit. Te anunta o singura data pe zi."""
        lock = self.cfg.get("daily_profit_lock_usd", 0) * self.scale()
        if not lock or self.day_pnl_today() < lock:
            return False
        today = self.now_fn().strftime("%Y-%m-%d")
        if self.profit_lock_day != today:
            self.profit_lock_day = today
            self.tg.send(msg.profit_lock(self.day_pnl_today(), lock))
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
        if not self.unlocked:
            self.tg.send("🔒 Contul real nu e confirmat în sesiunea asta, nu deschid nimic.")
            return
        self.sync()                                              # sold si pozitii la zi INAINTE de dimensionare
        if any(k["name"] == name for k in self.known.values()):
            self.tg.send(f"ℹ️ Ai deja o poziție deschisă pe {msg.pair(name)}, nu deschid încă una.")
            return
        amount, lev, notional = self.sizing(inst, bool(p.get("boost")))
        free = self.free_margin(name)
        if amount > free + 0.001 or amount < self.cfg["min_margin_usd"] - 0.001:
            self.tg.send(f"🚫 Nu pot deschide {msg.pair(name)}: " + (
                f"eToro cere minim {msg.usd(self.cfg['min_margin_usd'])} pe poziție și ai {msg.usd(free)} liber."
                if free < self.cfg["min_margin_usd"] else msg.no_free_margin(amount, free)) + ".")
            return
        px = sl = tp = None
        try:
            px = self.live_price(name, side)
            sl, tp, _, _ = self.levels(side, px, notional, p.get("atr_pct"))
            d = digits_for(name, px)
            problem = self.order_problem(side, px, round(sl, d), round(tp, d))
            if problem:
                self.tg.send(f"🛑 Nu trimit ordinul pe {msg.pair(name)}: {problem}")
                return
            pid = self.broker.open(name, side, amount, lev, round(sl, d), round(tp, d), max_amount=free)
        except OrderUnconfirmed as e:
            self.adopt.append({"name": name, "side": side, "before": set(e.before), "at": e.sent_at or self.now_fn(),
                               "atr_pct": p.get("atr_pct"), "px": px})
            self.save_state()
            low = free < self.cfg["min_margin_usd"] + 0.01
            cause = (f"Cauză probabilă: bani liberi sub minimul eToro ({msg.usd(self.cfg['min_margin_usd'])} pe poziție)." if low else
                     "Banii liberi sunt suficienți; ordinul pare încă în procesare la eToro (sau a fost refuzat acolo).")
            self.tg.send(f"⏳ Ordinul pe {msg.pair(name)} a fost trimis, dar nu apare încă în portofoliu. NU repet ordinul.\n{cause}\n"
                         f"Dacă poziția apare, o preiau automat în următoarele 15 minute și o urmăresc.")
            return
        except (OrderRejected, EToroError, Exception) as e:  # noqa: BLE001
            self.tg.send(f"⚠️ Ordinul pe {msg.pair(name)} n-a mers (respins): {str(e)[:250]}\nNu am deschis nimic.")
            return
        self.bot_pids.add(str(pid))
        if p.get("counter"):
            self.counter_pids.add(str(pid))
        fill = getattr(self.broker, "last", None) or {}
        amount, lev = fill.get("amount", amount), fill.get("leverage", lev)
        if self.real and self.real_balance is not None:
            self.real_balance = max(0.0, self.real_balance - amount)         # banii liberi scad imediat (citirea de la eToro vine la urmatoarea verificare)
        notional = amount * lev
        sl, tp, tp_usd, sl_usd = self.levels(side, px, notional, p.get("atr_pct"))
        self.known[pid] = {"id": pid, "name": name, "side": side, "open_rate": px, "units": notional / (px * self.fx(name)) if name in USD_QUOTE_FACTOR_ONE else notional,
                           "amount": amount, "leverage": lev, "sl": sl, "tp": tp, "last_pnl": 0.0,
                           "tp_usd": tp_usd, "sl_usd": sl_usd, "opened_at": self.now_fn(), "counter": bool(p.get("counter"))}
        self.tg.send(("🔴 CONT REAL\n" if self.real else "") + msg.opened(name, side, px, d, amount, lev, notional, tp, tp_usd, sl, sl_usd))
        self.save_state()

    def order_problem(self, side: int, px: float, sl: float, tp: float) -> str | None:
        """Verificari de bun-simt inainte sa trimit un ordin cu bani: SL/TP de partea corecta a pretului si la distanta rezonabila."""
        if not (px > 0 and sl > 0 and tp > 0):
            return "pret sau niveluri invalide"
        ok = (sl < px < tp) if side == 1 else (tp < px < sl)
        if not ok:
            return f"plasa ({sl}) și ținta ({tp}) nu sunt de-o parte și de alta a prețului ({px})"
        if min(abs(px - sl), abs(tp - px)) / px < 0.0003:
            return "țința sau plasa sunt prea aproape de preț (sub 0,03%)"
        return None

    def close_one(self, pid: str, kind: str) -> None:
        pos = self.known.get(pid)
        if not pos:
            return
        self.expecting[pid] = kind
        pos["last_pnl"] = self.fresh_pnl(pos)                                   # rezultat proaspat la momentul inchiderii
        try:
            self.broker.close(pid, pos["name"])
        except Exception as e:  # noqa: BLE001
            self.expecting.pop(pid, None)
            self.tg.send(f"⚠️ N-am reușit să închid {msg.pair(pos['name'])}: {str(e)[:150]}\nÎncearcă din eToro dacă e urgent.")
            return
        self.sleep(3)
        self.monitor(check_basket=False)                # confirma inchiderea si anunta

    # ------------------------------------------------------------------ urmarire pozitii
    def track(self, p: dict, atr_pct: float | None = None) -> None:
        """Incep sa urmaresc o pozitie: tinta/plasa in $ vin din ATR (pozitii deschise de mine) sau din nivelurile puse pe eToro."""
        notional = p["amount"] * p["leverage"]
        if atr_pct:
            _, _, tp_usd, sl_usd = self.levels(p["side"], p["open_rate"] or 1.0, notional, atr_pct)
        else:
            op = p["open_rate"]
            tp_usd = abs(p["tp"] - op) / op * notional if p.get("tp") and op else self.cfg["tp_usd"]
            sl_usd = abs(p["sl"] - op) / op * notional if p.get("sl") and op else self.cfg["sl_usd"]
        self.known[p["id"]] = {**p, "last_pnl": 0.0, "tp_usd": tp_usd, "sl_usd": sl_usd, "counter": str(p["id"]) in self.counter_pids,
                               "opened_at": parse_time(p.get("time")) or self.now_fn()}

    def sync(self) -> None:
        """Aduce starea la zi (sold si pozitii de la eToro) inainte de dimensionare sau ordine."""
        self.monitor(check_basket=False)

    def quote_pnl(self, pos: dict, q: dict) -> float | None:
        """Profit/pierdere din cotatia live: iesirea se face la bid (pozitie lunga) sau ask (scurta), iar cursul de conversie
        aduce valoarea in $. Spread-ul e inclus deja in bid/ask."""
        conv = q.get("conv_bid") or 0
        if conv <= 0:
            return None
        exit_px = q["bid"] if pos["side"] == 1 else q["ask"]
        return pos["side"] * pos["units"] * (exit_px - pos["open_rate"]) * conv

    def fresh_pnl(self, pos: dict) -> float:
        try:
            q = self.broker.quotes([pos["name"]]).get(pos["name"]) if hasattr(self.broker, "quotes") else None
            v = self.quote_pnl(pos, q) if q else None
            return v if v is not None else self.pnl(pos, self.broker.price(pos["name"]))
        except Exception:  # noqa: BLE001
            return pos.get("last_pnl", 0.0)

    def live_price(self, name: str, side: int) -> float:
        """Pretul la care s-ar deschide acum (ask la cumparare, bid la vanzare); altfel ultima lumanare."""
        try:
            if hasattr(self.broker, "quotes"):
                q = self.broker.quotes([name]).get(name)
                if q:
                    return q["ask"] if side == 1 else q["bid"]
        except Exception:  # noqa: BLE001
            pass
        return self.broker.price(name)

    def monitor(self, check_basket: bool = True) -> None:
        self.refresh_real()                               # soldul liber real, proaspat la fiecare verificare
        self.try_adopt()                                  # inainte de citirea pozitiilor, ca cele preluate sa fie incluse
        try:
            allp = self.broker.positions()
            current = {p["id"]: p for p in allp
                       if p["name"] in self.inst and (not self.real or str(p["id"]) in self.bot_pids)}
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")
            return
        rows = []
        qs: dict = {}
        if current and hasattr(self.broker, "quotes"):
            try:
                qs = self.broker.quotes(sorted({p["name"] for p in current.values()}))
            except Exception:  # noqa: BLE001
                qs = {}
        if any(p["name"] in EUR_QUOTE and p["name"] not in qs for p in current.values()):
            try:
                self.eurusd = self.broker.price("EURUSD")
            except Exception:  # noqa: BLE001
                pass
        for pid, pos in current.items():
            pnl = self.quote_pnl(pos, qs[pos["name"]]) if pos["name"] in qs else None
            if pnl is None:
                try:
                    pnl = self.pnl(pos, self.broker.price(pos["name"]))
                except Exception:  # noqa: BLE001
                    pnl = self.known.get(pid, {}).get("last_pnl", 0.0)
            pos["last_pnl"] = pnl
            q = qs.get(pos["name"])
            if q:
                pos["px_now"] = q["bid"] if pos["side"] == 1 else q["ask"]
            rows.append(pos)
        # pozitii care au disparut: inchise (TP / SL / de tine / de mine). O singura citire fara ele poate fi o eroare a API-ului,
        # deci cele neasteptate se considera inchise abia la a doua verificare la rand.
        for pid in list(self.known):
            if pid in current:
                self.miss.pop(pid, None)
                continue
            self.miss[pid] = self.miss.get(pid, 0) + 1
            if pid not in self.expecting and self.miss[pid] < 2:
                continue
            old = self.known.pop(pid)
            self.miss.pop(pid, None)
            kind = self.expecting.pop(pid, None)
            pnl = old.get("last_pnl", 0.0)
            if kind is None:
                kind, pnl = self.classify_vanished(old, pnl)
            self.bot_pids.discard(str(pid))
            self.counter_pids.discard(str(pid))
            self.add_realized(pnl)
            self.refresh_real()
            self.tg.send(msg.closed(old["name"], kind, pnl, self.profit_text(), self.equity() if self.cfg.get("progressive") else None,
                                    plan=old.get("tp_usd_plan") or old.get("tp_usd")))
        for pid, pos in current.items():
            self.known[pid] = {**self.known.get(pid, {}), **pos}          # pastram tinta/plasa in $ si ora deschiderii
            if not self.known[pid].get("opened_at"):
                self.known[pid]["opened_at"] = parse_time(pos.get("time")) or self.now_fn()
            self.sync_targets(self.known[pid])
        self.hold_alert()
        self.check_money(allp)
        total = sum(r["last_pnl"] for r in rows)
        c = self.cfg
        if check_basket and len(rows) >= c["basket_min_positions"] and total >= c["basket_target_usd"]:
            green = [pid for pid, p in self.known.items() if p.get("last_pnl", 0.0) > 0]       # Regula 1: nu inchid niciodata pe rosu
            if green:
                self.tg.send(msg.basket(len(green), sum(self.known[p]["last_pnl"] for p in green), len(rows) - len(green)))
                for pid in green:
                    self.close_one(pid, "BASKET")
        self.time_stop()

    def time_stop(self) -> None:
        """Limita de timp, DOAR pe plus (Regula 1): o pozitie deschisa de `max_hold_hours` ore sau mai mult si aflata pe profit (peste
        `time_stop_min_profit_usd`) se inchide, ca sa nu mai astepti ore pentru cativa dolari. Cele pe minus raman pana la tinta sau plasa."""
        limit = self.cfg.get("max_hold_hours", 0)
        if not limit:
            return
        now = self.now_fn()
        for pid, p in list(self.known.items()):
            opened = p.get("opened_at")
            if not opened or pid in self.expecting or (now - opened).total_seconds() < limit * 3600:
                continue
            if self.time_stop_tried.get(pid) and (now - self.time_stop_tried[pid]).total_seconds() < 600:
                continue                                  # o incercare esuata nu se repeta mai des de 10 minute
            if self.fresh_pnl(p) < self.cfg.get("time_stop_min_profit_usd", 0.30):
                continue
            self.time_stop_tried[pid] = now
            self.close_one(pid, "TIME")

    def refresh_blocked(self, now: datetime) -> None:
        """Semnalele care nu se puteau deschide din lipsa de bani liberi: le reevaluez cu banii de ACUM. Daca acum incap, semnalul se propune din nou
        (cu cifrele reale de acum); daca tot nu incap, retin motivul proaspat. Dupa valabilitate (signal_valid_min) dispar."""
        valid = timedelta(minutes=self.cfg["signal_valid_min"])
        for n, b in list(self.blocked.items()):
            if now - b["at"] > valid or n not in self.inst:
                self.blocked.pop(n, None)
                continue
            try:
                amount, _, _ = self.sizing(self.inst[n])
                free = self.free_margin(n)
            except Exception:  # noqa: BLE001
                continue
            if amount <= free + 0.001 and amount >= self.cfg["min_margin_usd"] - 0.001:
                self.blocked.pop(n, None)
                self.seen_bar.pop(n, None)                 # scanarea de acum il propune din nou, cu cifrele reale de acum
            else:
                b["status"] = (f"eToro cere minim {msg.usd(self.cfg['min_margin_usd'])} pe poziție și ai doar {msg.usd(free)} liber"
                               if free < self.cfg["min_margin_usd"] else msg.no_free_margin(amount, free))

    def check_money(self, allp: list[dict]) -> None:
        """Bani intrati sau iesiti din cont (depunere/retragere): totalul contului = bani liberi + marja pozitiilor; el se schimba doar cu profitul/
        pierderea inchise. O diferenta de cel putin `money_alert_usd` care se vede la DOUA verificari la rand te anunta o singura data."""
        if not self.real or self.real_balance is None:
            return
        try:
            eq = self.real_balance + sum(p["amount"] for p in allp)
            if self.acct_eq is None:
                self.acct_eq, self.realized_acc = eq, 0.0
                return
            delta = eq - self.acct_eq - self.realized_acc
            if abs(delta) < self.cfg.get("money_alert_usd", 20.0):
                self.acct_eq, self.realized_acc, self.money_cand = eq, 0.0, None
                return
            if self.money_cand and abs(self.money_cand[0] - eq) <= 2.0:          # confirmat a doua oara: nu e o citire gresita
                self.tg.send(msg.money_moved(delta, self.equity()))
                self.acct_eq, self.realized_acc, self.money_cand = eq, 0.0, None
            else:
                self.money_cand = (eq, delta)
        except Exception as e:  # noqa: BLE001 - verificarea banilor nu are voie sa opreasca botul
            print(f"[!] verificare bani: {type(e).__name__}")

    def sync_targets(self, k: dict) -> None:
        """Tinta/plasa in $ afisate = cele de PE eToro (nivelurile si pretul real de deschidere), nu planul. Daca difera mult de plan
        (de ex. pretul vazut de mine la ordin era vechi), o singura data te anunt, iar planul ramane in `tp_usd_plan`."""
        op, notional = k.get("open_rate"), (k.get("amount") or 0) * (k.get("leverage") or 0)
        if not (op and notional):
            return
        real_tp = abs(k["tp"] - op) / op * notional if k.get("tp") else None
        real_sl = abs(k["sl"] - op) / op * notional if k.get("sl") else None
        plan = k.get("tp_usd_plan") or k.get("tp_usd")
        if real_tp is None or not plan:
            return
        k.setdefault("tp_usd_plan", plan)
        if abs(real_tp - plan) <= max(0.25 * plan, 0.30):
            return                                                         # diferenta normala (spread, rotunjiri)
        k["tp_usd"] = real_tp
        if real_sl is not None:
            k["sl_usd"] = real_sl
        if not k.get("target_warned"):
            k["target_warned"] = True
            self.tg.send(msg.target_differs(k["name"], plan, real_tp, real_sl))
            self.save_state()

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
            def fresh(p, rec=rec):
                t = parse_time(p.get("time"))
                return t is None or t >= rec["at"] - timedelta(seconds=120)          # deschisa dupa trimiterea ordinului
            hit = next((p for p in allpos if p["id"] not in rec["before"] and p["name"] == rec["name"]
                        and p["side"] == rec["side"] and fresh(p)), None)
            if hit:
                self.adopt.remove(rec)
                self.bot_pids.add(str(hit["id"]))
                self.track(hit, rec.get("atr_pct"))
                self.save_state()
                self.tg.send(f"✅ Poziția pe {msg.pair(rec['name'])} a apărut în eToro (preț {hit['open_rate']}). O urmăresc acum.")
            elif (now - rec["at"]).total_seconds() > 15 * 60:
                self.adopt.remove(rec)
                self.save_state()
                self.tg.send(f"⌛ Ordinul pe {msg.pair(rec['name'])} nu a apărut în portofoliu în 15 minute. Probabil n-a fost executat; "
                             f"verifică în eToro (ordine în așteptare).")

    def classify_vanished(self, old: dict, last_pnl: float) -> tuple[str, float]:
        """O pozitie a disparut fara sa o fi inchis eu: TP, SL sau altceva? Intai intreb eToro (istoricul pozitiilor inchise: rezultat REAL
        si pretul la care s-a inchis); doar daca nu o gasesc acolo, estimez dupa pretul de acum si dupa cat se apropiase de plasa/tinta."""
        real = self.history_of(old)
        if real:
            tol = 0.0004 * (real["open_rate"] or 1.0)                              # inchiderea cade pe nivel (cu mici alunecari)
            if real["tp"] and abs(real["close_rate"] - real["tp"]) <= tol:
                return "TP", real["net"]
            if real["sl"] and abs(real["close_rate"] - real["sl"]) <= tol:
                return "SL", real["net"]
            return "OTHER", real["net"]
        tp_usd, sl_usd = old.get("tp_usd", self.cfg["tp_usd"]), old.get("sl_usd", self.cfg["sl_usd"])
        px = None
        try:
            q = self.broker.quotes([old["name"]]).get(old["name"]) if hasattr(self.broker, "quotes") else None
            px = (q["bid"] if old["side"] == 1 else q["ask"]) if q else self.broker.price(old["name"])
        except Exception:  # noqa: BLE001
            pass
        if px is not None:
            side = old["side"]
            if old.get("tp") and side * (px - old["tp"]) >= 0:
                return "TP", tp_usd
            if old.get("sl") and side * (old["sl"] - px) >= 0:
                return "SL", -sl_usd
        if last_pnl <= -0.8 * sl_usd:                                               # era aproape de plasa: cel mai probabil a prins-o
            return "SL", -sl_usd
        if last_pnl >= 0.9 * tp_usd:
            return "TP", tp_usd
        return "OTHER", self.fresh_pnl(old) if px is not None else last_pnl

    def history_of(self, old: dict) -> dict | None:
        """Rezultatul real al unei pozitii inchise, din istoricul eToro (cu 2 reincercari: istoricul poate intarzia cateva secunde)."""
        if not hasattr(self.broker, "closed_trade"):
            return None
        day = (self.now_fn() - timedelta(days=2)).strftime("%Y-%m-%d")
        for i in range(3):
            try:
                r = self.broker.closed_trade(str(old["id"]), day)
            except Exception:  # noqa: BLE001
                r = None
            if r:
                return r
            if i < 2:
                self.sleep(4)
        return None

    def hold_alert(self) -> None:
        """O pozitie care nu si-a atins ținta in ~2 ore: te intreb daca vrei sa o inchizi tu."""
        now = self.now_fn()
        for pid, p in self.known.items():
            age = (now - p["opened_at"]).total_seconds() / 60 if p.get("opened_at") else 0
            if age >= self.cfg.get("hold_alert_min", 120) and pid not in self.hold_alerted:
                self.hold_alerted.add(pid)
                self.tg.send(msg.hold_alert(p["name"], int(age // 60), p.get("last_pnl", 0.0), self.advice_for(p)),
                             [[(f"🔒 Închide {msg.pair(p['name']).split(' ')[0]}", f"close:{pid}"), ("👍 Las-o", "cancel")]])

    @staticmethod
    def context_line(s: dict) -> str:
        """Context pe scurt pentru semnal: trend pe 1h si 4h, cel mai apropiat suport si rezistenta."""
        arrow = {"sus": "↗️", "jos": "↘️", "lateral": "↔️"}
        bits = []
        if s.get("trend"):
            bits.append(f"trend 1h {arrow[s['trend']]}" + (f", 4h {arrow[s['trend4h']]}" if s.get("trend4h") else ""))
        if s.get("support"):
            bits.append(f"suport {s['support']:.5g}")
        if s.get("resistance"):
            bits.append(f"rezistență {s['resistance']:.5g}")
        return (". Context: " + " · ".join(bits)) if bits else ""

    def send_chart(self, name: str, s: dict, side: int | None = None, entry: float | None = None, tp: float | None = None,
                   sl: float | None = None, caption: str = "") -> None:
        """Graficul instrumentului pe Telegram (lumanari, medii, intrare/tinta/plasa, suport/rezistenta, RSI). Nu blocheaza nimic la eroare."""
        df = s.get("_df")
        if df is None or not hasattr(self.tg, "send_photo"):
            return
        try:
            d = digits_for(name, entry or float(df["close"].iloc[-1]))
            png = chart_mod.render(df, msg.pair(name).split(" ")[0], side, entry, tp, sl, s.get("support"), s.get("resistance"), digits=d)
            self.tg.send_photo(png, caption)
        except Exception as e:  # noqa: BLE001
            print(f"[!] grafic: {type(e).__name__}")

    def advice_for(self, pos: dict) -> dict:
        """Sfat pentru o pozitie: trendul orar si RSI-ul de acum (din Yahoo) + pretul/profitul de acum (din eToro)."""
        trend = rsi = None
        scan_res: dict = {}
        try:
            inst = self.inst[pos["name"]]
            s = signals.scan(self.fetch(inst["yahoo"], "1h", "90d"), inst["signals"], pd.Timestamp(self.now_fn()))
            trend, rsi = s.get("trend"), s.get("rsi_live")
            scan_res = s
        except Exception:  # noqa: BLE001
            scan_res = {}
        opened = pos.get("opened_at")
        age_h = (self.now_fn() - opened).total_seconds() / 3600 if opened else 0.0
        out = advisor.advise(pos["side"], pos["open_rate"], pos.get("px_now"), pos.get("tp"), pos.get("sl"),
                             pos.get("last_pnl", 0.0), age_h, trend, rsi, counter=bool(pos.get("counter")))
        out.update(trend=trend, rsi=rsi, age_h=age_h, trend4h=scan_res.get("trend4h"), scan=scan_res)
        return out

    def advice_tick(self) -> None:
        """La fiecare 15 min: daca sfatul pentru o pozitie e sa o inchizi, te anunt (cu buton), cel mult o data pe ora pe pozitie."""
        now = time.time()
        for pid, p in list(self.known.items()):
            if now - self.advice_sent.get(pid, 0) < 3600:
                continue
            adv = self.advice_for(p)
            sig = (adv["verdict"], re.sub(r"[\d.,$+%-]+", "", adv["reasons"][0]) if adv.get("reasons") else "")   # fara cifre: motivul, nu valorile
            last = self.advice_last.get(pid)
            if adv["verdict"] == "INCHIDE" and last and last[0] == sig and now - last[1] < 4 * 3600:
                continue                                  # acelasi sfat, acelasi motiv: nu-l repet (cel mult o data la 4 ore)
            if adv["verdict"] == "INCHIDE":
                self.advice_last[pid] = (sig, now)
                self.advice_sent[pid] = now
                self.tg.send(f"💡 {msg.pair(p['name'])} ({'cumpărat' if p['side'] == 1 else 'vândut'}): {msg.signed(p.get('last_pnl', 0.0))}"
                             f"{msg.advice_block(adv)}", [[(f"🔒 Închide {msg.pair(p['name']).split(' ')[0]}", f"close:{pid}"), ("👍 Las-o", "cancel")]])

    def status(self) -> None:
        self.monitor()
        self.refresh_real()
        rows = [{"name": p["name"], "side": p["side"], "pnl": p["last_pnl"], "tp_usd": p.get("tp_usd"), "advice": self.advice_for(p)} for p in self.known.values()]
        total = sum(r["pnl"] for r in rows)
        buttons = [[(f"🔒 Închide {msg.pair(r['name']).split(' ')[0]}", f"close:{p['id']}")] for r, p in zip(rows, self.known.values())]
        if len(rows) >= 2:
            buttons.append([("🔒🔒 Închide tot", "closeall")])
        warn = ""
        if self.real and (self.last_ok is None or time.time() - self.last_ok > 120):
            warn = "⚠️ Nu am putut citi soldul de la eToro în ultimele minute; cifrele de buget pot fi vechi."
        rsv = self.oil_reserve()
        if rsv and not any(p["name"] == "OIL" for p in self.known.values()):
            warn = (warn + "\n" if warn else "") + f"🛢️ Rezervat pentru petrol: {msg.usd(rsv)} (forexul nu-l folosește)"
        if rows:
            buttons.append([("📈 Grafice", "charts")])
        self.tg.send(msg.status(rows, total, self.free_margin(), self.equity(), self.profit_text(), self.autotrade, warn),
                     buttons or None)

    def status_charts(self) -> None:
        """Graficele pozitiilor deschise, la cerere (butonul «Grafice» din Status), nu la fiecare Status."""
        for p in list(self.known.values()):
            adv = self.advice_for(p)
            self.send_chart(p["name"], adv.get("scan", {}), p["side"], p.get("open_rate"), p.get("tp") or None, p.get("sl") or None,
                            f"{msg.pair(p['name'])}: {'cumpărat' if p['side'] == 1 else 'vândut'}, acum {msg.signed(p['last_pnl'])}")

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
            elif d == "charts":
                self.status_charts()
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
        elif t.startswith("/raport") or t.strip() == "raport":
            self.daily_report(final=False)
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
        self.total_pnl = st.get("total_pnl", self.realized)               # total de la început: nu se reseteaza cu /reset
        self.n_total = st.get("n_total", max(self.n_closed, sum(v.get("n", 0) for v in st.get("history", {}).values())))
        self.history = st.get("history", {})
        self.since = st.get("since") or msg.ro_dt(self.now_fn()).strftime("%Y-%m-%d")
        self.report_day = st.get("report_day", "")
        if self.real and self.cfg.get("since_real"):                      # primul meu rulaj pe contul real: totalul include deja ce era înainte
            self.since = min(self.since, self.cfg["since_real"])
        self.day, self.day_pnl = st.get("day", ""), st.get("day_pnl", 0.0)
        self.seen_bar = {k: v for k, v in st.get("seen", {}).items() if k in self.inst}      # nu re-propun aceeasi bara dupa o repornire
        for k, v in self.seen_bar.items():                                                    # nici acelasi val dupa o repornire
            if str(v).startswith("wave"):
                self.wave_n[(k, v)] = self.cfg.get("wave_max_proposals", 1)
        cont = os.getenv("CONTINUED") == "1"
        self.autotrade = bool(st.get("autotrade")) and cont                               # sesiune noua pornita de tine: autotrading oprit
        self.bot_pids = set(st.get("bot_pids", [])) if self.real else set()
        self.counter_pids = set(st.get("counter_pids", []))
        for r in st.get("adopt", []) if self.real else []:
            t = parse_time(r.get("at"))
            if t:
                self.adopt.append({**r, "before": set(r.get("before", [])), "at": t})
        self.unlocked = (bool(st.get("unlocked")) and cont) if self.real else True        # pe real: confirmare la fiecare pornire noua
        self.refresh_real()
        if self.reconcile():
            self.tg.send("🧮 Am recalculat profitul din istoricul real de la eToro (nu din estimări):\n" + self.profit_text())
        try:
            for p in self.broker.positions(fresh=True):
                if p["name"] in self.inst and (not self.real or str(p["id"]) in self.bot_pids):
                    self.track(p)
        except Exception as e:  # noqa: BLE001
            self.report_error(f"nu pot citi pozițiile de pe eToro ({type(e).__name__})")

        if os.getenv("CONTINUED") == "1":
            self.tg.send(msg.continued(hours), menu=msg.MENU)
        else:
            self.tg.send(msg.started(hours, self.equity(), c["scan_every_min"], c["basket_target_usd"], real=self.real), menu=msg.MENU)
        if self.aggr:
            self.tg.send("⚡ AGGRESSIVE_MODE activ: mai multe semnale, expunere mai mare. Siguranțele rămân (SL+TP pe fiecare ordin, oprire la pierdere zilnică).")
        if c.get("_mode_note"):
            self.tg.send(c["_mode_note"])
        if self.real and not self.unlocked:
            bal = "necunoscut (nu pot citi soldul!)" if self.real_balance is None else msg.usd(self.real_balance)
            mm = c["min_margin_usd"]
            can_n = 0 if self.real_balance is None else min(self.max_pos(), int(self.real_balance // mm))
            self.tg.send(f"🔴 CONT REAL. Sold disponibil: {bal}.\neToro cere minim {msg.usd(mm)} pe poziție. Deschid acum maxim {can_n} poziții "
                         f"(maxim {self.max_pos()} odată cât bugetul e {'sub' if self.equity() < c['small_account_usd'] else 'peste'} {msg.usd(c['small_account_usd'])}).\n"
                         f"Nu deschid nimic până nu confirmi că vrei să tranzacționez cu bani adevărați.",
                         [[("✅ Confirm: cont real", "realok"), ("❌ Nu, oprește", "stopnow")]])
        self.save_state()
        if self.known:
            self.tg.send(f"👀 Am găsit {len(self.known)} poziții deschise {'de mine' if self.real else 'pe eToro'}; le urmăresc și pe ele.")
            self.monitor()
        this_run, remaining = plan_session(hours)
        start = time.time()
        end = start + this_run * 3600
        t_scan = t_mon = t_upd = 0.0
        t_hb = time.time()
        slot_min = int(c.get("scan_slot_min", 15))
        last_sent = {"t": 0.0, "total": 0.0}
        warned = False
        sig_mod.signal(sig_mod.SIGTERM, lambda *a: setattr(self, "stop_reason", "GitHub a oprit sesiunea"))
        sig_mod.signal(sig_mod.SIGINT, lambda *a: setattr(self, "stop_reason", "GitHub a oprit sesiunea"))
        while not self.stop_reason:
            try:
                for ev in self.tg.poll(timeout=15):
                    self.handle(ev)
                now = time.time()
                utc = self.now_fn()
                slot = (utc.date(), utc.hour, utc.minute // slot_min)
                if slot != self.last_slot and (self.last_slot is None or utc.second >= 20):   # la :00/:15/:30/:45 (+20s), cand apare ora noua
                    self.last_slot = slot
                    self.scan()
                if now - t_mon >= c["pl_check_every_sec"]:
                    t_mon = now
                    self.monitor()
                if now - t_upd >= c["scan_every_min"] * 60 and self.known:
                    t_upd = now
                    total = sum(p["last_pnl"] for p in self.known.values())
                    if now - last_sent["t"] >= c.get("update_every_min", 60) * 60 or abs(total - last_sent["total"]) >= c.get("update_delta_usd", 1.0):
                        last_sent.update(t=now, total=total)
                        self.tg.send(msg.update([{"name": p["name"], "pnl": p["last_pnl"], "tp_usd": p.get("tp_usd")} for p in self.known.values()], total), silent=True)
                    self.advice_tick()
                if now - t_hb >= 6 * 3600 and not self.market_open(self.now_fn()):
                    t_hb = now
                    n = self.now_fn()
                    self.tg.send(msg.heartbeat(msg.ro_hm(n), self.scans, self.last_scan, len(self.known), self.market_open(n)), silent=True)
                if self.unlocked and self.report_due(utc):
                    self.daily_report()
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
            (HERE / "handover.txt").write_text("0" if hours <= 0 else f"{remaining:g}", encoding="utf-8")          # pasul urmator din workflow porneste sesiunea noua
            self.tg.send(msg.handover(remaining, len(self.known)), silent=True)
        else:
            self.tg.send(msg.stopped(self.stop_reason, len(self.known)))


def main() -> int:
    from broker import EToroBroker
    from etoro import EToroDemo
    from telegram_bot import Telegram
    import modes
    hours = float(os.getenv("SESSION_HOURS", "5"))
    real = os.getenv("TRADING_MODE") == "real"
    cfg = modes.apply(json.loads((HERE / "config.json").read_text(encoding="utf-8")), real)
    tg, api = Telegram(), EToroDemo(real=real)
    journal = channel.from_env(HERE / "journal.enc")          # jurnal criptat al mesajelor (doar cu HELGA_KEY); fara cheie: oprit
    if journal:
        import telegram_bot
        telegram_bot.HOOKS.append(journal.on_telegram)
        journal.add("start", f"sesiune noua, mod {'real' if real else 'demo'}, ore {hours:g}")
    ids = {}
    for inst in cfg["instruments"]:
        ids[inst["name"]] = api.find_instrument_id(inst["etoro"])
    Assistant(cfg, tg, EToroBroker(api, ids), real=real).run(hours)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
