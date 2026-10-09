#!/usr/bin/env python3
"""Verifica scanarea pe date reale: timp, prospetimea datelor, valorile fata de praguri. Raportul merge pe Telegram."""
import json
import time
from pathlib import Path

import messages as msg
import signals
import ta
from telegram_bot import Telegram

cfg = json.loads((Path(__file__).parent / "config.json").read_text())
rows, t0 = [], time.time()
for inst in cfg["instruments"]:
    t1 = time.time()
    df = ta.fetch_ohlc(inst["yahoo"], "1h", "30d")
    s = signals.scan(df, inst["signals"])
    thr = next((int(n[7:]) for n in inst["signals"] if n.startswith("rsi_rev")), 25)
    rows.append({"name": inst["name"], "rsi": s["rsi"], "thr": thr, "asia": s["asia_pos"], "bar": msg.hour_range(s["bar"]),
                 "note": f"{s['n_bars']} bare, {time.time() - t1:.1f}s"})
total = time.time() - t0
text = msg.scan_report(rows) + f"\n\n⏱️ Timp total real: {total:.1f} secunde pentru {len(rows)} instrumente (descarc ~30 de zile de date pentru fiecare)."
Telegram().send(text)
print(f"Diagnostic trimis pe Telegram ({total:.1f}s).")
