#!/usr/bin/env python3
"""Diagnostic pe contul REAL, doar citire: arata STRUCTURA raspunsului portofoliului (numele campurilor, nu valorile).
Detaliile (pozitii, sume) merg doar pe Telegram."""
import json
from pathlib import Path

from etoro import EToroDemo, EToroError
from telegram_bot import Telegram

tg = Telegram()
try:
    api = EToroDemo(real=True)
    p = api.portfolio()
    cp = p.get("clientPortfolio", p) if isinstance(p, dict) else {}
    print("chei portofoliu:", sorted(cp.keys()) if isinstance(cp, dict) else type(cp).__name__)
    pos = api.positions()
    print("nr pozitii:", len(pos))
    if pos:
        print("campuri pozitie:", sorted(pos[0].keys()))
    for k in ("orders", "ordersForOpen", "pendingOrders", "ordersForClose", "entryOrders"):
        v = cp.get(k) if isinstance(cp, dict) else None
        if v is not None:
            print(f"{k}:", len(v), "campuri:", sorted(v[0].keys()) if v and isinstance(v[0], dict) else "-")
    cfg = json.loads((Path(__file__).parent / "config.json").read_text())
    nzd = api.find_instrument_id("NZDUSD")
    lines = []
    for x in pos:
        iid = x.get("instrumentID") or x.get("InstrumentID")
        lines.append(f"• instrument {iid}{' (NZDUSD)' if iid == nzd else ''}: " + ", ".join(f"{k}={x.get(k)}" for k in
                     ("positionID", "isBuy", "openRate", "units", "amount", "leverage", "stopLossRate", "takeProfitRate", "openDateTime") if k in x))
    tg.send("🔎 Pozițiile de pe contul REAL acum (doar citire):\n" + ("\n".join(lines) if lines else "niciuna"))
    print("trimis pe Telegram")
except EToroError as e:
    tg.send(f"⚠️ Inspecție cont REAL eșuată: {str(e)[:300]}")
    print("eroare")
