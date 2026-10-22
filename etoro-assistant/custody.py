"""Custodie (Eugen, 22 oct): pe contul real botul NU deschide nimic nou; doar pune pe eToro tinta si plasa pentru pozitiile
lui Eugen deschise manual, apoi verifica. Nivelurile vin dintr-un secret GitHub (CUSTODY_JSON), nu din codul public.
Format: {"targets": [{"pid": "123", "tp": 95.0, "sl": 107.8}, {"pid": "456", "tp": 0.826}]} (tp sau sl pot lipsi)."""
from __future__ import annotations

import json


def load_targets(raw: str | None) -> list[dict]:
    """Lista de tinte; goala daca secretul lipseste sau nu poate fi citit (atunci botul lucreaza ca de obicei)."""
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    out = []
    for t in data.get("targets", []) if isinstance(data, dict) else []:
        if not isinstance(t, dict) or not t.get("pid") or (t.get("tp") is None and t.get("sl") is None):
            continue
        out.append({"pid": str(t["pid"]), "tp": None if t.get("tp") is None else float(t["tp"]),
                    "sl": None if t.get("sl") is None else float(t["sl"])})
    return out


def signature(targets: list[dict]) -> str:
    return json.dumps(sorted(targets, key=lambda t: t["pid"]), sort_keys=True)


def check(t: dict, side: int, bid: float, ask: float, margin: float = 0.0) -> str | None:
    """De ce NU aplicam (None = e in regula). La cumparare iesirea e la «vanzare» (bid): tinta peste, plasa sub.
    La vanzare iesirea e la «cumparare» (ask): tinta sub, plasa peste.
    margin = distanta minima ceruta (fractie din pret) cand pretul e doar aproximativ (lumanarea orara)."""
    px = bid if side > 0 else ask
    gap = px * margin
    if t.get("tp") is not None and (t["tp"] - px) * side <= gap:
        return f"ținta {t['tp']:g} e de partea greșită a prețului ({px:g})"
    if t.get("sl") is not None and (px - t["sl"]) * side <= gap:
        return f"plasa {t['sl']:g} e de partea greșită a prețului ({px:g})"
    return None


def applied(t: dict, pos: dict, tol: float = 1e-6) -> bool:
    """Nivelurile citite de pe eToro dupa modificare = cele cerute (toleranta relativa mica)."""
    for k in ("tp", "sl"):
        if t.get(k) is not None and abs(float(pos.get(k) or 0) - t[k]) > max(tol, abs(t[k]) * 1e-4):
            return False
    return True
