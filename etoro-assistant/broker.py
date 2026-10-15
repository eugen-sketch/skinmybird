"""eToro (demo sau real): pozitii, ordine cu SL/TP, inchideri, cotatii."""
from __future__ import annotations

import math
import time

from datetime import datetime, timedelta, timezone

from etoro import EToroDemo, EToroError, EToroHTTPError, EToroNetworkError

MAX_QUOTE_AGE_S = 120        # cotatiile eToro mai vechi de 2 minute nu se folosesc (pe 15.10 veneau cu ~40 min intarziere)


def parse_time(txt) -> datetime | None:
    """Ora de la eToro (ISO, uneori cu fractii de secunda si 'Z'); None daca nu o pot citi."""
    try:
        s = str(txt).replace("Z", "+00:00")
        t = datetime.fromisoformat(s.split(".")[0] + ("+00:00" if "+" not in s else ""))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class OrderRejected(EToroError):
    """Ordin respins CLAR de eToro (nu s-a deschis nimic)."""


class OrderUnconfirmed(EToroError):
    """Ordin trimis (sau cu rezultat neclar), dar pozitia nu a aparut inca in portofoliu: poate fi deschis sau in asteptare."""

    def __init__(self, msg: str, before: set, response, sent_at: datetime | None = None):
        super().__init__(msg)
        self.before, self.response, self.sent_at = before, response, sent_at or datetime.now(timezone.utc)


class EToroBroker:
    def __init__(self, api: EToroDemo, ids: dict[str, int]):
        self.api, self.ids = api, ids
        self.rev = {v: k for k, v in ids.items()}
        self.last: dict = {}

    def credit(self) -> float | None:
        return self.api.credit()

    def price(self, name: str) -> float:
        """Pret orientativ (ultima lumanare de 1 ora); pentru profit/pierdere si ordine folosim quotes() (bid/ask live)."""
        return self.api.last_price(self.ids[name])

    def quotes(self, names: list[str]) -> dict[str, dict]:
        """Cotatii live pentru mai multe instrumente intr-un singur apel: {nume: {bid, ask, conv_bid, conv_ask}}."""
        by = self.api.rates([self.ids[n] for n in names])
        out = {}
        now = datetime.now(timezone.utc)
        for n in names:
            x = by.get(self.ids[n])
            if x and x.get("bid") and x.get("ask"):
                t = parse_time(x.get("date"))
                if t is not None and (now - t).total_seconds() > MAX_QUOTE_AGE_S:
                    print(f"[!] cotatie eToro veche pentru {n}: {int((now - t).total_seconds())} s, o ignor (folosesc lumanarea orara)")
                    continue                                                      # cotatie intarziata: apelantii trec pe pretul lumanarii orare (la zi)
                out[n] = {"bid": float(x["bid"]), "ask": float(x["ask"]),
                          "conv_bid": float(x.get("conversionRateBid") or 0), "conv_ask": float(x.get("conversionRateAsk") or 0)}
        return out

    def positions(self, fresh: bool = False) -> list[dict]:
        out = []
        for p in self.api.positions(fresh):
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

    def closed_trades(self, min_date: str) -> list[dict]:
        """Toate pozitiile inchise de la min_date: [{id, net, close_time, ...}] (rezultatul real, din istoricul eToro)."""
        out = []
        for x in self.api.trade_history(min_date):
            pid = x.get("positionId") or x.get("positionID")
            if pid:
                out.append({"id": str(pid), "net": float(x.get("netProfit") or 0.0), "close_time": x.get("closeTimestamp", ""),
                            "close_rate": float(x.get("closeRate") or 0.0)})
        return out

    def closed_trade(self, position_id: str, min_date: str) -> dict | None:
        """Pozitia inchisa din istoricul eToro: {net, close_rate, close_time, open_rate, sl, tp, side, fees} sau None daca nu e (inca) acolo."""
        for x in self.api.trade_history(min_date):
            if str(x.get("positionId") or x.get("positionID") or "") == str(position_id):
                return {"net": float(x.get("netProfit") or 0.0), "close_rate": float(x.get("closeRate") or 0.0),
                        "close_time": x.get("closeTimestamp", ""), "open_rate": float(x.get("openRate") or 0.0),
                        "sl": float(x.get("stopLossRate") or 0.0), "tp": float(x.get("takeProfitRate") or 0.0),
                        "side": 1 if x.get("isBuy") else -1, "fees": float(x.get("fees") or 0.0)}
        return None

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

    def open(self, name: str, side: int, amount: float, lev: int, sl: float, tp: float, max_amount: float | None = None) -> str:
        """Deschide pozitia. Reincearca cu levier 20 DOAR daca eToro a respins CLAR ordinul din cauza levierului si doar daca marja
        mai mare incape in max_amount. Dupa un ordin trimis sau cu rezultat neclar NU se reincearca niciodata (risc de ordin dublu)."""
        try:
            pid = self._open(name, side, amount, lev, sl, tp)
            self.last = {"amount": amount, "leverage": lev}
            return pid
        except OrderRejected as e:
            if lev <= 20 or "leverage" not in str(e).lower():
                raise
            amount2 = math.ceil(amount * lev / 20 * 100) / 100
            if max_amount is not None and amount2 > max_amount + 0.001:
                raise OrderRejected(f"{e} (levier 20 ar cere {amount2:.2f}$ marja, peste banii liberi)") from e
            pid = self._open(name, side, amount2, 20, sl, tp)
            self.last = {"amount": amount2, "leverage": 20}
            return pid

    def _open(self, name, side, amount, lev, sl, tp) -> str:
        try:
            before = {p["id"] for p in self.positions(fresh=True)}
        except EToroError as e:                                   # inainte de a trimite ordinul: nu s-a intamplat nimic
            raise OrderRejected(f"nu pot citi portofoliul inainte de ordin ({type(e).__name__}); n-am trimis nimic") from e
        sent = datetime.now(timezone.utc)
        try:
            r = self.api.open_market(self.ids[name], side == 1, amount, lev, sl, tp)
        except EToroNetworkError as e:                            # nu stim daca a ajuns
            raise OrderUnconfirmed(f"nu stiu daca ordinul a ajuns la eToro ({type(e).__name__})", before, None, sent) from e
        except EToroHTTPError as e:
            if e.status >= 500:
                raise OrderUnconfirmed(f"eToro a raspuns cu eroare de server ({e.status}); rezultat neclar", before, str(e)[:200], sent) from e
            raise OrderRejected(str(e)) from e                    # 4xx: respins clar
        oid = self._order_id(r)
        for _ in range(12):                                       # pana la ~60 s
            time.sleep(5)
            if oid:
                try:
                    st = self.api.order_status(oid)
                    if isinstance(st, dict) and st.get("statusID") == 4:
                        raise OrderRejected(f"Ordin respins: {st.get('errorMessage')}")
                except OrderRejected:
                    raise
                except EToroError:
                    pass
            try:
                new = [p for p in self.positions(fresh=True) if p["id"] not in before and p["name"] == name and p["side"] == side
                       and (parse_time(p["time"]) is None or parse_time(p["time"]) >= sent.replace(microsecond=0) - timedelta(seconds=120))]
            except EToroError:
                continue
            if new:
                return new[0]["id"]
        raise OrderUnconfirmed("Ordinul a fost trimis, dar nu l-am văzut încă în portofoliu", before, r, sent)

    def close(self, pid: str, name: str) -> None:
        self.api.close_position(int(pid), self.ids[name])
