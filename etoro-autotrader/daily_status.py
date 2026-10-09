#!/usr/bin/env python3
"""Arata semnalele zilnice curente pe indici (fara ordine)."""
import json
from datetime import datetime, timezone
from pathlib import Path

import ta
import trader

cfg = json.loads((Path(__file__).parent / "config.json").read_text())
now = datetime.now(timezone.utc)
for inst in cfg["instruments"]:
    df = ta.fetch_ohlc(inst["yahoo"], "1d", "2y")
    s = trader.daily_signal(df, cfg["params"], now)
    print(f"{inst['name']}: ultima bara {s['bar'][:10]} pret {s['price']:.1f} RSI2 {s['rsi2']:.1f} -> {'CUMPARA' if s['side'] == 1 else 'nimic'} (iesire daca RSI2>{cfg['params']['rsi2_exit']}: {s['exit_long']})")
