"""Notificari Telegram (optional) + consola."""
import os

import requests


def send(text: str) -> None:
    print(text, "\n" + "-" * 50)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    for i in range(0, len(text), 3900):
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text[i:i + 3900]}, timeout=15).raise_for_status()
        except requests.RequestException as e:
            print(f"[!] Telegram a esuat: {e}")
