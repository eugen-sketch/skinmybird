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
            f"👛 Buget de lucru: {usd(budget)} · " + ("Rulez fără limită de timp, mă relansez singur (mă oprești cu ⛔ Oprește)" if hours <= 0
                                                       else f"Sesiune: {hours:g} ore (apoi mă opresc singur)") + "\n\n"
            f"👇 Folosește butoanele din meniul de sub căsuța de scris.")


HELP = ("🤖 Ce pot face (butoanele din meniul de jos fac același lucru):\n"
        "• 📊 Status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• 🔎 Caută semnale – scanez piața chiar acum\n"
        "• 🔒 Închide tot – îți cer o confirmare, apoi închid toate pozițiile\n"
        "• ⛔ Oprește – îți cer o confirmare, apoi mă opresc\n"
        "• Deschidere manuală: scrie «vinde nzdusd», «cumpără eurusd», «vinde aur», «cumpără dax» – calculez suma din banii liberi și te întreb OK/NU\n"
        "• «preia nzdusd» – dacă ai deschis o poziție direct în eToro și vrei s-o urmăresc eu\n"
        "• 🤖 Autotrading – pornești/oprești deschiderea automată a semnalelor (doar tu o pornești; limită de pierdere pe zi)\n"
        "• ▶️ Pornește – când sunt oprit, mă pornești de aici (apoi merg fără oprire: la câteva ore repornesc singur și preiau tot, până apeși ⛔ Oprește)\n\n"
        "Cele scrise de mână:\n"
        "• /status – pozițiile deschise și cât câștigi/pierzi acum\n"
        "• /inchide tot – închid toate pozițiile\n"
        "• /raport – raportul zilei (câștig azi + total de la început); vine singur cu ~30 min înainte de închiderea pieței\n"
        "• decizii – socoteala deciziilor tale pe ultimele 7 zile (ce ai închis/deschis/refuzat tu, față de botul lăsat singur); vine singur vineri seara\n"
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
             + advice_block(r.get("advice"), short=True) for r in rows]
    icon = "📈" if total >= 0 else "📉"
    return ("📊 Pozițiile deschise acum:\n" + "\n".join(lines) + f"\n\n{icon} Total acum: {signed(total)}\n"
            f"👛 Buget liber: {usd(free)} din {usd(budget)}\n\n{profit}{tail}")


VERDICT = {"TINE": "✋ ȚINE-O", "INCHIDE": "🔒 ÎNCHIDE-O", "ATENTIE": "⚠️ ATENȚIE", "NOU": "🆕 DESCHISĂ ACUM"}


def advice_block(adv: dict | None, short: bool = False) -> str:
    """Sfatul pentru o pozitie, pe scurt si pe intelesul tuturor (fara grafice). short=True (in Status): doar verdictul si motivul principal."""
    if not adv:
        return ""
    if short and adv.get("verdict") != "NOU":
        why = (adv.get("reasons") or [""])[0]
        extra = f" · {min(100, adv['to_tp'] * 100):.0f}% spre țintă" if adv.get("to_tp") else ""
        return f"\n   👉 {VERDICT.get(adv['verdict'], adv['verdict'])}" + (f" — {why}" if why else "") + extra
    if adv.get("verdict") == "NOU":                       # sub ~15 min: fara verdict, doar cum stau lucrurile
        return "\n   🆕 " + "; ".join(adv.get("reasons", []))
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


