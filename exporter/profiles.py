"""Load and list SkinMyBird aircraft profiles from profiles/*.json."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "profiles"

# commercial (default): Airbus + Boeing fixed-wing airliners only
# personal: commercial set + helicopter / balloon / GA stub
VALID_EDITIONS = frozenset({"commercial", "personal"})


def get_edition() -> str:
    """Active product edition from SKINMYBIRD_EDITION (default commercial)."""
    raw = (os.environ.get("SKINMYBIRD_EDITION") or "commercial").strip().lower()
    return raw if raw in VALID_EDITIONS else "commercial"


def _profile_allowed(edition_tag: str, active: str) -> bool:
    """commercial profiles always included; personal only when edition=personal."""
    tag = (edition_tag or "commercial").strip().lower()
    if tag == "personal":
        return active == "personal"
    return True  # commercial (or missing) → always shown


def list_profiles() -> list[dict[str, Any]]:
    """Return summary dicts for profiles allowed by SKINMYBIRD_EDITION."""
    return list(_list_profiles_for(get_edition()))


@lru_cache(maxsize=4)
def _list_profiles_for(active: str) -> tuple[dict[str, Any], ...]:
    if not PROFILES_DIR.is_dir():
        return ()
    out: list[dict[str, Any]] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not _profile_allowed(data.get("edition", "commercial"), active):
            continue
        out.append(
            {
                "id": data["id"],
                "displayName": data.get("displayName", data["id"]),
                "category": data.get("category", "avion"),
                "paint_mode": data.get("paint_mode", "whole_albedo"),
                "silhouette": data.get("silhouette", "airliner"),
                "ui_type": data.get("ui_type", ""),
                "ui_manufacturer": data.get("ui_manufacturer", ""),
                "notes": data.get("notes", ""),
                "has_uv": bool(data.get("uv_rects")),
                "texture_count": len(data.get("textures") or []),
                "edition": data.get("edition", "commercial"),
            }
        )
    out.sort(key=lambda p: p["displayName"].lower())
    return tuple(out)


def load_profile(profile_id: str) -> dict[str, Any]:
    """Load full profile JSON by id (filename stem or id field)."""
    direct = PROFILES_DIR / f"{profile_id}.json"
    if direct.is_file():
        data = json.loads(direct.read_text(encoding="utf-8"))
    else:
        data = None
        for path in PROFILES_DIR.glob("*.json"):
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if candidate.get("id") == profile_id:
                data = candidate
                break
        if data is None:
            raise FileNotFoundError(f"Profile not found: {profile_id}")
    active = get_edition()
    if not _profile_allowed(data.get("edition", "commercial"), active):
        raise FileNotFoundError(
            f"Profile not available in {active} edition: {profile_id}"
        )
    return data


def clear_cache() -> None:
    _list_profiles_for.cache_clear()
