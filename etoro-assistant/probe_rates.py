#!/usr/bin/env python3
"""Sondare date de piata (fara cont): cotatii live bid/ask si cursul de conversie in USD pentru fiecare instrument."""
import json
from pathlib import Path

from etoro import EToroDemo

api = EToroDemo()
cfg = json.loads((Path(__file__).parent / "config.json").read_text())
ids = {i["name"]: api.find_instrument_id(i["etoro"]) for i in cfg["instruments"]}
d = api._req("GET", "/api/v1/market-data/instruments/rates", params={"instrumentIds": ",".join(str(v) for v in ids.values())})
items = d.get("rates") if isinstance(d, dict) else d
by = {int(x["instrumentID"]): x for x in items}
for n, i in ids.items():
    x = by.get(i)
    if x:
        print(f"{n:8s} bid {x['bid']} ask {x['ask']} convBid {x.get('conversionRateBid')} convAsk {x.get('conversionRateAsk')} date {x.get('date')}")
