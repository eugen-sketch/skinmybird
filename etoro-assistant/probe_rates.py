#!/usr/bin/env python3
"""Sondare date de piata (fara cont): ce da eToro pentru cotatii live? Doar numele campurilor."""
from etoro import EToroDemo, EToroError

api = EToroDemo()
for path in ("/api/v1/market-data/instruments/rates", "/api/v1/market-data/instruments/1/rates", "/api/v1/market-data/rates"):
    try:
        d = api._req("GET", path, params={"instrumentIds": "1,3"})
        items = d.get("rates") if isinstance(d, dict) else d
        first = items[0] if isinstance(items, list) and items else d
        print(path, "OK ->", sorted(first.keys()) if isinstance(first, dict) else type(first).__name__)
    except EToroError as e:
        print(path, "ERR", str(e)[:120])
