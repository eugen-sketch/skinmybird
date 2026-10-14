"""Client minimal pentru eToro Public API.

Implicit lucreaza DOAR pe contul DEMO: orice cale de tranzactionare trebuie sa contina '/demo/', altfel codul refuza.
Contul REAL se activeaza doar explicit (real=True, adica TRADING_MODE=real, decizia utilizatorului) si foloseste ALTE chei
(ETORO_REAL_API_KEY / ETORO_REAL_USER_KEY); in modul real, orice cale care contine '/demo/' este refuzata.
Documentatia oficiala: https://api-portal.etoro.com (caile exacte pot varia - vezi etoro_check.py).
"""
from __future__ import annotations

import json
import os
import time
import uuid

import requests

BASE = os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")


class EToroError(RuntimeError):
    pass


class EToroHTTPError(EToroError):
    """eToro a raspuns cu eroare HTTP (respingere clara pentru 4xx; 5xx = rezultat neclar)."""

    def __init__(self, msg: str, status: int):
        super().__init__(msg)
        self.status = status


class EToroNetworkError(EToroError):
    """Nu stim daca cererea a ajuns (timeout, conexiune cazuta): la un ordin, rezultatul e NECLAR."""


class EToroDemo:
    def __init__(self, api_key: str | None = None, user_key: str | None = None, verbose: bool | None = None, real: bool = False):
        self.real = real
        pre = "ETORO_REAL_" if real else "ETORO_"
        self.api_key = api_key or os.getenv(pre + "API_KEY", "")
        self.user_key = user_key or os.getenv(pre + "USER_KEY", "")
        if not (self.api_key and self.user_key):
            raise EToroError(f"Lipsesc {pre}API_KEY / {pre}USER_KEY")
        # logurile rularilor din repo-ul public sunt vizibile oricui: raspunsurile eToro se afiseaza doar la cerere
        self.verbose = os.getenv("ETORO_VERBOSE") == "1" if verbose is None else verbose
        self._pf: tuple[float, dict | list] | None = None        # portofoliul citit recent (reducem numarul de apeluri)

    # ---------------------------------------------------------------- baza
    def _req(self, method: str, path: str, *, params=None, body=None, trading: bool = False) -> dict | list:
        if trading and not self.real and "/demo/" not in path:
            raise EToroError(f"REFUZ: calea de tranzactionare nu e DEMO: {path}")
        if trading and self.real and "/demo/" in path:
            raise EToroError(f"REFUZ: modul real nu poate folosi o cale DEMO: {path}")
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
                    raise EToroNetworkError(f"{method} {path}: {type(e).__name__}") from e
                headers["x-request-id"] = str(uuid.uuid4())
        if self.verbose:
            print(f"[eToro] {method} {path} {params or ''} {json.dumps(body) if body else ''} -> {r.status_code} {r.text[:2500] if 'portfolio' in path else r.text[:600]}")
        if method == "GET" and r.status_code in (429, 500, 502, 503, 504):          # citirile se reiau (limita de apeluri / eroare trecatoare)
            for wait in (1.5, 4.0):
                try:
                    wait = min(float(r.headers.get("Retry-After", wait)), 10.0)
                except (TypeError, ValueError):
                    pass
                time.sleep(wait)
                headers["x-request-id"] = str(uuid.uuid4())
                try:
                    r = requests.request(method, BASE + path, headers=headers, params=params, timeout=60)
                except requests.RequestException as ex:
                    raise EToroNetworkError(f"{method} {path}: {type(ex).__name__}") from ex
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
        if r.status_code >= 400:
            raise EToroHTTPError(f"{method} {path} -> {r.status_code}: {r.text[:200]}", r.status_code)
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}

    # ---------------------------------------------------------- instrumente
    def search_symbols(self, symbol: str, pages: int = 4) -> list[dict]:
        """Toate instrumentele al caror simbol incepe cu 'symbol' (pagini de cate 100)."""
        out = []
        for page in range(1, pages + 1):
            data = self._req("GET", "/api/v1/market-data/search",
                             params={"internalSymbolFull": symbol, "fields": "instrumentId,internalSymbolFull,displayname",
                                     "pageSize": 100, "pageNumber": page, "page": page})
            items = data.get("items") if isinstance(data, dict) else data
            items = [i for i in (items or []) if i.get("internalSymbolFull")]
            out += items
            if not items or len(out) >= int(data.get("totalItems", 0) if isinstance(data, dict) else 0):
                break
        return out

    def find_instrument_id(self, symbol: str) -> int:
        """ID-ul numeric al instrumentului dupa simbolul exact eToro (ex: EURUSD, OIL)."""
        items = self.search_symbols(symbol)
        for it in items:
            if str(it.get("internalSymbolFull", "")).upper() == symbol.upper():
                return int(it["instrumentId"])
        names = [it["internalSymbolFull"] for it in items][:30]
        raise EToroError(f"Nu am gasit exact {symbol}; candidati: {names}")

    # --------------------------------------------------------------- cont
    def tp(self, demo_path: str) -> str:
        """Calea de tranzactionare: cea DEMO (cu /demo/) sau, in modul real, aceeasi cale fara '/demo'."""
        return demo_path.replace("/demo/", "/", 1) if self.real else demo_path

    def portfolio(self, fresh: bool = False) -> dict:
        """Portofoliul; reutilizat max. 6 secunde (monitorizarea il cere de mai multe ori), cu fresh=True mereu proaspat."""
        if not fresh and self._pf and time.time() - self._pf[0] < 6:
            return self._pf[1]
        data = self._req("GET", self.tp("/api/v1/trading/info/demo/portfolio"), trading=True)
        self._pf = (time.time(), data)
        return data

    def rates(self, instrument_ids: list[int]) -> dict[int, dict]:
        """Cotatii live (bid/ask + cursul de conversie in USD) pentru mai multe instrumente, intr-un singur apel."""
        d = self._req("GET", "/api/v1/market-data/instruments/rates", params={"instrumentIds": ",".join(str(i) for i in instrument_ids)})
        items = d.get("rates") if isinstance(d, dict) else d
        return {int(x["instrumentID"]): x for x in (items or []) if isinstance(x, dict) and "instrumentID" in x}

    def credit(self, fresh: bool = False) -> float | None:
        """Banii disponibili (fara pozitiile deschise) din portofoliu; None daca nu gasesc campul."""
        p = self.portfolio(fresh)
        cp = p.get("clientPortfolio", p) if isinstance(p, dict) else {}
        for k in ("credit", "Credit", "availableBalance", "availableCash"):
            if isinstance(cp, dict) and isinstance(cp.get(k), (int, float)):
                return float(cp[k])
        return None

    def positions(self, fresh: bool = False) -> list[dict]:
        p = self.portfolio(fresh)
        if isinstance(p, dict):
            p = p.get("clientPortfolio", p)
            if "positions" not in p and "Positions" not in p:
                raise EToroError("raspuns de portofoliu fara campul 'positions'")     # nu-l tratam ca 'nicio pozitie'
            pos = p.get("positions") or p.get("Positions") or []
        else:
            pos = p
        return [x for x in pos if isinstance(x, dict)]

    def trade_history(self, min_date: str, page_size: int = 100, max_pages: int = 10) -> list[dict]:
        """Pozitiile INCHISE de la min_date (YYYY-MM-DD): rezultat real (netProfit), pret de inchidere, plasa/tinta puse. Aceeasi ruta pe real."""
        out: list[dict] = []
        for page in range(1, max_pages + 1):
            d = self._req("GET", "/api/v1/trading/info/trade/history", params={"minDate": min_date, "page": page, "pageSize": page_size}, trading=True)
            items = d if isinstance(d, list) else (d.get("items") or d.get("trades") or d.get("history") or []) if isinstance(d, dict) else []
            items = [x for x in items if isinstance(x, dict)]
            out += items
            if len(items) < page_size:
                break
        return out

    # ------------------------------------------------------------- ordine
    def open_market(self, instrument_id: int, is_buy: bool, amount: float, leverage: int,
                    stop_loss: float, take_profit: float) -> dict:
        """Deschide pozitie la piata pe DEMO, cu SL/TP obligatorii."""
        body_v2 = {"action": "open", "transaction": "buy" if is_buy else "sell", "instrumentId": instrument_id,
                   "orderType": "mkt", "leverage": leverage, "amount": round(amount, 2), "orderCurrency": "usd",
                   "stopLossRate": stop_loss, "takeProfitRate": take_profit, "stopLossType": "fixed"}
        if is_buy and not self.real:  # v2 nu suporta vanzarea (short); pe contul real folosim doar v1 (documentat)
            try:
                return self._req("POST", "/api/v2/trading/execution/demo/orders", body=body_v2, trading=True)
            except EToroError as e:
                if not any(k in str(e) for k in ("404", "405", "not supported")):
                    raise
        self._pf = None                                             # dupa un ordin, portofoliul se citeste din nou
        body_v1 = {"InstrumentID": instrument_id, "IsBuy": is_buy, "Leverage": leverage, "Amount": round(amount, 2),
                   "StopLossRate": stop_loss, "TakeProfitRate": take_profit, "IsTslEnabled": False}
        return self._req("POST", self.tp("/api/v1/trading/execution/demo/market-open-orders/by-amount"), body=body_v1, trading=True)

    def close_position(self, position_id: int, instrument_id: int) -> dict:
        body = {"InstrumentId": instrument_id, "UnitsToDeduct": None}
        self._pf = None
        return self._req("POST", self.tp(f"/api/v1/trading/execution/demo/market-close-orders/positions/{position_id}"),
                         body=body, trading=True)

    def last_price(self, instrument_id: int) -> float:
        """Ultimul pret eToro (inchiderea ultimei lumanari de 1 ora)."""
        data = self._req("GET", f"/api/v1/market-data/instruments/{instrument_id}/history/candles/desc/OneHour/2")
        candles = data.get("candles") if isinstance(data, dict) else data
        if candles and isinstance(candles[0], dict) and "candles" in candles[0]:
            candles = candles[0]["candles"]
        c = candles[0]
        return float(c.get("close") or c.get("Close"))

    def order_status(self, order_id: int) -> dict:
        """Starea unui ordin: statusID 3 = executat, 4 = respins (cu errorMessage)."""
        path = f"/api/v1/trading/info/real/orders/{order_id}" if self.real else f"/api/v1/trading/info/demo/orders/{order_id}"   # pe real ruta are '/real/'
        return self._req("GET", path, trading=True)
