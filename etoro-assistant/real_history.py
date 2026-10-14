#!/usr/bin/env python3
"""Sonda cont REAL, doar citire: cauta ruta istoricului pozitiilor inchise. In log: doar coduri HTTP si NUMELE campurilor (nu valorile)."""
import json

from etoro import EToroDemo, EToroError, EToroHTTPError


def shape(x, depth=0):
    if isinstance(x, dict):
        return {k: (shape(v, depth + 1) if depth < 1 else type(v).__name__) for k, v in list(x.items())[:40]}
    if isinstance(x, list):
        return [shape(x[0], depth + 1)] if x else []
    return type(x).__name__


api = EToroDemo(real=True)
paths = [
    ("/api/v1/trading/info/trade/history", {"minDate": "2026-10-12", "page": 1, "pageSize": 5}),
    ("/api/v1/trading/info/real/trade/history", {"minDate": "2026-10-12", "page": 1, "pageSize": 5}),
    ("/api/v1/trading/info/real/history", {"minDate": "2026-10-12"}),
    ("/api/v1/trading/info/history", {"minDate": "2026-10-12"}),
    ("/api/v1/trading/info/real/trade/history", {"minDate": "2026-10-12"}),
    ("/api/v1/trading/info/trade/history", {"minDate": "2026-10-12"}),
]
for path, params in paths:
    try:
        r = api._req("GET", path, params=params, trading=True)
        print("200", path, json.dumps(shape(r))[:900])
    except EToroHTTPError as e:
        print(e.status, path)
    except EToroError as e:
        print("ERR", path, type(e).__name__)
