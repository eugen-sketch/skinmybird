"""Socoteala deciziilor tale: ce ai facut tu (inchideri inainte de tinta/plasa, pozitii deschise de tine, semnale refuzate)
fata de ce ar fi facut botul singur. Varianta «ce-ar fi fost» se calculeaza din preturile de 5 minute de dupa decizia ta,
cu aceleasi reguli ca botul: tinta si plasa puse pe eToro, plus limita de timp (doar pe plus)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from broker import parse_time

YOURS = {"YOU", "OTHER"}            # inchise de tine: din Telegram (YOU) sau direct din eToro (OTHER)
OPENED_BY_YOU = {"manual", "preluat"}


def entry(kind: str, name: str, side: int, **kw) -> dict:
    """Un rand in registru (doar campuri simple, ca sa intre in starea criptata)."""
    out = {"kind": kind, "name": name, "side": int(side)}
    for k, v in kw.items():
        out[k] = v.isoformat(timespec="seconds") if isinstance(v, datetime) else (round(v, 6) if isinstance(v, float) else v)
    return out


def walk(path: pd.DataFrame, side: int, ref_px: float, start: datetime, tp: float, sl: float, open_rate: float, notional: float,
         opened_at: datetime | None, max_hold_h: float, min_profit: float, cost_pct: float) -> tuple[float, str] | None:
    """Pretul la care s-ar fi iesit dupa `start`, cu tinta/plasa/limita de timp. Preturile Yahoo sunt aduse la scara eToro
    (raportul dintre pretul eToro de la `start` si pretul Yahoo de atunci). Intoarce (pret de iesire, cum) sau None fara date."""
    if path is None or path.empty or not ref_px:
        return None
    before = path[path.index <= start]
    after = path[path.index > start]
    if before.empty or after.empty:
        return None
    k = ref_px / float(before["close"].iloc[-1])
    half = cost_pct / 200 * notional
    for t, r in after.iterrows():
        h, l, o = float(r["high"]) * k, float(r["low"]) * k, float(r["open"]) * k
        if sl and ((l <= sl) if side == 1 else (h >= sl)):
            return (min(sl, o) if side == 1 else max(sl, o)), "plasa"
        if tp and ((h >= tp) if side == 1 else (l <= tp)):
            return tp, "tinta"
        if max_hold_h and opened_at and (t + timedelta(minutes=5) - opened_at).total_seconds() >= max_hold_h * 3600:
            best = h if side == 1 else l
            if side * (best - open_rate) / open_rate * notional - half >= min_profit:
                return open_rate * (1 + side * (min_profit + half) / notional), "limita de timp"
    return float(after["close"].iloc[-1]) * k, "încă deschisă"


def summarize(ledger: list[dict], since: datetime, fetch, inst: dict, cfg: dict, foreign: list[dict] | None = None, now: datetime | None = None) -> dict:
    """Totalurile pe saptamana: botul singur / inchiderile tale (luat vs ce-ar fi fost) / deschise de tine / semnale refuzate."""
    rows = [r for r in ledger if (parse_time(r.get("close_t") or r.get("at")) or since) >= since]
    paths: dict[str, pd.DataFrame | None] = {}
    days = max(2, min(59, int(((now or datetime.now(since.tzinfo)) - since).days) + 3))

    def path(name):
        if name not in paths:
            try:
                paths[name] = fetch(inst[name]["yahoo"], "5m", f"{days}d")
            except Exception:  # noqa: BLE001
                paths[name] = None
        return paths[name]

    mh, mp = cfg.get("max_hold_hours", 0), cfg.get("time_stop_min_profit_usd", 0.30)
    out = {"bot_n": 0, "bot_net": 0.0, "you_n": 0, "you_net": 0.0, "you_alt": 0.0, "you_open": 0, "you_miss": 0,
           "mine_n": 0, "mine_net": 0.0, "skip_n": 0, "skip_alt": 0.0, "skip_miss": 0, "skip_open": 0, "details": []}
    for r in rows:
        name, side = r["name"], r["side"]
        if r["kind"] in ("SKIP", "EXPIRED"):
            out["skip_n"] += 1
            at = parse_time(r.get("at"))
            w = walk(path(name), side, r.get("px", 0), at, r.get("tp", 0), r.get("sl", 0), r.get("px", 0), r.get("notional", 0),
                     at, mh, mp, inst.get(name, {}).get("cost", 0)) if name in inst and at else None
            if w is None:
                out["skip_miss"] += 1
                continue
            alt = side * (w[0] - r["px"]) / r["px"] * r["notional"] - inst[name]["cost"] / 100 * r["notional"]
            out["skip_alt"] += alt
            out["skip_open"] += w[1] == "încă deschisă"
            out["details"].append(("refuzat", name, side, 0.0, alt, w[1]))
            continue
        net = float(r.get("net", 0.0))
        if r.get("origin") in OPENED_BY_YOU:
            out["mine_n"] += 1
            out["mine_net"] += net
        elif r["kind"] in YOURS:
            out["you_n"] += 1
            out["you_net"] += net
            ct, ot = parse_time(r.get("close_t")), parse_time(r.get("open_t"))
            w = walk(path(name), side, r.get("close_rate", 0), ct, r.get("tp", 0), r.get("sl", 0), r.get("open_rate", 0),
                     r.get("notional", 0), ot, mh, mp, inst.get(name, {}).get("cost", 0)) if name in inst and ct and r.get("open_rate") else None
            if w is None:
                out["you_miss"] += 1
                out["you_alt"] += net                     # fara date: nu-ti atribui nici castig, nici pierdere
                continue
            alt = net + side * (w[0] - r["close_rate"]) / r["open_rate"] * r.get("notional", 0)
            out["you_alt"] += alt
            out["you_open"] += w[1] == "încă deschisă"
            out["details"].append(("închisă de tine", name, side, net, alt, w[1]))
        else:
            out["bot_n"] += 1
            out["bot_net"] += net
    for f in foreign or []:                                # deschise si inchise de tine direct in eToro (botul nu le-a vazut)
        out["mine_n"] += 1
        out["mine_net"] += f["net"]
    out["effect"] = (out["you_net"] - out["you_alt"]) + out["mine_net"] - out["skip_alt"]
    return out