def money_moved(delta: float, equity: float) -> str:
    if delta > 0:
        return (f"💰 Au intrat bani noi în cont: aproximativ {signed(delta)}. Buget de lucru acum: {usd(equity)}. "
                f"Mărimea pozițiilor și limitele se adaptează singure.")
    return (f"💸 Au ieșit bani din cont: aproximativ {signed(delta)}. Buget de lucru acum: {usd(equity)}. "
            f"Mărimea pozițiilor și limitele se adaptează singure.")


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
    if kind == "SL_GAP":
        return (f"😕🛡️ {p}: s-a activat plasa de siguranță, dar prețul a sărit peste ea (de obicei la redeschiderea pieței după weekend "
                f"sau la o știre), așa că eToro a închis la primul preț disponibil. Rezultat ≈ {signed(pnl)}. Poziția e închisă.")
    if kind == "TIME":
        return f"⏱️ {p}: era pe plus după limita de timp, am încasat profitul. Rezultat ≈ {signed(pnl)}. Poziția e închisă."
    if kind == "BASKET":
        return f"🎯 {p}: închisă împreună cu celelalte. Rezultat {signed(pnl)}."
    if kind == "YOU":
        return f"✋ {p}: am închis la cererea ta. Rezultat ≈ {signed(pnl)}."
    return (f"👋 {p}: poziția s-a închis în afara țintei și a plasei (nu am închis-o eu). Rezultat {signed(pnl)}.\n"
            f"Dacă nu ai închis-o tu din eToro, spune-mi ca să verific.")


def basket(n: int, total: float, left_red: int = 0) -> str:
    rest = f" Cele {left_red} aflate pe minus rămân deschise (nu închid niciodată pe minus), până la țintă sau plasă." if left_red else ""
    return f"🎯💵 Țintă comună atinsă! Cele {n} poziții pe plus fac ≈ {signed(total)}. Le închid acum.{rest}"


def gate_reason(code: str, detail: str, g: dict) -> str:
    """De ce un semnal NU e socotit semnal (apare la «Caută semnale», la instrumentul respectiv)."""
    lo, hi = g.get("hours_utc", [0, 24])
    if code == "regula":
        return f"semnal respins: regula {detail} pierde cel mai des"
    if code == "ora":
        return f"semnal respins: în afara orelor bune ({ro_hm(_utc_today(lo))}–{ro_hm(_utc_today(hi))} ora României)"
    if code == "adx":
        return f"semnal respins: piața n-are direcție clară (ADX {detail}, minim {g.get('adx_min', 0)})"
    return f"semnal respins: piață prea liniștită ({detail}% din mișcările obișnuite)"


def _utc_today(hour: int) -> datetime:
    n = datetime.now(timezone.utc)
    return n.replace(hour=hour % 24, minute=0, second=0, microsecond=0)


def gate_ok(s: dict) -> str:
    """O linie care spune clar ca semnalul a trecut verificarile."""
    bits = []
    if s.get("bar_hour") is not None:
        bits.append("în orele bune")
    if s.get("adx") is not None:
        bits.append(f"mișcare clară (ADX {s['adx']:.0f})")
    if s.get("vol_rank") is not None:
        bits.append("piață activă")
    return "✅ Semnal verificat: " + ", ".join(bits)


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


