#!/usr/bin/env python3
"""Compara pozitiile deschise pe eToro DEMO cu regulile din config.json. Detaliile merg pe Telegram, in log doar verdictul."""
import json
import math
import signal
from pathlib import Path

import messages as msg
from broker import EToroBroker
from etoro import EToroDemo
from telegram_bot import Telegram

signal.alarm(150)          # nu lasam scriptul sa atarne
cfg = json.loads((Path(__file__).parent / "config.json").read_text())
api = EToroDemo()
ids = {i["name"]: api.find_instrument_id(i["etoro"]) for i in cfg["instruments"]}
br = EToroBroker(api, ids)
inst = {i["name"]: i for i in cfg["instruments"]}
pos = br.positions()
lines, verdict = [], []
for p in pos:
    i = inst[p["name"]]
    lev_max = min(i["lev_cap"], cfg["max_leverage"])
    notional = p["amount"] * p["leverage"]
    tp_usd = abs(p["tp"] - p["open_rate"]) / p["open_rate"] * notional if p["tp"] else 0
    sl_usd = abs(p["sl"] - p["open_rate"]) / p["open_rate"] * notional if p["sl"] else 0
    margin_expected = math.floor(cfg["budget_usd"] / cfg["max_positions"] * 100) / 100
    checks = {
        "levier maxim": p["leverage"] == lev_max,
        "expunere >= 1000$": notional >= cfg["min_notional"],
        "marja ~ 46,66$": abs(p["amount"] - margin_expected) < 1.0 or lev_max < 30,
        "TP ~ 2,75$": abs(tp_usd - cfg["tp_usd"]) < 0.3,
        "SL ~ 6$": abs(sl_usd - cfg["sl_usd"]) < 0.6,
    }
    ok = all(checks.values())
    verdict.append(f"{p['name']} {'OK' if ok else 'ATENTIE'}")
    lines.append(f"{'🟢 cumpărat' if p['side'] == 1 else '🔴 vândut'} {msg.pair(p['name'])}\n"
                 f"  • levier {p['leverage']} (maxim permis {lev_max}) {'✅' if checks['levier maxim'] else '❌'}\n"
                 f"  • marjă {msg.usd(p['amount'])}, expunere {msg.usd(notional)} {'✅' if checks['expunere >= 1000$'] else '❌'}\n"
                 f"  • țintă (TP) ≈ {msg.usd(tp_usd)} (regula {msg.usd(cfg['tp_usd'])}) {'✅' if checks['TP ~ 2,75$'] else '❌'}\n"
                 f"  • plasă (SL) ≈ {msg.usd(sl_usd)} (regula {msg.usd(cfg['sl_usd'])}) {'✅' if checks['SL ~ 6$'] else '❌'}")
text = ("🔎 Verificare poziții deschise pe eToro demo:\n\n" + "\n\n".join(lines)) if pos else "📭 Nu văd nicio poziție deschisă pe eToro demo."
Telegram().send(text)
print("Verificare facuta, detaliile sunt pe Telegram.")        # nimic despre pozitii in logul public
