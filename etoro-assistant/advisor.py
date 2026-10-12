"""Sfat simplu pentru o pozitie deschisa: TINE / INCHIDE / ATENTIE, cu motivele in limbaj omenesc.

Reguli simple (nu garanteaza nimic): cat din drumul spre tinta/plasa a parcurs pretul, de cat timp e deschisa, daca trendul orar
merge in directia ei, daca RSI-ul arata ca miscarea e obosita, cat profit e deja pe masa."""
from __future__ import annotations

MIN_GREEN_USD = 1.0          # peste atat, e deja "in verde" si merita incasat cand miscarea slabeste


def advise(side: int, open_rate: float, price: float | None, tp: float | None, sl: float | None, pnl: float,
           age_h: float, trend: str | None, rsi: float | None) -> dict:
    """Returneaza {'verdict': 'TINE'|'INCHIDE'|'ATENTIE', 'reasons': [...], 'to_tp': % sau None, 'to_sl': % sau None}."""
    to_tp = to_sl = None
    if price and open_rate and tp and abs(tp - open_rate) > 0:
        to_tp = max(0.0, side * (price - open_rate)) / abs(tp - open_rate)
    if price and open_rate and sl and abs(sl - open_rate) > 0:
        to_sl = max(0.0, -side * (price - open_rate)) / abs(sl - open_rate)
    aligned = (trend == "sus" and side == 1) or (trend == "jos" and side == -1)
    against = (trend == "jos" and side == 1) or (trend == "sus" and side == -1)
    tired = rsi is not None and ((side == 1 and rsi >= 70) or (side == -1 and rsi <= 30))
    reasons: list[str] = []
    if aligned:
        reasons.append("trendul pe oră merge în direcția ta")
    elif against:
        reasons.append("trendul pe oră merge ÎMPOTRIVA ta")
    elif trend == "lateral":
        reasons.append("piața stă pe loc (trend lateral)")
    if tired:
        reasons.append("mișcarea în direcția ta pare obosită (RSI extrem), poate urma o revenire")
    if age_h >= 1:
        reasons.append(f"e deschisă de ~{age_h:.0f} h" if age_h >= 2 else "e deschisă de peste o oră")

    verdict = "TINE"
    if to_sl is not None and to_sl >= 0.7:
        verdict = "INCHIDE" if against else "ATENTIE"
        reasons.insert(0, f"prețul a parcurs {to_sl * 100:.0f}% din drumul spre plasa de siguranță")
    elif pnl >= MIN_GREEN_USD:
        if to_tp is not None and to_tp >= 0.75:
            reasons.insert(0, "e aproape de țintă, mai las-o puțin")
        elif age_h >= 2 or against or tired:
            verdict = "INCHIDE"
            reasons.insert(0, f"ești deja în plus (+${pnl:.2f}) și mișcarea nu mai accelerează")
        else:
            reasons.insert(0, f"ești în plus (+${pnl:.2f}), iar mișcarea e încă în favoarea ta")
    elif pnl > 0:
        if age_h >= 3 and (to_tp or 0) < 0.3 and not aligned:
            verdict = "INCHIDE"
            reasons.insert(0, f"stă de ore bune aproape pe loc și ești în plus mic (+${pnl:.2f}); poți ieși în verde și elibera banii")
        elif against and age_h >= 1.5:
            verdict = "INCHIDE"
            reasons.insert(0, f"ești în plus doar puțin (+${pnl:.2f}) și trendul s-a întors")
        else:
            reasons.insert(0, "profit mic, încă are timp să ajungă la țintă")
    else:
        if against and (to_sl or 0) >= 0.35:
            verdict = "INCHIDE"
            reasons.insert(0, "ești pe minus și trendul merge împotriva ta; mai bine tai pierderea mică")
        elif against:
            verdict = "ATENTIE"
            reasons.insert(0, "ești pe minus și trendul e împotriva ta, urmărește-o")
        elif age_h >= 4 and (to_tp or 0) < 0.2:
            reasons.insert(0, "a stat mult pe loc; ține-o doar dacă vrei s-o lași să-și vadă de țintă sau de plasă")
        else:
            reasons.insert(0, "e pe minus mic, dar trendul nu e împotriva ta")
    return {"verdict": verdict, "reasons": reasons, "to_tp": to_tp, "to_sl": to_sl}
