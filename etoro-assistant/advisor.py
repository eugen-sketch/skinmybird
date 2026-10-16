"""Sfat simplu pentru o pozitie deschisa: TINE / INCHIDE / ATENTIE, cu motivele in limbaj omenesc.

Reguli simple (nu garanteaza nimic): cat din drumul spre tinta/plasa a parcurs pretul, de cat timp e deschisa, daca trendul orar
merge in directia ei, daca RSI-ul arata ca miscarea e obosita, cat profit e deja pe masa."""
from __future__ import annotations

MIN_GREEN_USD = 1.0          # peste atat, e deja "in verde" si merita incasat cand miscarea slabeste


NEW_MIN = 15                 # sub atatea minute pozitia e „noua”: minusul mic de la inceput e doar costul de intrare (spread)


def against_trend(side: int, trend: str | None) -> bool:
    """Intrare contra trendului orar (de ex. cumpar cand trendul e in jos): asta face regulile de revenire (RSI extrem)."""
    return (trend == "jos" and side == 1) or (trend == "sus" and side == -1)


def advise(side: int, open_rate: float, price: float | None, tp: float | None, sl: float | None, pnl: float,
           age_h: float, trend: str | None, rsi: float | None, counter: bool = False) -> dict:
    """Returneaza {'verdict': 'TINE'|'INCHIDE'|'ATENTIE'|'NOU', 'reasons': [...], 'to_tp': % sau None, 'to_sl': % sau None}.
    `counter` = pozitia a fost deschisa de bot PE REVENIRE, stiind de la inceput ca trendul e impotriva ei: nu o mai tratam ca pe o surpriza."""
    to_tp = to_sl = None
    if price and open_rate and tp and abs(tp - open_rate) > 0:
        to_tp = max(0.0, side * (price - open_rate)) / abs(tp - open_rate)
    if price and open_rate and sl and abs(sl - open_rate) > 0:
        to_sl = max(0.0, -side * (price - open_rate)) / abs(sl - open_rate)
    aligned = (trend == "sus" and side == 1) or (trend == "jos" and side == -1)
    against_raw = against_trend(side, trend)
    against = against_raw and not counter                    # trend impotriva e „surpriza” doar daca nu era planul
    tired = rsi is not None and ((side == 1 and rsi >= 70) or (side == -1 and rsi <= 30))
    reasons: list[str] = []
    if age_h * 60 < NEW_MIN and not (to_sl is not None and to_sl >= 0.7):
        # pozitie foarte noua: fara verdict dupa o pierdere mica (la deschidere minusul e spread-ul)
        why = ["deschisă acum, minusul mic de la început e costul de intrare"]
        if counter and against_raw:
            why.append("în plan: am intrat pe revenire, deși trendul orar merge " + ("în jos" if trend == "jos" else "în sus"))
        return {"verdict": "NOU", "reasons": why, "to_tp": to_tp, "to_sl": to_sl}
    if aligned:
        reasons.append("trendul pe oră merge în direcția ta")
    elif counter and against_raw:
        reasons.append("în plan: am intrat pe revenire, deși trendul orar merge " + ("în jos" if trend == "jos" else "în sus"))
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
        verdict = "ATENTIE"                                  # Regula 1: nu sfatuim si nu facem inchideri pe minus; plasa de siguranta ramane
        reasons.insert(0, f"prețul a parcurs {to_sl * 100:.0f}% din drumul spre plasa de siguranță (nu închid pe minus; decide plasa sau tu)")
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
            verdict = "ATENTIE"
            reasons.insert(0, "ești pe minus și trendul merge împotriva ta; nu închid pe minus, așteptăm țintă sau plasă")
        elif against:
            verdict = "ATENTIE"
            reasons.insert(0, "ești pe minus și trendul e împotriva ta, urmărește-o")
        elif age_h >= 4 and (to_tp or 0) < 0.2:
            reasons.insert(0, "a stat mult pe loc; ține-o doar dacă vrei s-o lași să-și vadă de țintă sau de plasă")
        elif counter and against_raw:
            reasons.insert(0, "e pe minus mic, normal pentru o intrare pe revenire; așteptăm revenirea sau ținta/plasa")
        else:
            reasons.insert(0, "e pe minus mic, dar trendul nu e împotriva ta")
    return {"verdict": verdict, "reasons": reasons, "to_tp": to_tp, "to_sl": to_sl}