def scan_report(rows: list[dict], took: float | None = None, active: list[dict] | None = None, gate: dict | None = None) -> str:
    """Raportul de la «Caută semnale»: o linie cu cifre pentru fiecare instrument (petrolul primul), verificarile la vedere, coerent cu semnalele active.
    rows: name, price, rsi, rsi_live, adx, trend, thr (prag RSI), rsi_rule, note, skip. active: semnale propuse recent (name, side, until, status)."""
    arrow = {"sus": "↗️", "jos": "↘️", "lateral": "↔️"}
    g = gate or {}
    active = active or []
    act_names = {a["name"] for a in active}
    scanned = [r for r in rows if not r.get("skip") and not r.get("note") and r["name"] not in act_names]
    other = [r for r in rows if (r.get("skip") or r.get("note")) and r["name"] not in act_names]
    bar = next((r["bar"] for r in rows if not r.get("skip") and r.get("bar") not in (None, "?")), "?")
    n_ok = len([r for r in rows if not r.get("skip")])
    out = [f"🔎 Scanare {ro_hm(datetime.now(timezone.utc))}: am descărcat date noi pentru {n_ok} instrumente"
           + (f" în {took:.0f} s" if took is not None else "") + f" (ultima oră încheiată: {bar})."]
    if active:
        out.append("📌 Semnale active acum:")
        for a in active:
            act = "CUMPĂR" if a["side"] == 1 else "VÂND"
            out.append(f"• {pair(a['name']).split(' ')[0]} — {act} (valabil până la {ro_hm(a['until'])}): {a['status']}")

    def line(r: dict) -> str:
        nm = "Petrol" if r["name"] == "OIL" else pair(r["name"]).split(" ")[0]
        px = f"{r['price']:g}" if r.get("price") else "?"
        live = f" (acum {r['rsi_live']:.0f})" if r.get("rsi_live") is not None and abs(r["rsi_live"] - r["rsi"]) >= 1 else ""
        adx = ""
        if r.get("adx") is not None and g.get("adx_min"):
            adx = f" · ADX {r['adx']:.0f}{'✓' if r['adx'] >= g['adx_min'] else '✗'}"
        return f"{'🛢️' if r['name'] == 'OIL' else '•'} {nm}: {px} · RSI {r['rsi']:.0f}{live} · {arrow.get(r.get('trend'), '')}{adx} · fără semnal"
    if scanned:
        scanned = sorted(scanned, key=lambda r: r["name"] != "OIL")
        out.append("Ce văd acum (preț · RSI · trend orar" + (f" · ADX, minim {g['adx_min']}" if g.get("adx_min") else "") + "):")
        out += [line(r) for r in scanned]
    if other:
        out.append("Nu scanez / respinse: " + "; ".join((("Petrol" if r["name"] == "OIL" else pair(r["name"]).split(" ")[0]) + (f" ({r['note']})" if r.get("note") else "")) for r in other))
    near = sorted((r for r in scanned if r.get("rsi_rule", True)),
                  key=lambda r: min(abs(r["rsi"] - r["thr"]), abs(r["rsi"] - (100 - r["thr"]))))
    if near and not active:
        n = near[0]
        side = "BUY" if n["rsi"] < 50 else "SELL"
        in_zone = n["rsi"] <= n["thr"] if side == "BUY" else n["rsi"] >= 100 - n["thr"]
        nm = pair(n["name"]).split(" ")[0]
        if in_zone:
            out.append(f"🎯 Cel mai aproape: {nm}: RSI {n['rsi']:.0f} e deja în zona de {side}, dar semnalul apare doar când RSI-ul INTRĂ în zonă, nu cât stă în ea.")
        else:
            out.append(f"🎯 Cel mai aproape: {nm} (RSI {n['rsi']:.0f}), devine {side} {'sub ' + str(n['thr']) if side == 'BUY' else 'peste ' + str(100 - n['thr'])}.")
    if active:
        sides = "; ".join(f"{'BUY' if a['side'] == 1 else 'SELL'} {pair(a['name']).split(' ')[0]}" for a in active)
        out.append(f"👉 Recomandare acum: {sides} (semnalele de mai sus încă valabile).")
    else:
        out.append("👉 Recomandare acum: HOLD ⏸️ — am verificat toate regulile pe datele de acum și niciuna nu s-a declanșat.")
    ticks = [r["tick"] for r in rows if r.get("tick")]
    if ticks:
        out.append(f"⏱️ ultima cotație văzută: {ro_hm(max(ticks))}")
    return NL.join(out)


NL = chr(10)


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


def stocks_monthly(day, close: float, ma: float, n: int, fund: str) -> str:
    """Verdictul lunar pentru planul pe actiuni: doar informatie, ordinele le pune Eugen."""
    d = day.strftime("%d.%m.%Y")
    head = (f"📈 Fondul Nasdaq, verificarea lunară (eu nu pun niciun ordin).\nLa închiderea din {d}, Nasdaq-100 (prețul fondului QQQ) a fost {usd(close)}, "
            f"iar media pe {n} de zile {usd(ma)}: ")
    if close > ma:
        return (head + f"PESTE medie ({(close / ma - 1) * 100:+.1f}%).\n✅ Regula zice: ȚII fondul. Dacă ești pe bani, CUMPERI.\n"
                f"Fondul pe eToro: {fund}, în orele bursei din Londra.")
    return (head + f"SUB medie ({(close / ma - 1) * 100:+.1f}%).\n🔻 Regula zice: VINZI tot fondul, chiar dacă e pe minus (cum ai hotărât), "
            f"și stai pe bani până la prima lună în care revine peste medie.\nFondul pe eToro: {fund}, în orele bursei din Londra.")


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
    return (f"🔁 Am trecut într-o sesiune nouă (limita GitHub e ~6 ore pe sesiune). "
            + ("Rulez fără limită de timp. " if hours <= 0 else f"Mai sunt {hours:g} ore. ") + "Totul rămâne la fel: "
            f"scanez la 15 minute și nu deschid nimic fără OK-ul tău. Pozițiile deschise le-am preluat de pe eToro.")


