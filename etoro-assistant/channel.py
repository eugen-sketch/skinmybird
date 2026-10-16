"""Jurnal CRIPTAT al botului (Fernet: AES + semnatura), pentru ca Helga sa poata vedea ce a trimis botul pe Telegram, fara sa-l faca public.

Cheia (HELGA_KEY) e in GitHub Secrets si pe PC-ul lui Eugen, niciodata in repo. Fiecare mesaj trimis pe Telegram si fiecare buton apasat intra in
`journal.enc` (un token criptat pe linie). Fisierul se urca la sfarsitul sesiunii ca artefact; fara cheie continutul nu se poate citi.
Fara cheie sau fara biblioteca `cryptography`: jurnalul e oprit si botul merge exact ca inainte. Nicio eroare de aici nu opreste botul."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except Exception:  # noqa: BLE001 - fara biblioteca: functiile de criptare sunt oprite
    Fernet = None

MAX_BYTES = 1_500_000


def fernet(key: str | bytes | None = None):
    """Obiectul de criptare din cheia data sau din HELGA_KEY; None daca nu avem cheie valida / biblioteca."""
    key = key or os.getenv("HELGA_KEY", "")
    if not (Fernet and key):
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:  # noqa: BLE001
        return None


def encrypt(obj, key=None) -> str | None:
    f = fernet(key)
    return f.encrypt(json.dumps(obj, ensure_ascii=False).encode()).decode() if f else None


def decrypt(token: str, key=None, ttl: int | None = None):
    """Obiectul din token, sau None daca cheia nu se potriveste / token modificat / prea vechi."""
    f = fernet(key)
    if not f:
        return None
    try:
        return json.loads(f.decrypt(token.strip().encode(), ttl=ttl))
    except Exception:  # noqa: BLE001
        return None


class Journal:
    def __init__(self, path: Path | str, key=None):
        self.path = Path(path)
        self.f = fernet(key)
        self.enabled = self.f is not None

    def add(self, kind: str, text: str = "", **extra) -> None:
        if not self.enabled:
            return
        try:
            obj = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "k": kind, "x": text, **{k: v for k, v in extra.items() if v}}
            line = self.f.encrypt(json.dumps(obj, ensure_ascii=False).encode()).decode()
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            if self.path.stat().st_size > MAX_BYTES:                       # nu lasam fisierul sa creasca la nesfarsit: pastram jumatatea noua
                lines = self.path.read_text(encoding="utf-8").splitlines()
                self.path.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
        except Exception:  # noqa: BLE001 - jurnalul nu are voie sa opreasca botul
            pass

    def on_telegram(self, kind: str, text: str, buttons=None) -> None:
        """Legatura cu Telegram: «out» = mesaj trimis, «photo» = grafic, «in» = ce ai scris/apasat tu."""
        self.add(kind, text, buttons=[[b[0] for b in row] for row in buttons] if buttons else None)


def read(path: Path | str, key=None) -> list[dict]:
    """Citeste si decripteaza un jurnal (folosit de Helga, local, cu HELGA_KEY de pe PC)."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        obj = decrypt(line, key)
        if obj is not None:
            out.append(obj)
    return out


def from_env(path: Path | str) -> Journal | None:
    j = Journal(path)
    return j if j.enabled else None
