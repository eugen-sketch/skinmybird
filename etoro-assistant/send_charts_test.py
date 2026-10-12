#!/usr/bin/env python3
"""Trimite pe Telegram graficele reale (GBP/USD, USD/CAD, aur) cu trend 1h/4h, suport si rezistenta, ca sa vezi cum arata."""
import signals
import ta
from assistant import Assistant
from telegram_bot import Telegram
import chart
import messages as msg

tg = Telegram()
for name, ysym in (("GBPUSD", "GBPUSD=X"), ("USDCAD", "USDCAD=X"), ("GOLD", "GC=F")):
    s = signals.scan(ta.fetch_ohlc(ysym, "1h", "90d"), ["rsi_rev25"])
    df = s["_df"]
    px = float(df["close"].iloc[-1])
    d = 2 if name == "GOLD" else 5
    png = chart.render(df, msg.pair(name).split(" ")[0], None, None, None, None, s.get("support"), s.get("resistance"), digits=d)
    tg.send_photo(png, f"{msg.pair(name)}{Assistant.context_line(s)}")
    print(name, "grafic trimis", len(png))
