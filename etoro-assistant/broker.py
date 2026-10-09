"""eToro DEMO: pozitii, ordine cu SL/TP, inchideri, pret."""
from __future__ import annotations

import math
import time

from etoro import EToroDemo, EToroError


class EToroBroker:
    def __init__(self, api: EToroDemo, ids: dict[str, int]):
        self.api, self.ids = api, ids
        self.rev = {v: k for k, v in ids.items()}
        self.last: dict = {}

    def price(self, name: str) -> float:
        return self.api.last_price(self.ids[name])

    def positions(self) -> list[dict]:
        out = []
        for p in self.api.positions():
            iid = int(p.get("instrumentID") or p.get("InstrumentID") or p.get("instrumentId") or 0)
            pid = p.get("positionID") or p.get("PositionID") or p.get("positionId")
            if not pid or iid not in self.rev:
                continue
            buy = p.get("isBuy", p.get("IsBuy"))
            out.append({"id": str(pid), "name": self.rev[iid], "side": 1 if buy else -1,
                        "open_rate": float(p.get("openRate") or p.get("OpenRate") or 0),
                        "units": float(p.get("units") or p.get("Units") or 0),
                        "amount": float(p.get("amount") or p.get("Amount") or 0),
                        "leverage": int(p.get("leverage") or p.get("Leverage") or 1),
                        "sl": float(p.get("stopLossRate") or 0), "tp": float(p.get("takeProfitRate") or 0),
                        "time": p.get("openDateTime", "")})
        return out

    def open(self, name: str, side: int, amount: float, lev: int, sl: float, tp: float) -> str:
        """Deschide pe DEMO. Daca levierul > 20 e refuzat, reincearca cu 20 (aceeasi expunere)."""
        try:
            pid = self._open(name, side, amount, lev, sl, tp)
            self.last = {"amount": amount, "leverage": lev}
            return pid
        except EToroError:
            if lev <= 20:
                raise
            amount2 = math.ceil(amount * lev / 20 * 100) / 100
            pid = self._open(name, side, amount2, 20, sl, tp)
            self.last = {"amount": amount2, "leverage": 20}
            return pid

    def _open(self, name, side, amount, lev, sl, tp) -> str:
        before = {p["id"] for p in self.positions()}
        r = self.api.open_market(self.ids[name], side == 1, amount, lev, sl, tp)
        oid = r.get("orderId") if isinstance(r, dict) else None
        for _ in range(8):
            time.sleep(3)
            if oid:
                st = self.api.order_status(oid)
                if st.get("statusID") == 4:
                    raise EToroError(f"Ordin respins: {st.get('errorMessage')}")
            new = [p for p in self.positions() if p["id"] not in before and p["name"] == name]
            if new:
                return new[0]["id"]
        raise EToroError("Ordinul a fost trimis, dar pozitia nu apare in portofoliu (verifica pe eToro).")

    def close(self, pid: str, name: str) -> None:
        self.api.close_position(int(pid), self.ids[name])
