"""Mesaje Telegram pe limbaj omenesc, cu iconuri."""
from __future__ import annotations


def pair(name: str) -> str:
    if name == "OIL":
        return "Petrol (WTI) 🛢️"
    return f"{name[:3]}/{name[3:]}" if len(name) == 6 and name.isalpha() else name


def usd(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def signed(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


MENU = [["📊 Status", "🔎 Caută semnale"], ["🔒 Închide tot", "⛔ Oprește"], ["❓ Ajutor"]]


def started(hours: float, budget: float, scan_min: int, tp: float, basket: float) -> str:
    return (f"🟢 Asistentul a pornit și mă uit pe piață.\n\n"
            f"🔎 Scanez forex și petrol la fiecare {scan_min} minute și îți scriu când văd un semnal.\n"
            f"🤝 Nu deschid NICIUN ordin fără un „OK” de la tine.\n"
            f"🎯 Fiecare poziție deschisă are țintă ≈ {usd(tp)}. Dacă ai mai multe deschise și împreună ajung la ≈ {usd(basket)}, le închid eu automat.\n"
            f"✋ Poți închide oricând, din eToro sau de aici.\n"
            f"👛 Buget: {usd(budget)} · Sesiune: {hours:g} ore (apoi mă opresc singur)\n\n"
            f"👇 Folosește butoanele din meniul de sub căsuța de scris: Status, Caută semnale, Închide tot, Oprește, Ajutor.")


HELP = ("🤖 Ce pot face (butoanele din meniul de jos fac același lucru):\n"
        "• 📊 Status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• 🔎 Caută semnale – scanez piața chiar acum\n"
        "• 🔒 Închide tot – îți cer o confirmare, apoi închid toate pozițiile\n"
        "• ⛔ Oprește – îți cer o confirmare, apoi mă opresc\n\n"
        "Cele scrise de mână:\n"
        "• /status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• /inchide tot – închid toate pozițiile\n"
        "• /inchide EURUSD – închid o singură poziție (poți scrie și OIL)\n"
        "• /scan – caut semnale chiar acum\n"
        "• /stop – mă opresc (pozițiile rămân pe eToro, cu Stop Loss și Take Profit)\n"
        "La semnale apar butoanele ✅ OK / ❌ NU.")


def signal(name: str, side: int, why: str, px: float, digits: int, amount: float, lev: int, notional: float,
           tp_px: float, tp_usd: float, sl_px: float, sl_usd: float, free: float, can: bool, reason_no: str = "") -> str:
    act = "CUMPĂR" if side == 1 else "VÂND (short)"
    verdict = "BUY (cumpără)" if side == 1 else "SELL (vinde, short)"
    head = (f"{'🟢' if side == 1 else '🔴'} Semnal pe {pair(name)}: aș putea să {act}.\n{why[:1].upper() + why[1:]}.\nPreț acum: {px:.{digits}f}"
            f"\n👉 Recomandare: {verdict}")
    if not can:
        return f"{head}\n\n🚫 Nu pot deschide acum: {reason_no}"
    return (f"{head}\n\n"
            f"Dacă zici OK:\n"
            f"💰 bag {usd(amount)} din buget (levier {lev}, expunere ≈ {usd(notional)})\n"
            f"🎯 țintă {tp_px:.{digits}f} → câștig ≈ {usd(tp_usd)}\n"
            f"🛡️ plasă de siguranță {sl_px:.{digits}f} → pierd cel mult ≈ {usd(sl_usd)}\n"
            f"👛 buget liber acum: {usd(free)}\n\n"
            f"Deschid?")


def opened(name: str, side: int, px: float, digits: int, amount: float, lev: int, notional: float, tp_px: float, tp_usd: float,
           sl_px: float, sl_usd: float) -> str:
    head = (f"🟢🛒 Gata, am cumpărat {pair(name)} la {px:.{digits}f}." if side == 1
            else f"🔴📉 Gata, am vândut (short) {pair(name)} la {px:.{digits}f}.")
    return (f"{head}\n"
            f"💰 {usd(amount)} din buget (levier {lev}, expunere ≈ {usd(notional)})\n"
            f"🎯 Take Profit pus la {tp_px:.{digits}f} (≈ {usd(tp_usd)})\n"
            f"🛡️ Stop Loss pus la {sl_px:.{digits}f} (≈ {usd(sl_usd)})\n"
            f"Te țin la curent. Poți închide oricând cu /inchide.")


def status(rows: list[dict], total: float, free: float, budget: float, realized: float, n_closed: int) -> str:
    if not rows:
        return (f"📭 Nu ai nicio poziție deschisă.\n👛 Buget liber: {usd(free)} din {usd(budget)}\n"
                f"📒 În sesiunea asta: {n_closed} închise, rezultat {signed(realized)}")
    lines = [f"{'🟢' if r['pnl'] >= 0 else '🔴'} {pair(r['name'])} ({'cumpărat' if r['side'] == 1 else 'vândut'}): {signed(r['pnl'])}" for r in rows]
    icon = "📈" if total >= 0 else "📉"
    return ("📊 Pozițiile deschise acum:\n" + "\n".join(lines) + f"\n\n{icon} Total acum: {signed(total)}\n"
            f"👛 Buget liber: {usd(free)} din {usd(budget)}\n📒 În sesiunea asta: {n_closed} închise, rezultat {signed(realized)}")


def update(rows: list[dict], total: float) -> str:
    parts = ", ".join(f"{pair(r['name']).split(' ')[0]} {signed(r['pnl'])}" for r in rows)
    return f"⏱️ Update: {parts} · total {signed(total)}"


def closed(name: str, kind: str, pnl: float, total_closed: float) -> str:
    p = pair(name)
    if kind == "TP":
        return f"🎉💵 {p}: ținta a fost atinsă! Rezultat {signed(pnl)}. Poziția e închisă."
    if kind == "SL":
        return f"😕🛡️ {p}: s-a activat plasa de siguranță. Rezultat {signed(pnl)}. Poziția e închisă."
    if kind == "BASKET":
        return f"🎯 {p}: închisă împreună cu celelalte. Rezultat {signed(pnl)}."
    if kind == "YOU":
        return f"✋ {p}: am închis la cererea ta. Rezultat ≈ {signed(pnl)}."
    return f"👋 {p}: poziția s-a închis (probabil ai închis-o tu din eToro). Rezultat ≈ {signed(pnl)}."


def basket(n: int, total: float) -> str:
    return f"🎯💵 Țintă comună atinsă! Cele {n} poziții împreună fac ≈ {signed(total)}. Le închid acum."


def reminder(name: str, side: int, n: int, left_min: int) -> str:
    act = "BUY (cumpără)" if side == 1 else "SELL (vinde, short)"
    return (f"⏰ Aștept încă răspunsul tău ({n}): {'🟢' if side == 1 else '🔴'} {pair(name)} → {act}.\n"
            f"Semnalul mai e valabil ≈ {left_min} min. Zici OK sau NU?")


def expired() -> str:
    return "⌛ Semnalul ăsta a expirat (prețul s-a mișcat între timp). Dacă mai e valabil, îl găsesc la următoarea scanare."


def skipped() -> str:
    return "👍 Bine, nu deschid nimic."


def no_free_margin(need: float, free: float) -> str:
    return f"nu mai ai buget liber ({usd(free)} liber, cere {usd(need)})"


def error(txt: str) -> str:
    return f"⚠️🔧 Am o problemă tehnică: {txt}\nÎncerc din nou la următoarea verificare. Pozițiile deschise rămân pe eToro cu Stop Loss și Take Profit."


def stopped(reason: str, open_n: int) -> str:
    tail = (f"\n⚠️ Ai {open_n} poziții deschise: rămân pe eToro cu Stop Loss și Take Profit, dar eu nu le mai urmăresc (nici țintă comună)."
            if open_n else "")
    return f"🔴 M-am oprit ({reason}).{tail}"


def ending_soon(minutes: int) -> str:
    return f"⏰ Mai sunt ≈ {minutes} minute din sesiune. După aceea mă opresc; pornește-mă din nou dacă vrei să continui."


def confirm_close_all(n: int) -> str:
    return f"🔒 Sigur închid toate cele {n} poziții acum?"


def confirm_stop(open_n: int) -> str:
    extra = f" Cele {open_n} poziții deschise rămân pe eToro, cu Stop Loss și Take Profit." if open_n else ""
    return f"⛔ Sigur mă opresc?{extra}"


def cancelled() -> str:
    return "👌 Bine, las totul cum era."


def scan_report(rows: list[dict]) -> str:
    """rows: name, rsi, thr (prag RSI), asia (poz. fata de intervalul de noapte sau None), bar (ora ultimei bare), note."""
    lines = []
    for r in rows:
        extra = f" · fața de intervalul de noapte: {r['asia']}" if r.get("asia") and r["name"] != "OIL" else ""
        note = f" ({r['note']})" if r.get("note") else ""
        lines.append(f"• {pair(r['name']).split(' ')[0]}: RSI {r['rsi']:.0f}{extra}{note}")
    bar = rows[0]["bar"] if rows else "?"
    near = sorted((r for r in rows if "rsi" in r), key=lambda r: min(abs(r["rsi"] - r["thr"]), abs(r["rsi"] - (100 - r["thr"]))))
    n = near[0] if near else None
    if n:
        side = "BUY" if n["rsi"] < 50 else "SELL"
        close = (f"\n\n🎯 Cel mai aproape de semnal: {pair(n['name']).split(' ')[0]} (RSI {n['rsi']:.0f}). "
                 f"Ar deveni {side} dacă RSI ajunge {'sub ' + str(n['thr']) if side == 'BUY' else 'peste ' + str(100 - n['thr'])}.")
    else:
        close = ""
    return (f"🔎 Am scanat acum {len(rows)} instrumente (ultima oră încheiată: {bar}).\n" + "\n".join(lines) +
            f"\n\nNiciun semnal nou. Cumpăr/vând doar la RSI extrem sau la spargerea intervalului de noapte (07–11 UTC).{close}"
            f"\n\n👉 Recomandare acum: HOLD ⏸️ — nu cumpăra și nu vinde nimic, așteptăm.")


def heartbeat(hhmm: str, scans: int, last_scan: str, open_n: int, market_open: bool) -> str:
    if not market_open:
        return f"😴 {hhmm} UTC: sunt activ, dar piața e închisă acum. Reiau scanările când se deschide."
    pos = f" Ai {open_n} poziții deschise." if open_n else ""
    return (f"🟢 {hhmm} UTC: sunt activ. De la pornire am făcut {scans} scanări (la fiecare 15 min), ultima la {last_scan} UTC: "
            f"niciun semnal nou.{pos}")


def hour_range(bar_iso: str) -> str:
    """'2026-10-09T07:00:00+00:00' -> '07:00–08:00 UTC' (bara incepe la 07:00 si se incheie la 08:00)."""
    try:
        h = int(bar_iso[11:13])
    except ValueError:
        return str(bar_iso)
    return f"{h:02d}:00–{(h + 1) % 24:02d}:00 UTC"


def continued(hours: float) -> str:
    return (f"🔁 Am trecut într-o sesiune nouă (limita GitHub e ~6 ore pe sesiune). Mai sunt {hours:g} ore. Totul rămâne la fel: "
            f"scanez la 15 minute și nu deschid nimic fără OK-ul tău. Pozițiile deschise le-am preluat de pe eToro.")


def handover(remaining: float, open_n: int) -> str:
    return f"🔁 Mă mut într-o sesiune nouă, rămân pornit încă {remaining:g} ore. (Poziții deschise: {open_n}, rămân urmărite.)"
