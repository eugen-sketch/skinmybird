"""Mesajele Telegram, pe limbaj omenesc, cu iconuri."""
from __future__ import annotations

import random


def pair(name: str) -> str:
    return f"{name[:3]}/{name[3:]}" if len(name) == 6 and name.isalpha() else name


def usd(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def why_signal(reasons: list[str], side: int, rsi: float) -> str:
    out = []
    for r in reasons:
        if r == "london_breakout":
            out.append("a spart intervalul din noaptea asiatică, acum la deschiderea Londrei 🇬🇧")
        elif r.startswith("rsi_rev"):
            out.append(("a căzut prea tare într-un timp scurt" if side == 1 else "a urcat prea tare într-un timp scurt")
                       + f" (RSI {rsi:.0f}), mă aștept la o revenire")
    return "; ".join(out) or "semnal tehnic clar"


def sending(name: str, side: int, why: str) -> str:
    return (f"👀 Văd ceva pe {pair(name)}: {why}.\n"
            f"📤 Trimit acum ordinul de {'cumpărare' if side == 1 else 'vânzare'} pe eToro demo…")


def opened(name: str, side: int, px: float, digits: int, amount: float, lev: int, notional: float,
           sl: float, tp: float, risk: float, gain: float, hours: int, eq: float, paper: bool) -> str:
    head = (f"🟢🛒 Am cumpărat {pair(name)}\nMizez că urcă, am intrat la {px:.{digits}f}."
            if side == 1 else
            f"🔴📉 Am vândut {pair(name)} (short)\nMizez că scade, am intrat la {px:.{digits}f}.")
    return (f"{head}\n\n"
            f"💰 Am băgat {usd(amount)} din cont (levier {lev}, ca și cum aș avea {usd(notional)} în piață)\n"
            f"🎯 Dacă ajunge la {tp:.{digits}f} încasez ≈ {usd(gain)}\n"
            f"🛡️ Dacă merge invers și ajunge la {sl:.{digits}f}, pierd ≈ {usd(risk)} și ies automat\n"
            f"⏳ Dacă nu se întâmplă nimic, ies oricum în {hours} ore\n"
            f"👛 Cont virtual: {usd(eq)}{'  🧪 (simulare)' if paper else ''}")


def closed(name: str, kind: str, res: float, eq: float, start: float, hours: int) -> str:
    p = pair(name)
    bal = f"👛 Cont virtual: {usd(eq)} (am pornit de la {usd(start)})"
    if kind == "TP":
        return f"🎉💵 Am încasat pe {p}! Ținta a fost atinsă.\nCâștig: +{usd(res)}. Poziția e închisă.\n{bal}"
    if kind == "SL":
        return f"😕🛡️ Pe {p} piața a mers invers și s-a activat plasa de siguranță.\nPierdere: {usd(res)}. Poziția e închisă, trec mai departe.\n{bal}"
    sign = "+" if res >= 0 else ""
    icon = "👍" if res >= 0 else "🤷"
    return f"⏰{icon} Au trecut {hours} ore pe {p} fără nicio mișcare decisivă, am închis la piață.\nRezultat: {sign}{usd(res)}.\n{bal}"


def skipped(name: str, side: int, used: float, budget: float) -> str:
    return (f"🙈 Am văzut un semnal de {'cumpărare' if side == 1 else 'vânzare'} pe {pair(name)}, "
            f"dar toți banii sunt deja puși în alte tranzacții ({usd(used)} din {usd(budget)}). Aștept să se elibereze un loc.")


def summary(n: int, wins: int, pf: float, eq: float, start: float) -> str:
    tail = "📈" if eq >= start else "📉"
    return (f"📊 Bilanț până acum: {n} tranzacții închise, {wins} câștigate, {n - wins} pierdute.\n"
            f"{tail} Cont virtual: {usd(eq)} (am pornit de la {usd(start)})")


def error(msg: str) -> str:
    return f"⚠️🔧 Am o problemă tehnică și nu pot lucra normal acum.\nDetalii: {msg}\nÎncerc din nou automat, nu trebuie să faci nimic."


# ------------------------------------------------------------------ mod zilnic (indici)
INDEX_NAMES = {"SP500": "S&P 500 🇺🇸", "NASDAQ": "Nasdaq 100 🇺🇸", "DOW": "Dow Jones 🇺🇸", "DAX": "DAX 🇩🇪", "FTSE": "FTSE 100 🇬🇧"}


def idx(name: str) -> str:
    return INDEX_NAMES.get(name, name)


def daily_opened(name: str, px: float, digits: int, amount: float, lev: int, notional: float, sl: float, risk: float,
                 rsi2: float, exit_rsi: int, max_days: int, eq: float, paper: bool) -> str:
    return (f"🟢🛒 Am cumpărat {idx(name)}\n"
            f"Indicele a scăzut brusc într-o piață care altfel urcă (RSI {rsi2:.0f}), iar de obicei revine în câteva zile. Am intrat la {px:.{digits}f}.\n\n"
            f"💰 Am băgat {usd(amount)} din cont (levier {lev}, ca și cum aș avea {usd(notional)} în piață)\n"
            f"🎯 Vând când își revine (RSI peste {exit_rsi}), de obicei în 2–4 zile\n"
            f"🛡️ Plasă de siguranță la {sl:.{digits}f}: dacă ajunge acolo, pierd ≈ {usd(risk)} și ies automat\n"
            f"⏳ Dacă nu revine, ies oricum în {max_days} zile\n"
            f"👛 Cont virtual: {usd(eq)}{'  🧪 (simulare)' if paper else ''}")


def daily_closed(name: str, kind: str, res: float, eq: float, start: float, days: float) -> str:
    bal = f"👛 Cont virtual: {usd(eq)} (am pornit de la {usd(start)})"
    d = f"{days:.0f}" if days >= 1 else "mai puțin de o zi"
    if kind == "SL":
        return f"😕🛡️ Pe {idx(name)} piața a scăzut în continuare și s-a activat plasa de siguranță.\nPierdere: {usd(res)}. Poziția e închisă după {d} zile.\n{bal}"
    why = "și-a revenit, am vândut ✅" if kind == "RECOVERED" else "n-a revenit în timp, am închis la piață ⏰"
    icon = "🎉💵" if res > 0 else "🤷"
    sign = "+" if res >= 0 else ""
    return f"{icon} {idx(name)} {why}\nRezultat: {sign}{usd(res)} după {d} zile. Poziția e închisă.\n{bal}"
