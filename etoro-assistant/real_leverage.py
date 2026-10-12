#!/usr/bin/env python3
"""Citire pe contul REAL: cu ce levier sunt deschise pozitiile. Detaliile merg pe Telegram; in logul public apar doar valorile levierului."""
import json
from pathlib import Path

from etoro import EToroDemo
from telegram_bot import Telegram

api = EToroDemo(real=True)
cfg = json.loads((Path(__file__).parent / "config.json").read_text())
ids = {api.find_instrument_id(i["etoro"]): i["name"] for i in cfg["instruments"]}
pos = api.positions(fresh=True)
lines, levs = [], []
for p in pos:
    iid = p.get("instrumentID")
    lev = p.get("leverage")
    levs.append(lev)
    lines.append(f"• {ids.get(iid, f'instrument {iid}')} ({'cumpărat' if p.get('isBuy') else 'vândut'}): levier {lev}, marjă ${p.get('amount')}, "
                 f"expunere ≈ ${float(p.get('amount') or 0) * float(lev or 1):,.0f}")
Telegram().send("⚙️ Levierul pozițiilor deschise pe contul REAL:\n" + ("\n".join(lines) if lines else "nicio poziție"))
print("leveraje:", sorted(levs))
