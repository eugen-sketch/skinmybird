#!/usr/bin/env python3
"""Diagnostic cont REAL, doar citire: cauta ruta corecta pentru starea unui ordin (SCRIPT_ARG = id ordin). In log: doar coduri HTTP; continutul merge pe Telegram."""
import json
import os

from etoro import EToroDemo, EToroError
from telegram_bot import Telegram

tg = Telegram()
api = EToroDemo(real=True)
oid = os.getenv("SCRIPT_ARG", "").strip()
paths = ["/api/v1/trading/info/real/orders/{}", "/api/v1/trading/execution/market-open-orders/{}", "/api/v1/trading/execution/orders/{}",
         "/api/v1/trading/info/orders/{}", "/api/v1/trading/execution/real/orders/{}", "/api/v1/trading/info/real/order/{}"]
out = []
for tpl in paths:
    path = tpl.format(oid)
    try:
        r = api._req("GET", path, trading=True)
        txt = json.dumps(r, ensure_ascii=False)[:700]
        print("200", tpl)
        out.append(f"✅ {path}: {txt}")
    except EToroError as e:
        code = getattr(e, "status", "?")
        print(code, tpl)
        out.append(f"✖ {path}: {code}")
tg.send("🔎 Rute stare ordin (doar citire):\n" + "\n".join(out))
