"""Starea asistentului intre sesiuni (castig realizat, autotrading, pierderea zilei). Fisierul e ascuns usor (nu text clar),
deoarece GitHub il tine ca artefact intr-un repo public."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

PATH = Path(os.getenv("STATE_FILE", Path(__file__).parent / "state.json"))


def _stream(n: int) -> bytes:
    key = os.getenv("TELEGRAM_BOT_TOKEN", "local").encode()
    out, i = b"", 0
    while len(out) < n:
        out += hashlib.sha256(key + i.to_bytes(4, "big")).digest()
        i += 1
    return out[:n]


def dumps(d: dict) -> str:
    raw = json.dumps(d).encode()
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, _stream(len(raw))))).decode()


def loads(txt: str) -> dict:
    raw = base64.b64decode(txt)
    return json.loads(bytes(a ^ b for a, b in zip(raw, _stream(len(raw)))))


def load(path: Path | None = None) -> dict:
    try:
        return loads((path or PATH).read_text())
    except Exception:  # noqa: BLE001 - fara fisier / fisier stricat: pornim de la zero
        return {}


def save(d: dict, path: Path | None = None) -> None:
    try:
        (path or PATH).write_text(dumps(d))
    except OSError:
        pass
