#!/usr/bin/env python3
"""Verifica conexiunea la eToro DEMO: cheile, ID-urile instrumentelor, portofoliul.
Cu TEST_TRADE=1 deschide si inchide o pozitie minima pe DEMO ca sa confirme ca ordinele functioneaza."""
import os
import sys
import time

import notify
from etoro import EToroDemo, EToroError

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "GOLD"]


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
    try:
        pos = api.positions()
        print(f"Pozitii deschise pe demo: {len(pos)}")
    except EToroError as e:
        print(f"[!] portofoliu: {e}")
        ok = False
    if os.getenv("TEST_TRADE") == "1" and "EURUSD" in ids:
        try:
            r = api.open_market(ids["EURUSD"], True, 50, 1, stop_loss=0.5, take_profit=5.0)
            print("Ordin test deschis:", r)
            time.sleep(5)
            mine = [p for p in api.positions() if int(p.get("instrumentID") or p.get("InstrumentID") or 0) == ids["EURUSD"]]
            for p in mine:
                pid = p.get("positionID") or p.get("PositionID")
                print("Inchid", pid, api.close_position(int(pid), ids["EURUSD"]))
        except EToroError as e:
            print(f"[!] ordin test: {e}")
            ok = False
    notify.send(("✅ Conexiune eToro DEMO OK. " if ok else "⚠️ eToro DEMO: probleme, vezi logul. ") + f"IDs: {ids}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
