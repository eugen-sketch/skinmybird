#!/usr/bin/env python3
"""Pune logo-ul ca poza de profil a botului Telegram: imaginea fixa din assets/logo.jpg."""
import json
import os
import sys
from pathlib import Path

import requests

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
chat = os.getenv("TELEGRAM_CHAT_ID", "")
assets = Path(__file__).parent / "assets"
if not token:
    sys.exit("Lipseste tokenul")


def call(photo: dict, fname: str, kind: str):
    with open(assets / fname, "rb") as fh:
        r = requests.post(f"https://api.telegram.org/bot{token}/setMyProfilePhoto",
                          data={"photo": json.dumps(photo)}, files={kind: fh}, timeout=120)
    try:
        body = r.json()
    except ValueError:
        body = {"ok": False, "description": r.text[:200]}
    print(f"{fname}: {r.status_code} ok={body.get('ok')} {body.get('description', '')}")
    return bool(body.get("ok"))


ok = call({"type": "static", "photo": "attach://img"}, "logo.jpg", "img")
how = "fixă"
if chat:
    text = f"✅ Am pus logo-ul tău ca poză de profil ({how})." if ok else \
        "⚠️ Telegram n-a acceptat poza prin API. O poți pune din @BotFather: /mybots → botul tău → Edit Bot → Edit Botpic."
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text}, timeout=30)
sys.exit(0 if ok else 1)
