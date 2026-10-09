#!/usr/bin/env python3
"""Diagnostic DEMO (fara ordine noi): portofoliu brut + cautare stare ordin."""
import json
import os
import sys

from etoro import EToroDemo, EToroError

ORDER_ID = os.getenv("ORDER_ID", "387606844")


def main() -> int:
    api = EToroDemo()
    try:
        p = api.portfolio()
        cp = p.get("clientPortfolio", p)
        print("POZITII:", json.dumps(cp.get("positions"), indent=1)[:3000])
        print("ordersForOpen:", json.dumps(cp.get("ordersForOpen"))[:1000], "| credit:", cp.get("credit"))
    except EToroError as e:
        print("[!] portofoliu:", e)
    for path in (f"/api/v1/trading/info/demo/orders/{ORDER_ID}",
                 f"/api/v1/trading/info/demo/order/{ORDER_ID}",
                 f"/api/v2/trading/info/demo/orders/{ORDER_ID}",
                 "/api/v1/trading/info/demo/orders"):
        try:
            api._req("GET", path, trading=True)
        except EToroError as e:
            print("[!]", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
