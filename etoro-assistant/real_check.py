#!/usr/bin/env python3
"""Verifica doar CITIND (nicio tranzactie) ca cheile contului REAL merg: sold si nr. de pozitii. Detaliile merg pe Telegram,
in logul public apare doar un rezumat fara sume."""
import json
from pathlib import Path

from etoro import EToroDemo, EToroError
from telegram_bot import Telegram

tg = Telegram()
try:
    api = EToroDemo(real=True)
    credit = api.credit()
    n = len(api.positions())
    cfg = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
    ids = {i["name"]: api.find_instrument_id(i["etoro"]) for i in cfg["instruments"]}
    px = api.last_price(ids["EURUSD"])
    tg.send(f"🔴 Verificare cont REAL (doar citire, nimic tranzacționat):\n• sold disponibil: "
            f"{'NEGĂSIT în răspuns' if credit is None else f'${credit:,.2f}'}\n• poziții deschise pe cont: {n}\n"
            f"• instrumente găsite: {len(ids)}/{len(cfg['instruments'])}\n• preț EUR/USD: {px}")
    print("Verificare real: ok" if credit is not None else "Verificare real: sold negasit")
except EToroError as e:
    tg.send(f"⚠️ Verificare cont REAL eșuată: {str(e)[:300]}")
    print("Verificare real: eroare")
