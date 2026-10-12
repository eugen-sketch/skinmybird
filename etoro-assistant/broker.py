"""eToro DEMO: pozitii, ordine cu SL/TP, inchideri, pret."""
from __future__ import annotations

import math
import time

from etoro import EToroDemo, EToroError


class OrderUnconfirmed(EToroError):
    """Ordin trimis (eToro l-a primit), dar pozitia nu a aparut inca in portofoliu: poate fi deschis sau in asteptare."""

    def __init__(self, msg: str, before: set, response):
        super().__init__(msg)
        self.before, self.response = before, response


class EToroBroker:
    def __init__(self, api: EToroDemo, ids: dict[str, int]):
        self.api, self.ids = api, ids
        self.rev = {v: k for k, v in ids.items()}
        self.last: dict = {}

    def credit(self) -> float | None:
        return self.api.credit()

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

    @staticmethod
    def _order_id(r) -> str | None:
        """Id-ul ordinului din raspuns (cheia difera intre versiunile API): cautam in raspuns si in sub-obiecte."""
        if isinstance(r, dict):
            for k in ("orderId", "OrderId", "orderID", "OrderID", "id"):
                if r.get(k):
                    return str(r[k])
            for v in r.values():
                if isinstance(v, dict):
                    o = EToroBroker._order_id(v)
                    if o:
                        return o
        return None

    def open(self, name: str, side: int, amount: float, lev: int, sl: float, tp: float) -> str:
        """Deschide pozitia. Daca levierul > 20 e REFUZAT CURAT, reincearca cu 20 (aceeasi expunere).
        Dupa un ordin trimis dar neconfirmat NU se reincearca niciodata (risc de ordin dublu)."""
        try:
            pid = self._open(name, side, amount, lev, sl, tp)
            self.last = {"amount": amount, "leverage": lev}
            return pid
        except OrderUnconfirmed:
            raise
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
        oid = self._order_id(r)
        for _ in range(20):                                   # pana la ~60 s
            time.sleep(3)
            if oid:
                try:
                    st = self.api.order_status(oid)
                    if st.get("statusID") == 4:
                        raise EToroError(f"Ordin respins: {st.get('errorMessage')}")
                except EToroError as e:
                    if "respins" in str(e):
                        raise
            new = [p for p in self.positions() if p["id"] not in before and p["name"] == name and p["side"] == side]
            if new:
                return new[0]["id"]
        raise OrderUnconfirmed("Ordinul a fost trimis, dar nu l-am văzut încă în portofoliu", before, r)

    def close(self, pid: str, name: str) -> None:
        self.api.close_position(int(pid), self.ids[name])
