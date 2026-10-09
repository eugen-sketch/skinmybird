#!/usr/bin/env python3
"""Schimba numele afisat al botului Telegram (username-ul @... ramane). Nume in SCRIPT_ARG."""
import os
import sys

import requests

name = os.getenv("SCRIPT_ARG", "").strip()
token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not name or not token:
    sys.exit("Lipseste numele (SCRIPT_ARG) sau tokenul")
r = requests.post(f"https://api.telegram.org/bot{token}/setMyName", json={"name": name[:64]}, timeout=30)
print("setMyName:", r.status_code, r.json().get("ok"), r.json().get("description", ""))
r2 = requests.get(f"https://api.telegram.org/bot{token}/getMyName", timeout=30)
print("Nume acum:", r2.json().get("result"))
if r.status_code != 200 or not r.json().get("ok"):
    sys.exit(1)
requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
              json={"chat_id": os.getenv("TELEGRAM_CHAT_ID"), "text": f"✅ Gata, de acum mă numesc {name}."}, timeout=30)
