#!/usr/bin/env python3
"""Pornire de pe Telegram: cand asistentul NU ruleaza si scrii 'pornește' (sau apesi ▶️ Pornește), il pornesc.

Ruleaza din GitHub la cateva minute (workflow launcher.yml). Nu porneste nimic singur: numai la cererea ta,
numai din chat-ul tau. Cat timp asistentul ruleaza, nu face nimic (nu se atinge de Telegram)."""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DEFAULT_HOURS, MAX_HOURS, FRESH_MIN = 0, 72, 60          # implicit 0 = fără limită de timp (se relansează singur până apeși «Oprește»)
TG = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN', '')}"
GH = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY', '')}"
GH_HEAD = {"Authorization": f"Bearer {os.getenv('GH_TOKEN', '')}", "Accept": "application/vnd.github+json"}


def plain(t: str) -> str:
    return t.lower().translate(str.maketrans("îâășț", "iaast"))


def wants_start(text: str) -> bool:
    t = plain(text)
    return "porne" in t or t.startswith("/start") or t.strip() == "start"


def hours_from(text: str) -> int:
    m = re.search(r"\b(\d{1,3})\b", text)
    return max(1, min(MAX_HOURS, int(m.group(1)))) if m else DEFAULT_HOURS


def assistant_running() -> bool:
    r = requests.get(f"{GH}/actions/workflows/assistant.yml/runs", params={"per_page": 5}, headers=GH_HEAD, timeout=30)
    r.raise_for_status()
    return any(x["status"] != "completed" for x in r.json().get("workflow_runs", []))


NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def weekend_cfg() -> dict:
    try:
        return json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8")).get("weekend_pause") or {}
    except Exception:  # noqa: BLE001
        return {}


def scheduled_start(chat: str) -> bool:
    """Pornirea programata (decizia lui Eugen, 18 oct): duminica seara, dupa `start_utc`, timp de `window_min` minute, daca botul nu ruleaza
    si nu a fost pornit/oprit deja de atunci: il pornesc PE MANUAL (autotradingul il porneste doar Eugen). True daca a pornit."""
    w = weekend_cfg()
    now = NOW()
    if not w.get("enabled") or now.weekday() != 6:
        return False
    hh, mm = (int(x) for x in w.get("start_utc", "20:00").split(":"))
    start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if not start <= now < start + timedelta(minutes=w.get("window_min", 90)):
        return False
    r = requests.get(f"{GH}/actions/workflows/assistant.yml/runs", params={"per_page": 5}, headers=GH_HEAD, timeout=30)
    r.raise_for_status()
    for x in r.json().get("workflow_runs", []):
        made = x.get("created_at")
        if x.get("status") != "completed" or (made and datetime.fromisoformat(made.replace("Z", "+00:00")) >= start):
            return False                                       # ruleaza deja sau a fost pornit/oprit de la ora programata: nu ma bag
    d = requests.post(f"{GH}/actions/workflows/assistant.yml/dispatches", headers=GH_HEAD, timeout=30,
                      json={"ref": "master", "inputs": {"hours": "0", "continued": "0", "mode": "real", "aggressive": "true", "scheduled": "1"}})
    if d.status_code == 204:
        send(chat, "⏰ Pornire programată: pornesc asistentul pentru săptămâna care vine, PE MANUAL (autotradingul îl pornești doar tu). "
                   "În 1–2 minute vezi mesajul de pornire.")
        return True
    return False


def send(chat: str, text: str) -> None:
    requests.post(f"{TG}/sendMessage", json={"chat_id": chat, "text": text}, timeout=30)


def main() -> None:
    chat = str(os.getenv("TELEGRAM_CHAT_ID", ""))
    if not chat or assistant_running():
        return
    if scheduled_start(chat):
        return
    r = requests.get(f"{TG}/getUpdates", params={"timeout": 0, "allowed_updates": '["message"]'}, timeout=30)
    ups = r.json().get("result", []) if r.ok else []
    if not ups:
        return
    requests.get(f"{TG}/getUpdates", params={"offset": ups[-1]["update_id"] + 1, "timeout": 0}, timeout=30)   # le marcam citite
    mine = [u["message"] for u in ups if str(u.get("message", {}).get("chat", {}).get("id")) == chat
            and u["message"].get("text") and time.time() - u["message"].get("date", 0) < FRESH_MIN * 60]
    if not mine:
        return
    last_start = next((m for m in reversed(mine) if wants_start(m["text"])), None)
    if last_start is None:
        send(chat, "😴 Asistentul e oprit acum. Apasă ▶️ Pornește (sau scrie «pornește») și îl pornesc în maxim ~15-20 de minute (GitHub rulează verificarea rar). "
                   "Poți scrie și «pornește 24» ca să rămână pornit 24 de ore.")
        return
    hours = hours_from(last_start["text"])
    mode = "demo" if re.search(r"\bdemo\b", plain(last_start["text"])) else "real"          # implicit REAL; demo doar daca scrii «pornește demo»
    d = requests.post(f"{GH}/actions/workflows/assistant.yml/dispatches", headers=GH_HEAD, timeout=30,
                      json={"ref": "master", "inputs": {"hours": str(hours), "continued": "0", "mode": mode,
                                                    "aggressive": "true" if mode == "real" else "false"}})   # ca sesiunea care rulează acum
    if d.status_code == 204:
        send(chat, f"▶️ Am primit. Pornesc asistentul pe contul {'REAL 🔴' if mode == 'real' else 'DEMO'} {'fără limită de timp (se relansează singur, îl oprești cu ⛔ Oprește)' if hours <= 0 else f'pentru {hours} ore'}, în 1–2 minute vezi mesajul de pornire.")
    else:
        send(chat, f"⚠️ N-am reușit să-l pornesc (cod {d.status_code}). Încearcă din nou peste câteva minute.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - nu vrem rulari "esuate" care trimit emailuri
        print(f"launcher: {type(e).__name__}")
    sys.exit(0)
