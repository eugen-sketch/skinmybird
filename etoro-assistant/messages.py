"""Mesaje Telegram pe limbaj omenesc, cu iconuri."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    RO_TZ = ZoneInfo("Europe/Bucharest")
except Exception:  # noqa: BLE001 - fara baza de fusuri orare: UTC+3 (ora de vara) ca rezerva
    RO_TZ = timezone(timedelta(hours=3))


INDEX_NAMES = {"SPX500": "S&P 500 📈", "NSDQ100": "Nasdaq 100 📈", "DJ30": "Dow Jones 📈", "GER40": "DAX Germania 📈"}


def pair(name: str) -> str:
    if name == "OIL":
        return "Petrol (WTI) 🛢️"
    if name == "GOLD":
        return "Aur (Gold) 🥇"
    if name in INDEX_NAMES:
        return INDEX_NAMES[name]
    return f"{name[:3]}/{name[3:]}" if len(name) == 6 and name.isalpha() else name


def usd(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def signed(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):,.2f}"


MENU = [["📊 Status", "🔎 Caută semnale"], ["🔒 Închide tot", "⛔ Oprește"], ["🤖 Autotrading", "❓ Ajutor"], ["▶️ Pornește"]]


def started(hours: float, budget: float, scan_min: int, basket: float, real: bool = False) -> str:
    head = "🔴 CONT REAL (bani adevărați)" if real else "🧪 Cont DEMO"
    return (f"🟢 Asistentul a pornit și mă uit pe piață. {head}\n\n"
            f"🔎 Scanez forex, petrol, aur și indici la fiecare {scan_min} minute, pe trendul orar, și îți scriu când văd un semnal.\n"
            f"🤝 Nu deschid NICIUN ordin fără un „OK” de la tine, decât dacă pornești tu 🤖 Autotrading din meniu.\n"
            f"🎯 Țintă (TP) și plasă de siguranță (SL) le pun eu automat, din volatilitatea orară: țintă mică, atinsă de obicei în 1–2 ore, plasă largă.\n"
            f"🤝 Dacă ai mai multe poziții și împreună ajung la ≈ {usd(basket)}, le închid eu.\n"
            f"📈 Sumele urmează soldul din cont (împart bugetul pe 2 sau 3 poziții, minim 50 $ pe poziție).\n"
            f"✋ Poți închide oricând, din eToro sau de aici.\n"
            f"👛 Buget de lucru: {usd(budget)} · Sesiune: {hours:g} ore (apoi mă opresc singur)\n\n"
            f"👇 Folosește butoanele din meniul de sub căsuța de scris.")


HELP = ("🤖 Ce pot face (butoanele din meniul de jos fac același lucru):\n"
        "• 📊 Status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• 🔎 Caută semnale – scanez piața chiar acum\n"
        "• 🔒 Închide tot – îți cer o confirmare, apoi închid toate pozițiile\n"
        "• ⛔ Oprește – îți cer o confirmare, apoi mă opresc\n"
        "• Deschidere manuală: scrie «vinde nzdusd», «cumpără eurusd», «vinde aur», «cumpără dax» – calculez suma din banii liberi și te întreb OK/NU\n"
        "• «preia nzdusd» – dacă ai deschis o poziție direct în eToro și vrei s-o urmăresc eu\n"
        "• 🤖 Autotrading – pornești/oprești deschiderea automată a semnalelor (doar tu o pornești; limită de pierdere pe zi)\n"
        "• ▶️ Pornește – când sunt oprit, mă pornești de aici (rulez singur până la 12 ore, apoi repornesc automat)\n\n"
        "Cele scrise de mână:\n"
        "• /status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• /inchide tot – închid toate pozițiile\n"
        "• /raport – raportul zilei (câștig azi + total de la început); vine singur cu ~30 min înainte de închiderea pieței\n"
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


def profit_block(day: str, today: float, today_n: int, total: float, total_n: int, since: str) -> str:
    """Doua randuri CLARE, mereu la fel peste tot: profitul de AZI si profitul TOTAL de la inceput (doar pozitii inchise)."""
    def dmy(s: str) -> str:
        return f"{s[8:10]}.{s[5:7]}" if len(s) >= 10 else "?"
    return (f"📅 PROFIT AZI ({dmy(day)}): {signed(today)} · {today_n} poziții închise azi\n"
            f"💼 PROFIT TOTAL de la început ({dmy(since)}): {signed(total)} · {total_n} poziții închise în total")


def status(rows: list[dict], total: float, free: float, budget: float, profit: str, auto: bool = False, warn: str = "") -> str:
    tail = ("\n🤖 Autotrading: PORNIT" if auto else "") + (f"\n{warn}" if warn else "")
    if not rows:
        return (f"📭 Nu ai nicio poziție deschisă.\n👛 Buget liber: {usd(free)} din {usd(budget)}\n"
                f"\n{profit}{tail}")
    lines = [f"{'🟢' if r['pnl'] >= 0 else '🔴'} {pair(r['name'])} ({'cumpărat' if r['side'] == 1 else 'vândut'}): {signed(r['pnl'])}"
             + (f" · ținta e {signed(r['tp_usd'])}" if r.get("tp_usd") else "")
             + advice_block(r.get("advice")) for r in rows]
    icon = "📈" if total >= 0 else "📉"
    return ("📊 Pozițiile deschise acum:\n" + "\n".join(lines) + f"\n\n{icon} Total acum: {signed(total)}\n"
            f"👛 Buget liber: {usd(free)} din {usd(budget)}\n\n{profit}{tail}\n"
            f"ℹ️ Sfaturile vin din reguli simple (trend orar, RSI, timp, cât a mers spre țintă/plasă).")


VERDICT = {"TINE": "✋ ȚINE-O", "INCHIDE": "🔒 ÎNCHIDE-O", "ATENTIE": "⚠️ ATENȚIE"}


def advice_block(adv: dict | None) -> str:
    """Sfatul pentru o pozitie, pe scurt si pe intelesul tuturor (fara grafice)."""
    if not adv:
        return ""
    bits = []
    if adv.get("to_tp") is not None:
        bits.append(f"până la țintă: {min(100, adv['to_tp'] * 100):.0f}% parcurs")
    if adv.get("to_sl"):
        bits.append(f"spre plasă: {min(100, adv['to_sl'] * 100):.0f}%")
    if adv.get("age_h"):
        h = adv["age_h"]
        bits.append(f"deschisă de {int(h)} h {int((h % 1) * 60)} min" if h >= 1 else f"deschisă de {int(h * 60)} min")
    trend = {"sus": "↗️ sus", "jos": "↘️ jos", "lateral": "↔️ lateral"}.get(adv.get("trend"))
    t4 = {"sus": "↗️", "jos": "↘️", "lateral": "↔️"}.get(adv.get("trend4h"))
    if trend:
        bits.append(f"trend orar {trend}" + (f", pe 4 ore {t4}" if t4 else ""))
    if adv.get("rsi") is not None:
        bits.append(f"RSI {adv['rsi']:.0f}")
    why = "; ".join(adv.get("reasons", [])[:3])
    return (f"\n   {' · '.join(bits)}" if bits else "") + f"\n   👉 Sfat: {VERDICT.get(adv['verdict'], adv['verdict'])}" + (f" — {why}" if why else "")


def update(rows: list[dict], total: float) -> str:
    parts = ", ".join(f"{pair(r['name']).split(' ')[0]} {signed(r['pnl'])}" + (f" (ținta {signed(r['tp_usd'])})" if r.get("tp_usd") else "") for r in rows)
    return f"⏱️ Update: {parts} · total {signed(total)}"


def closed(name: str, kind: str, pnl: float, profit: str, equity: float | None = None, plan: float | None = None) -> str:
    return _closed(name, kind, pnl, plan) + f"\n\n{profit}" + (f"\n👛 Buget de lucru acum: {usd(equity)}" if equity else "")


def target_differs(name: str, plan: float, real_tp: float, real_sl: float | None) -> str:
    """Tinta de pe eToro difera mult de cea planuita: cifra reala, ca mesajele sa nu mai spuna alta poveste decat se intampla."""
    sl = f" Plasa reală: {usd(real_sl)}." if real_sl else ""
    return (f"⚠️ {pair(name)}: ținta reală pe eToro este {usd(real_tp)}, nu {usd(plan)} cât planificasem "
            f"(prețul de la care am calculat nu era cel de la deschidere).{sl} De aici încolo urmăresc cifrele reale.")


def _closed(name: str, kind: str, pnl: float, plan: float | None = None) -> str:
    p = pair(name)
    if kind == "TP":
        if plan and pnl < 0.6 * plan:                      # rezultat mult sub tinta planuita: nu spunem „ținta atinsă”
            return (f"✅ {p}: ieșit la nivelul de profit setat pe eToro. Rezultat ≈ {signed(pnl)} după costuri "
                    f"(ținta planificată era {usd(plan)}). Poziția e închisă.")
        return f"🎉💵 {p}: ținta a fost atinsă! Rezultat ≈ {signed(pnl)}. Poziția e închisă."
    if kind == "SL":
        return f"😕🛡️ {p}: s-a activat plasa de siguranță. Rezultat ≈ {signed(pnl)}. Poziția e închisă."
    if kind == "BASKET":
        return f"🎯 {p}: închisă împreună cu celelalte. Rezultat {signed(pnl)}."
    if kind == "YOU":
        return f"✋ {p}: am închis la cererea ta. Rezultat ≈ {signed(pnl)}."
    return (f"👋 {p}: poziția s-a închis în afara țintei și a plasei (nu am închis-o eu). Rezultat {signed(pnl)}.\n"
            f"Dacă nu ai închis-o tu din eToro, spune-mi ca să verific.")


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


def scan_report(rows: list[dict], took: float | None = None) -> str:
    """rows: name, rsi, thr (prag RSI), asia (poz. fata de intervalul de noapte sau None), bar (ora ultimei bare), note,
    trend, rsi_rule (are regula de RSI extrem), skip (n-am putut/nu trebuia sa-l scanez acum)."""
    lines = []
    for r in rows:
        nm = pair(r["name"]).split(" ")[0]
        note = f" ({r['note']})" if r.get("note") else ""
        if r.get("skip"):
            lines.append(f"• {nm}:{note}")
            continue
        extra = f" · fața de intervalul de noapte: {r['asia']}" if r.get("asia") and len(r["name"]) == 6 and r["name"].isalpha() else ""
        trend = {"sus": " · trend orar: ↗️ sus", "jos": " · trend orar: ↘️ jos", "lateral": " · trend orar: ↔️ lateral"}.get(r.get("trend"), "")
        live = r.get("rsi_live")
        now_rsi = f" (acum {live:.0f})" if live is not None and abs(live - r["rsi"]) >= 1 else ""
        lines.append(f"• {nm}: RSI {r['rsi']:.0f}{now_rsi}{trend}{extra}{note}")
    scanned = [r for r in rows if not r.get("skip")]
    bar = next((r["bar"] for r in scanned if r.get("bar") not in (None, "?")), "?")
    near = sorted((r for r in scanned if r.get("rsi_rule", True) and not r.get("note")),
                  key=lambda r: min(abs(r["rsi"] - r["thr"]), abs(r["rsi"] - (100 - r["thr"]))))
    n = near[0] if near else None
    if n:
        side = "BUY" if n["rsi"] < 50 else "SELL"
        close = (f"\n\n🎯 Cel mai aproape de semnal (la RSI): {pair(n['name']).split(' ')[0]} (RSI {n['rsi']:.0f}). "
                 f"Ar deveni {side} dacă RSI ajunge {'sub ' + str(n['thr']) if side == 'BUY' else 'peste ' + str(100 - n['thr'])}.")
    else:
        close = ""
    ticks = [r["tick"] for r in scanned if r.get("tick")]
    stamp = ""
    if took is not None:
        last = ro_hm(max(ticks)) if ticks else "?"
        stamp = (f"\n\n⏱️ Am citit datele proaspete acum, în {took:.1f} s (ultima cotație văzută: {last}). "
                 f"RSI-ul fără paranteză e pe ultima oră ÎNCHEIATĂ (după el decid semnalele); „acum” e pe ora în curs, doar informativ.")
    skipped = len(rows) - len(scanned)
    tail = f", {skipped} în afara programului sau fără date proaspete" if skipped else ""
    return (f"🔎 Am scanat acum {len(scanned)} instrumente{tail} (ultima oră încheiată: {bar}).\n" + "\n".join(lines) +
            f"\n\nNiciun semnal nou. Cumpăr/vând doar când văd semnal clar (revenire după retragere în trend, spargere de maxim/minim, RSI extrem, spargerea intervalului de noapte pe forex).{close}"
            f"{stamp}\n\n👉 Recomandare acum: HOLD ⏸️ — nu cumpăra și nu vinde nimic, așteptăm.")


def daily_report(day: str, pnl: float, n: int, unreal: float, open_rows: list, days: list, total: float, since: str, n_total: int,
                 final: bool = True) -> str:
    """Raportul zilei: profit AZI si profit TOTAL (acelasi bloc ca peste tot), pozitii deschise acum, ultimele zile."""
    def dmy(s: str) -> str:
        return f"{s[8:10]}.{s[5:7]}"
    head = "🌙 Raportul zilei" if final else "📋 Raport până acum"
    lines = [f"{head} · {dmy(day)}", "",
             f"━━ 📅 PROFIT AZI ({dmy(day)}) ━━",
             f"Profit azi: {signed(pnl)}",
             f"Poziții închise azi: {n}", "",
             f"━━ 💼 PROFIT TOTAL de la început ({dmy(since)}) ━━",
             f"Profit total: {signed(total)}",
             f"Poziții închise în total: {n_total}", ""]
    if open_rows:
        lines.append(f"⏳ Poziții deschise acum: {len(open_rows)} · {signed(unreal)} nerealizat (NU intră în profit până nu se închid)")
        for r in open_rows:
            left = r["tp_usd"] - r["pnl"]
            lines.append(f"• {pair(r['name'])} ({'cumpărat' if r['side'] == 1 else 'vândut'}): acum {signed(r['pnl'])} · "
                         f"ținta e {signed(r['tp_usd'])}"
                         + (f" (mai are {usd(left)} până la țintă)" if left > 0 else " (a trecut de țintă)")
                         + f" · plasa −{usd(r['sl_usd'])}")
    else:
        lines.append("📭 Nu rămâne nicio poziție deschisă.")
    if days:
        lines += ["", "Zilele dinainte:"] + [f"• {dmy(k)}: {signed(v['pnl'])} ({v['n']} poziții)" for k, v in days]
    if final:
        lines += ["", "Piața se închide în curând; cele deschise rămân pe eToro cu Stop Loss și Take Profit."]
    return "\n".join(lines)


def radar(rows: list[dict], hhmm: str) -> str:
    """Raport rar (silentios): doar ce s-a miscat cel mai mult; nu repet lista completa."""
    sc = [r for r in rows if not r.get("skip") and not r.get("note")]
    top = sorted(sc, key=lambda r: -abs(r.get("move_atr") or 0))[:3]
    arrow = {"sus": "↗️", "jos": "↘️", "lateral": "↔️"}
    lines = [f"• {pair(r['name']).split(' ')[0]} {arrow.get(r.get('trend'), '')} {'+' if (r.get('move_atr') or 0) >= 0 else '−'}{abs(r.get('move_atr') or 0):.1f}× "
             f"(RSI {r['rsi']:.0f})" for r in top]
    quiet = max((abs(r.get("move_atr") or 0) for r in sc), default=0) < 0.8
    head = "piața e liniștită" if quiet else "ce s-a mișcat cel mai mult în ultimele 3 ore (în multipli de volatilitate normală)"
    return (f"📡 Radar {hhmm} – {head}:\n" + "\n".join(lines) +
            "\n\nSupraveghez la fiecare 5 minute; când apare un val mare sau un semnal clar, te anunț imediat.")


def heartbeat(hhmm: str, scans: int, last_scan: str, open_n: int, market_open: bool) -> str:
    if not market_open:
        return f"😴 {hhmm}: sunt activ, dar piața e închisă acum. Reiau scanările când se deschide."
    pos = f" Ai {open_n} poziții deschise." if open_n else ""
    return (f"🟢 {hhmm}: sunt activ. De la pornire am făcut {scans} scanări (la fiecare 15 min), ultima la {last_scan}: "
            f"niciun semnal nou.{pos}")


def ro_dt(x):
    """Ora Romaniei (Europe/Bucharest, cu ora de vara/iarna) dintr-un datetime sau text ISO in UTC; None daca nu pot citi."""
    try:
        d = datetime.fromisoformat(x) if isinstance(x, str) else x
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(RO_TZ)
    except (ValueError, TypeError, AttributeError):
        return None


def ro_hm(x) -> str:
    d = ro_dt(x)
    return d.strftime("%H:%M") if d else "?"


def hour_range(bar_iso: str) -> str:
    """'2026-10-09T07:00:00+00:00' (UTC) -> '10:00–11:00' (ora Romaniei; bara dureaza o ora)."""
    d = ro_dt(bar_iso)
    if d is None:
        return str(bar_iso)
    return f"{d:%H:%M}–{(d + timedelta(hours=1)):%H:%M}"


def continued(hours: float) -> str:
    return (f"🔁 Am trecut într-o sesiune nouă (limita GitHub e ~6 ore pe sesiune). Mai sunt {hours:g} ore. Totul rămâne la fel: "
            f"scanez la 15 minute și nu deschid nimic fără OK-ul tău. Pozițiile deschise le-am preluat de pe eToro.")


def handover(remaining: float, open_n: int) -> str:
    return f"🔁 Mă mut într-o sesiune nouă, rămân pornit încă {remaining:g} ore. (Poziții deschise: {open_n}, rămân urmărite.)"


def auto_signal(name: str, side: int, why: str, px: float, digits: int) -> str:
    act = "BUY" if side == 1 else "SELL"
    return f"🤖 Autotrading: {'🟢' if side == 1 else '🔴'} {act} pe {pair(name)} la {px:.{digits}f}. {why[:1].upper() + why[1:]}. Deschid acum."


def confirm_autotrade(max_pos: int, daily_loss: float) -> str:
    return (f"🤖 Pornesc autotrading?\n\nDeschid singur semnalele noi (fără să te mai întreb), cu țintă și plasă puse automat, "
            f"maxim {max_pos} poziții odată. Dacă pierderea realizată azi ajunge la {usd(daily_loss)}, mă opresc singur din deschis.\n"
            f"Îl oprești oricând din același buton.")


def autotrade_on(max_pos: int, daily_loss: float) -> str:
    return (f"🤖✅ Autotrading PORNIT. Deschid singur semnalele (maxim {max_pos} poziții), te anunț la fiecare deschidere și închidere. "
            f"Mă opresc din deschis la pierdere de {usd(daily_loss)} într-o zi. Oprești cu 🤖 Autotrading.")


def autotrade_off() -> str:
    return "🤖⏸️ Autotrading OPRIT. De acum te întreb din nou la fiecare semnal. Pozițiile deschise rămân urmărite."


def profit_lock(day_pnl: float, lock: float) -> str:
    return (f"🔒 Profit bun azi: {usd(day_pnl)} realizat (țintă {usd(lock)}). Nu mai deschid și nu mai propun nimic până mâine, "
            f"ca să păstrăm câștigul. Pozițiile deschise își păstrează ținta și plasa. Dacă vrei, deschizi tu manual.")


def news_ahead(events: list[dict], before_min: int, after_min: int, held: list[str]) -> str:
    """Anunt cu ~1 ora inainte de evenimentele importante (ora Romaniei), cu pauza de semnale pe monedele afectate."""
    lines = [f"• {ro_hm(e['time'])} – {e['title']} ({e['cur']})" for e in events]
    txt = ("🗓️ Știri importante în curând (ora României):\n" + "\n".join(lines) +
           f"\n⏸️ Pe monedele afectate nu propun și nu deschid nimic de la {before_min} min înainte până la {after_min} min după eveniment, "
           f"fiindcă piața sare imprevizibil.")
    if held:
        txt += f"\n⚠️ Ai deja poziții deschise pe: {', '.join(pair(n) for n in held)}. Se pot mișca puternic la știre."
    return txt


def autotrade_limit(daily_loss: float) -> str:
    return (f"🤖🛑 Am oprit autotrading: pierderea realizată azi a ajuns la {usd(daily_loss)}. "
            f"Nu mai deschid singur nimic azi. Dacă vrei, îl pornești din nou din meniu.")


def hold_alert(name: str, hours: int, pnl: float, adv: dict | None = None) -> str:
    return (f"⏱️ {pair(name)} e deschisă de ≈{hours} ore și nu și-a atins încă ținta (acum {signed(pnl)}).{advice_block(adv)}\n"
            f"Vrei s-o închizi tu, sau o las să-și vadă de țintă?")
