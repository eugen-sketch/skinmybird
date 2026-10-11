#!/usr/bin/env python3
"""Pune meniul actual (cu butonul 🤖 Autotrading) in Telegram, fara sa pornesc asistentul."""
import messages as msg
from telegram_bot import Telegram

Telegram().send("🆕 Meniul s-a actualizat: acum ai și butonul 🤖 Autotrading. Asistentul e oprit; scrie «pornește» ca să-l pornești.", menu=msg.MENU)
print("Meniu trimis")