def handover(remaining: float, open_n: int) -> str:
    stay = "rămân pornit, fără limită de timp" if remaining <= 0 or remaining == float("inf") else f"rămân pornit încă {remaining:g} ore"
    return f"🔁 Mă mut într-o sesiune nouă, {stay}. (Poziții deschise: {open_n}, rămân urmărite.)"


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
    if pnl < 0:
        return (f"⏱️ {pair(name)} e deschisă de ≈{hours} ore, acum pe minus ({signed(pnl)}).{advice_block(adv)}\n"
                f"Nu o închid pe minus (regula mea). Rămâne până la țintă sau plasa de siguranță; dacă vrei, o închizi tu cu butonul.")
    return (f"⏱️ {pair(name)} e deschisă de ≈{hours} ore și nu și-a atins încă ținta (acum {signed(pnl)}).{advice_block(adv)}\n"
            f"Vrei s-o închizi tu, sau o las să-și vadă de țintă?")


def decisions_report(o: dict, days: int) -> str:
    """Socoteala deciziilor tale pe ultimele zile: ce ai luat tu fata de ce ar fi facut botul singur."""
    lines = [f"🧭 Deciziile tale, ultimele {days} zile (față de ce ar fi făcut botul singur)"]
    lines.append(f"🤖 Lăsate botului: {o['bot_n']} poziții, {signed(o['bot_net'])}")
    if o["you_n"]:
        d = o["you_net"] - o["you_alt"]
        note = f" ({o['you_open']} ar fi încă deschise, socotite la prețul de acum)" if o["you_open"] else ""
        miss = f" Pentru {o['you_miss']} nu am avut prețuri, le-am socotit egal." if o["you_miss"] else ""
        lines.append(f"✋ Închise de tine înainte de țintă sau plasă: {o['you_n']}. Ai luat {signed(o['you_net'])}; "
                     f"dacă le lăsai, ar fi fost {signed(o['you_alt'])}{note}. Diferența: {signed(d)}.{miss}")
    else:
        lines.append("✋ Închise de tine: niciuna.")
    lines.append(f"👆 Deschise de tine: {o['mine_n']} poziții, {signed(o['mine_net'])}" if o["mine_n"] else "👆 Deschise de tine: niciuna.")
    if o["skip_n"]:
        miss = f", {o['skip_miss']} fără prețuri" if o["skip_miss"] else ""
        lines.append(f"🙅 Semnale refuzate sau lăsate să expire: {o['skip_n']}; dacă le deschideai: {signed(o['skip_alt'])}{miss}.")
    e = o["effect"]
    verdict = "te-au ajutat" if e > 0.5 else "te-au costat" if e < -0.5 else "n-au schimbat mare lucru"
    lines.append(f"📌 Pe scurt: deciziile tale {verdict}: {signed(e)} față de botul lăsat singur.")
    lines.append("ℹ️ „Ce-ar fi fost” e calculat din prețurile de 5 minute de după decizia ta, cu ținta, plasa și limita de timp ale poziției.")
    return NL.join(lines)


def account_alarm(eq: float, lim: float) -> str:
    return (f"⚠️ Contul a coborât sub {usd(lim)}: acum {usd(eq)}.\nAm convenit să ne oprim aici și să ne gândim la varianta B "
            f"(poziții făcute astfel încât la plasă să pierzi doar ~2% din cont: mai puțin câștig, mai puțin risc). Nu schimb nimic singur; spune-i lui Helga ce alegi.")


