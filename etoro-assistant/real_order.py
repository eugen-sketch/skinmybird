#!/usr/bin/env python3
"""Diagnostic cont REAL, doar citire: starea unui ordin (SCRIPT_ARG = id-ul ordinului) si ce pozitii exista acum. Rezultatul merge doar pe Telegram."""
import json
import os

from etoro import EToroDemo, EToroError
from telegram_bot import Telegram

tg = Telegram()
try:
    api = EToroDemo(real=True)
    oid = os.getenv("SCRIPT_ARG", "").strip()
    out = []
    if oid:
        try:
            out.append("Ordin " + oid + ": " + json.dumps(api.order_status(int(oid)), ensure_ascii=False)[:900])
        except EToroError as e:
            out.append(f"Ordin {oid}: nu pot citi starea ({str(e)[:200]})")
    pos = api.positions(fresh=True)
    out.append(f"Poziții acum: {len(pos)}")
    for x in pos:
        out.append("• " + ", ".join(f"{k}={x.get(k)}" for k in ("positionID", "instrumentID", "isBuy", "amount", "leverage", "openDateTime") if k in x))
    out.append(f"credit={api.credit(fresh=True)}")
    tg.send("🔎 Diagnostic ordin (doar citire):\n" + "\n".join(out))
    print("trimis pe Telegram")
except EToroError as e:
    tg.send(f"⚠️ Diagnostic eșuat: {str(e)[:300]}")
    print("eroare")
