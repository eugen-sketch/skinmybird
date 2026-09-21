"""Load and list SkinMyBird aircraft profiles from profiles/*.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / "profiles"


@lru_cache(maxsize=1)
def list_profiles() -> list[dict[str, Any]]:
    """Return summary dicts for every profile (sorted by displayName)."""
    if not PROFILES_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
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
            }
        )
    out.sort(key=lambda p: p["displayName"].lower())
    return out


def load_profile(profile_id: str) -> dict[str, Any]:
    """Load full profile JSON by id (filename stem or id field)."""
    # Prefer exact filename match
    direct = PROFILES_DIR / f"{profile_id}.json"
    if direct.is_file():
        return json.loads(direct.read_text(encoding="utf-8"))
    for path in PROFILES_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("id") == profile_id:
            return data
    raise FileNotFoundError(f"Profile not found: {profile_id}")


def clear_cache() -> None:
    list_profiles.cache_clear()
