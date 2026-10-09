#!/usr/bin/env python3
"""Trimite doua mesaje de test pe Telegram: unul cu sunet, unul silentios (ca sa compari)."""
import time

from telegram_bot import Telegram

tg = Telegram()
tg.send("🔔 Test cu sunet: dacă auzi telefonul sunând, notificările merg.")
time.sleep(20)
tg.send("🔕 Test silențios (așa arată mesajul orar): acesta nu trebuie să sune.", silent=True)
print("Trimis")