def oil_watch(sig: dict, auto: bool, why_not: str | None) -> str:
    """Avertismentul paznicului de petrol: clar, cu ce s-a intamplat si ce urmeaza."""
    dirw = "URCĂ" if sig["side"] == 1 else "COBOARĂ"
    brk = (f" și a ieșit {'peste maximul' if sig['side'] == 1 else 'sub minimul'} zilei" if sig.get("brk") else "")
    head = (f"🛢️👀 URMĂREȘTE GRAFICUL PETROLULUI!\nPetrolul {dirw} tare: în ultima oră s-a mișcat de {abs(sig['move']):.1f} ori mai mult decât de obicei{brk}. "
            f"Preț acum ≈ {sig['px']:.2f}.")
    if why_not:
        return head + f"\nNu propun intrare acum: {why_not}. Doar te anunț, ca să te uiți la grafic."
    act = ("Autotradingul e pornit: deschid singur, pe poziția minimă (cea mai mică pe care o acceptă eToro), cu plasă de siguranță."
           if auto else "Îți trimit imediat propunerea cu butoane, pe poziția minimă, cu plasă de siguranță. Decizi tu.")
    return head + "\n" + act


def eia_heads_up(t_rel, first_min: int) -> str:
    return (f"🛢️⏰ La {ro_hm(t_rel)} (ora României) apare raportul american de stocuri de petrol. În minutele acelea petrolul poate sări brusc.\n"
            f"Uită-te la graficul petrolului. Proba noastră: la {ro_hm(t_rel + timedelta(minutes=first_min))} îți propun intrarea în direcția în care a fugit "
            f"prețul în primele {first_min} minute, pe poziția minimă, cu plasă de siguranță.")


def eia_skip(reason: str) -> str:
    return f"🛢️ Proba de miercuri: azi nu intru. Motiv: {reason}."


def eia_hour(pnl: float) -> str:
    return (f"🛢️⏱️ Poziția de probă pe petrol (raportul de stocuri) e deschisă de o oră: acum {signed(pnl)}.\n"
            f"Decizi tu dacă o închizi. Eu nu o închid pe minus; ținta și plasa ei rămân pe eToro.")


def oil4h(sig: dict, sl_usd: float, tp_usd: float, why_not: str | None) -> str:
    head = (f"🛢️📈 PETROL PE 4 ORE (proba de o lună): petrolul a trecut peste maximul ultimelor ~5 zile, iar trendul pe zile e în sus. "
            f"Preț ≈ {sig['px']:.2f}.")
    if why_not:
        return head + f"\nNu propun intrare acum: {why_not}. Doar te anunț."
    return (head + f"\nÎți propun o CUMPĂRARE pe poziția minimă: țintă ≈ +{usd(tp_usd)}, plasă de siguranță ≈ −{usd(sl_usd)}. "
            f"Poziția se ține de obicei ~1 zi (fără limita de 5 ore). Nu deschid singur, nici pe autotrading: decizi tu din butoane.")


def scheduled_start(oil_tools: bool = False) -> str:
    return ("⏰ Pornire programată pentru săptămâna care vine: sunt PE MANUAL (autotradingul e oprit; îl pornești doar tu, din 🤖 Autotrading). "
            "Nu deschid nimic fără OK-ul tău." + (" Uneltele de petrol pornite îți trimit propuneri cu butoane." if oil_tools else ""))


def weekend_reason(w: dict) -> str:
    return (f"se apropie închiderea pieței pentru weekend; repornesc singur duminică seara (pe la 22–23, ora României), pe manual. "
            f"Dacă vrei mai devreme, apasă ▶️ Pornește")


def simple_mode(sm: dict) -> str:
    return (f"🎯 Mod simplu: {usd(sm.get('margin_usd', 50))} pe poziție, plasa de siguranță mică (~{usd(sm.get('sl_usd', 0.5))} plus costul de intrare), "
            f"ținta mare ({sm.get('tp_atr', 3):g}× mișcarea obișnuită pe o oră, cel puțin de {sm.get('min_rr', 3):g} ori plasa). "
            f"Fără petrol, fără limita de 5 ore, fără coș comun, fără blocaj de profit. Ținta și plasa stau pe eToro de la deschidere.")
