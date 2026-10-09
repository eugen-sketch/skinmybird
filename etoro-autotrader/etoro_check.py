#!/usr/bin/env python3
"""Verifica conexiunea la eToro DEMO: cheile, ID-urile instrumentelor, portofoliul.
Cu TEST_TRADE=1 deschide si inchide o pozitie minima pe DEMO ca sa confirme ca ordinele functioneaza."""
import os
import sys
import time

import notify
from etoro import EToroDemo, EToroError

SYMBOLS = os.getenv("CHECK_SYMBOLS", "OIL,GOLD,EURUSD").split(",")


def main() -> int:
    try:
        api = EToroDemo()
    except EToroError as e:
        notify.send(f"❌ eToro: {e}")
        return 1
    ok = True
    ids = {}
    for s in SYMBOLS:
        try:
            ids[s] = api.find_instrument_id(s)
        except EToroError as e:
            print(f"[!] {s}: {e}")
            ok = False
    print("INSTRUMENT IDs:", ids)
    for q in os.getenv("CHECK_SEARCH", "OIL,GOLD").split(","):   # descoperire: numele exacte pe eToro
        try:
            names = [(i["internalSymbolFull"], i["instrumentId"]) for i in api.search_symbols(q)]
            print(f"CANDIDATI {q}: {names[:25]}")
        except EToroError as e:
            print(f"[!] cautare {q}: {e}")
    if "EURUSD" in ids:
        try:
            print("Pret EURUSD pe eToro:", api.last_price(ids["EURUSD"]))
        except Exception as e:  # noqa: BLE001
            print(f"[!] pret: {e}")
    try:
        pos = api.positions()
        print(f"Pozitii deschise pe demo: {len(pos)}")
    except EToroError as e:
        print(f"[!] portofoliu: {e}")
        ok = False
    if os.getenv("TEST_TRADE") == "1" and "EURUSD" in ids:
        try:
            px = api.last_price(ids["EURUSD"])
            r = api.open_market(ids["EURUSD"], True, 52, 20, stop_loss=round(px * 0.99, 5), take_profit=round(px * 1.02, 5))
            oid = r.get("orderId")
            pid = None
            for _ in range(10):
                time.sleep(3)
                print("Stare ordin:", api.order_status(oid))
                mine = [p for p in api.positions() if int(p.get("instrumentID") or p.get("InstrumentID") or 0) == ids["EURUSD"]]
                if mine:
                    pid = mine[0].get("positionID") or mine[0].get("PositionID")
                    break
            print("Pozitie deschisa, id:", pid)
            if pid:
                print("Inchid:", api.close_position(int(pid), ids["EURUSD"]))
                time.sleep(6)
                print("Pozitii ramase:", len(api.positions()))
        except EToroError as e:
            print(f"[!] ordin test: {e}")
            ok = False
    notify.send(("✅ Conexiune eToro DEMO OK. " if ok else "⚠️ eToro DEMO: probleme, vezi logul. ") + f"IDs: {ids}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
