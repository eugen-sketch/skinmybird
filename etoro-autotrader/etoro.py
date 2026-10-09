"""Client minimal pentru eToro Public API - DOAR cont DEMO.

Orice cale de tranzactionare trebuie sa contina '/demo/'; codul refuza explicit orice altceva,
deci nu poate plasa ordine pe contul real.
Documentatia oficiala: https://api-portal.etoro.com (caile exacte pot varia - vezi etoro_check.py).
"""
from __future__ import annotations

import json
import os
import uuid

import requests

BASE = os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")


class EToroError(RuntimeError):
    pass


class EToroDemo:
    def __init__(self, api_key: str | None = None, user_key: str | None = None, verbose: bool = True):
        self.api_key = api_key or os.getenv("ETORO_API_KEY", "")
        self.user_key = user_key or os.getenv("ETORO_USER_KEY", "")
        if not (self.api_key and self.user_key):
            raise EToroError("Lipsesc ETORO_API_KEY / ETORO_USER_KEY")
        self.verbose = verbose

    # ---------------------------------------------------------------- baza
    def _req(self, method: str, path: str, *, params=None, body=None, trading: bool = False) -> dict | list:
        if trading and "/demo/" not in path:
            raise EToroError(f"REFUZ: calea de tranzactionare nu e DEMO: {path}")
        headers = {"x-api-key": self.api_key, "x-user-key": self.user_key,
                   "x-request-id": str(uuid.uuid4()), "Content-Type": "application/json"}
        r = None
        for attempt in (1, 2):
            try:
                r = requests.request(method, BASE + path, headers=headers, params=params,
                                     data=json.dumps(body) if body is not None else None, timeout=60)
                break
            except requests.RequestException as e:
                if attempt == 2 or method != "GET":   # nu repetam ordinele (risc de dublare)
                    raise EToroError(f"{method} {path}: {type(e).__name__}") from e
                headers["x-request-id"] = str(uuid.uuid4())
        if self.verbose:
            print(f"[eToro] {method} {path} {params or ''} {json.dumps(body) if body else ''} -> {r.status_code} {r.text[:600]}")
        if r.status_code >= 400:
            raise EToroError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}

    # ---------------------------------------------------------- instrumente
    def find_instrument_id(self, symbol: str) -> int:
        """Cauta ID-ul numeric al instrumentului dupa simbol (ex: EURUSD, GOLD)."""
        last = None
        for path, params in (
            ("/api/v1/market-data/search", {"internalSymbolFull": symbol, "fields": "instrumentId,internalSymbolFull,displayname"}),
            ("/api/v1/market-data/search", {"searchText": symbol, "fields": "instrumentId,internalSymbolFull,displayname"}),
        ):
            try:
                data = self._req("GET", path, params=params)
            except EToroError as e:
                last = e
                continue
            items = data.get("items") or data.get("instruments") or data.get("Items") if isinstance(data, dict) else data
            for it in items or []:
                sym = str(it.get("internalSymbolFull") or it.get("symbolFull") or it.get("symbol") or "").upper()
                iid = it.get("instrumentId") or it.get("InstrumentID") or it.get("instrumentID")
                if iid and sym == symbol.upper():
                    return int(iid)
        raise EToroError(f"Nu am gasit instrumentul {symbol}: {last}")

    # --------------------------------------------------------------- cont
    def portfolio(self) -> dict:
        return self._req("GET", "/api/v1/trading/info/demo/portfolio", trading=True)

    def positions(self) -> list[dict]:
        p = self.portfolio()
        if isinstance(p, dict):
            p = p.get("clientPortfolio", p)
            pos = p.get("positions") or p.get("Positions") or []
        else:
            pos = p
        return [x for x in pos if isinstance(x, dict)]

    # ------------------------------------------------------------- ordine
    def open_market(self, instrument_id: int, is_buy: bool, amount: float, leverage: int,
                    stop_loss: float, take_profit: float) -> dict:
        """Deschide pozitie la piata pe DEMO, cu SL/TP obligatorii."""
        body_v2 = {"action": "open", "transaction": "buy" if is_buy else "sell", "instrumentId": instrument_id,
                   "orderType": "mkt", "leverage": leverage, "amount": round(amount, 2), "orderCurrency": "usd",
                   "stopLossRate": stop_loss, "takeProfitRate": take_profit, "stopLossType": "fixed"}
        try:
            return self._req("POST", "/api/v2/trading/execution/demo/orders", body=body_v2, trading=True)
        except EToroError as e:
            if "404" not in str(e) and "405" not in str(e):
                raise
        body_v1 = {"InstrumentID": instrument_id, "IsBuy": is_buy, "Leverage": leverage, "Amount": round(amount, 2),
                   "StopLossRate": stop_loss, "TakeProfitRate": take_profit, "IsTslEnabled": False}
        return self._req("POST", "/api/v1/trading/execution/demo/market-open-orders/by-amount", body=body_v1, trading=True)

    def close_position(self, position_id: int, instrument_id: int) -> dict:
        body = {"InstrumentId": instrument_id, "UnitsToDeduct": None}
        return self._req("POST", f"/api/v1/trading/execution/demo/market-close-orders/positions/{position_id}",
                         body=body, trading=True)

    def last_price(self, instrument_id: int) -> float:
        """Ultimul pret eToro (inchiderea ultimei lumanari de 1 ora)."""
        data = self._req("GET", f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/OneHour/2")
        candles = data.get("candles") if isinstance(data, dict) else data
        if candles and isinstance(candles[0], dict) and "candles" in candles[0]:
            candles = candles[0]["candles"]
        c = candles[0]
        return float(c.get("close") or c.get("Close"))
