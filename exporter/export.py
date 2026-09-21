#!/usr/bin/env python3
"""
SkinMyBird exporter — generate an MSFS 2020 Community package
(variation of Asobo A320neo) from a livery config JSON.

ASSUMPTIONS / LIMITATIONS (v0):
- Textures are PLACEHOLDER PNG albedo maps (flat zone colors + simple stickers).
  Real DDS (BC7/DXT5 via texconv) + official Asobo paintkit UV layout comes next.
- Texture filenames follow community-documented Asobo A320neo names:
  A320NEO_AIRFRAME_{FUSELAGE,WINGS,ENGINES,LIVERY,LIVERY_TEXTS}_ALBD
- Tail color is painted onto the aft fuselage / vertical stabilizer region of the
  fuselage placeholder (real UV has rudder split across fuselage+wings).
- base_container = "..\\Asobo_A320_NEO" (default Asobo path in Official content).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow required. Activate .venv and: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output"

# Placeholder texture sizes — real paintkit is typically 4K/8K; v0 uses 1024 for speed.
TEX_SIZE = 1024

TEXTURE_FILES = [
    "A320NEO_AIRFRAME_FUSELAGE_ALBD.png",
    "A320NEO_AIRFRAME_WINGS_ALBD.png",
    "A320NEO_AIRFRAME_ENGINES_ALBD.png",
    "A320NEO_AIRFRAME_LIVERY_ALBD.png",
    "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png",
]


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "livery"


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def load_config(path: Path | None, preset: str | None) -> dict[str, Any]:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    if preset:
        p = ROOT / "presets" / f"{preset}.json"
        if not p.exists():
            raise FileNotFoundError(f"Preset not found: {p}")
        return json.loads(p.read_text(encoding="utf-8"))
    raise ValueError("Provide --config or --preset")


def make_fuselage(colors: dict, stickers: list, registration: str, photo_path: Path | None) -> Image.Image:
    """Simplified UV mock: left = port side, right = starboard; aft band = tail."""
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (*hex_to_rgb(colors["fuselage"]), 255))
    draw = ImageDraw.Draw(img)
    # Tail / vertical stab region (aft ~18% of width) — ASSUMPTION for placeholder UV
    tail = (*hex_to_rgb(colors["tail"]), 255)
    tw = int(TEX_SIZE * 0.18)
    draw.rectangle([TEX_SIZE - tw, 0, TEX_SIZE, TEX_SIZE], fill=tail)
    # Nose highlight
    draw.ellipse([-80, TEX_SIZE // 3, 120, 2 * TEX_SIZE // 3], fill=(255, 255, 255, 40))
    # Windows row
    for i in range(12):
        x = 180 + i * 55
        draw.rounded_rectangle([x, TEX_SIZE // 2 - 18, x + 36, TEX_SIZE // 2 + 8], radius=6, fill=(30, 40, 60, 220))

    for st in stickers:
        if not st.get("enabled"):
            continue
        t = st.get("type")
        if t == "team_stripe":
            y = TEX_SIZE // 2 + 40
            draw.rectangle([80, y, TEX_SIZE - tw - 20, y + 28], fill=(255, 255, 255, 230))
            draw.rectangle([80, y + 28, TEX_SIZE - tw - 20, y + 48], fill=(*hex_to_rgb(colors["tail"]), 255))
        elif t == "heart":
            cx, cy = TEX_SIZE // 3, TEX_SIZE // 3
            draw.ellipse([cx - 40, cy - 30, cx, cy + 10], fill=(220, 40, 60, 255))
            draw.ellipse([cx, cy - 30, cx + 40, cy + 10], fill=(220, 40, 60, 255))
            draw.polygon([(cx - 45, cy), (cx + 45, cy), (cx, cy + 55)], fill=(220, 40, 60, 255))
        elif t == "custom_text":
            text = st.get("text") or registration
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            except OSError:
                font = ImageFont.load_default()
            draw.text((200, 120), text, fill=(255, 255, 255, 255), font=font)

    if photo_path and photo_path.exists():
        try:
            photo = Image.open(photo_path).convert("RGBA")
            photo.thumbnail((180, 180))
            # "Soacră photo" decal — mid-fuselage UV approx
            img.paste(photo, (TEX_SIZE // 2 - 90, TEX_SIZE // 2 + 80), photo)
        except OSError as e:
            print(f"Warning: could not place photo: {e}", file=sys.stderr)

    return img


def make_solid(color: str, label: str) -> Image.Image:
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (*hex_to_rgb(color), 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    draw.text((24, 24), f"SkinMyBird placeholder\n{label}", fill=(255, 255, 255, 180), font=font)
    # Panel lines for visual interest
    for i in range(0, TEX_SIZE, 128):
        draw.line([(i, 0), (i, TEX_SIZE)], fill=(0, 0, 0, 40), width=1)
        draw.line([(0, i), (TEX_SIZE, i)], fill=(0, 0, 0, 40), width=1)
    return img


def make_livery_layer(stickers: list, registration: str) -> Image.Image:
    """Transparent livery/decal layer (alpha)."""
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for st in stickers:
        if st.get("enabled") and st.get("type") == "heart":
            cx, cy = TEX_SIZE // 2, TEX_SIZE // 2
            draw.ellipse([cx - 50, cy - 40, cx, cy + 10], fill=(220, 40, 60, 255))
            draw.ellipse([cx, cy - 40, cx + 50, cy + 10], fill=(220, 40, 60, 255))
            draw.polygon([(cx - 55, cy), (cx + 55, cy), (cx, cy + 70)], fill=(220, 40, 60, 255))
    return img


def make_texts_layer(registration: str) -> Image.Image:
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    draw.text((64, TEX_SIZE // 2 - 32), registration, fill=(255, 255, 255, 255), font=font)
    return img


def aircraft_cfg(cfg: dict, texture_folder: str, unique_title: str) -> str:
    reg = cfg.get("registration", "SMB-001")
    airline = cfg.get("airline", "SkinMyBird")
    icao = cfg.get("icao", "SMB")
    name = cfg.get("name", "Custom")
    return f"""[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\\\Asobo_A320_NEO"

; SkinMyBird generated variation — ASSUMPTION: Asobo_A320_NEO is the Official folder name.
[FLTSIM.0]
title = "{unique_title}"
model = ""
panel = ""
sound = ""
texture = "{texture_folder}"
kb_checklists = ""
kb_reference = ""
description = "SkinMyBird custom A320neo livery — {name}. Placeholder PNG textures (convert to DDS next)."
wip_indicator = 0
ui_manufacturer = "Airbus"
ui_type = "A320neo"
ui_variation = "{name}"
ui_typerole = "Commercial Airliner"
ui_createdby = "SkinMyBird"
atc_id = "{reg}"
atc_airline = "{airline}"
atc_flight_number = "1"
icao_airline = "{icao}"
isAirTraffic = 0
isUserSelectable = 1
"""


def texture_cfg() -> str:
    return """[fltsim]
fallback.1=..\\..\\Asobo_A320_NEO\\texture
fallback.2=..\\..\\..\\..\\texture\\DetailMap
fallback.3=..\\..\\..\\..\\texture\\Glass
fallback.4=..\\..\\..\\..\\texture\\Interiors
fallback.5=..\\..\\..\\..\\texture
fallback.6=..\\..\\..\\..\\texture\\Livery
fallback.7=..\\..\\..\\..\\texture\\Planes_Generic
"""


def manifest_json(cfg: dict, package_title: str) -> dict:
    return {
        "dependencies": [],
        "content_type": "AIRCRAFT",
        "title": package_title,
        "manufacturer": "Airbus",
        "creator": "SkinMyBird",
        "package_version": "0.1.0",
        "minimum_game_version": "1.7.12",
        "release_notes": {
            "neutral": {
                "LastUpdate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "OlderHistory": "SkinMyBird MVP placeholder textures (PNG). Convert to DDS before flight.",
            }
        },
    }


def build_layout(package_root: Path) -> dict:
    """Build layout.json with relative paths, sizes, and dates (MSFS format)."""
    entries = []
    for path in sorted(package_root.rglob("*")):
        if path.is_file() and path.name != "layout.json":
            rel = path.relative_to(package_root).as_posix()
            st = path.stat()
            # MSFS uses FILETIME-like date; tools often use Unix*10M or similar.
            # Community convention: integer size + date as Windows FILETIME or unix.
            # We'll use a widely accepted form: size + date (unix seconds * 10000000 + epoch offset approximated)
            # Many generators use: date = int((mtime + 11644473600) * 10000000)
            date = int((st.st_mtime + 11644473600) * 10000000)
            entries.append({"path": rel, "size": st.st_size, "date": date})
    return {"content": entries}


def readme_ro(cfg: dict, package_folder: str) -> str:
    name = cfg.get("name", "Custom")
    return f"""# SkinMyBird — Instalare livery MSFS 2020

## Ce ai primit
Pachet Community pentru o **variație** a Asobo A320neo: **{name}**.

Folder pachet: `{package_folder}`

## Instalare
1. Copiază întregul folder `{package_folder}` în directorul **Community** al MSFS 2020.
   - Exemplu Steam: `C:\\Users\\<tu>\\AppData\\Roaming\\Microsoft Flight Simulator\\Packages\\Community\\`
   - Exemplu MS Store: `C:\\Users\\<tu>\\AppData\\Local\\Packages\\Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalCache\\Packages\\Community\\`
2. Repornește Microsoft Flight Simulator 2020.
3. Alege Airbus A320neo → livery **{name}** (SkinMyBird).

## IMPORTANT — texturi placeholder
Texturile din acest pachet sunt **PNG placeholder** (culori plate pe zone).
MSFS așteaptă de obicei **DDS**. Pași următori:
1. Obține paintkit-ul oficial / legal A320neo.
2. Convertește PNG → DDS cu **texconv** (DirectXTex), format BC7 sau DXT5 după material.
3. Înlocuiește fișierele din `texture.*` și regenerează `layout.json`.

Până atunci, pachetul apare în meniu, dar texturile pot fi magenta / fallback Asobo.

## Despre SkinMyBird
Instrument comercial one-time **€9.99** — recolorează livery-uri default Asobo și adaugă stickere/poze, apoi exportă pachet Community gata de copiat.

Creat cu SkinMyBird MVP v0.1
"""


def export_package(
    cfg: dict,
    out_dir: Path,
    *,
    zip_out: bool = False,
    photo: Path | None = None,
) -> Path:
    name = cfg.get("name", "Custom")
    slug = slugify(cfg.get("id") or name)
    package_folder = f"skinmybird-a320neo-{slug}"
    aircraft_folder = f"skinmybird_a320neo_{slug}"
    texture_name = slug
    unique_title = f"Airbus A320 Neo SkinMyBird {name}"

    package_root = out_dir / package_folder
    sim_aircraft = package_root / "SimObjects" / "Airplanes" / aircraft_folder
    tex_dir = sim_aircraft / f"texture.{texture_name}"
    tex_dir.mkdir(parents=True, exist_ok=True)

    colors = cfg.get("colors", {})
    stickers = cfg.get("stickers", [])
    registration = cfg.get("registration", "SMB-001")
    photo_path = photo
    if not photo_path and cfg.get("soacraPhoto"):
        photo_path = Path(cfg["soacraPhoto"])

    # Textures
    make_fuselage(colors, stickers, registration, photo_path).save(
        tex_dir / "A320NEO_AIRFRAME_FUSELAGE_ALBD.png"
    )
    make_solid(colors.get("wings", "#111111"), "WINGS").save(
        tex_dir / "A320NEO_AIRFRAME_WINGS_ALBD.png"
    )
    make_solid(colors.get("engines", "#222222"), "ENGINES").save(
        tex_dir / "A320NEO_AIRFRAME_ENGINES_ALBD.png"
    )
    make_livery_layer(stickers, registration).save(
        tex_dir / "A320NEO_AIRFRAME_LIVERY_ALBD.png"
    )
    make_texts_layer(registration).save(
        tex_dir / "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png"
    )
    (tex_dir / "texture.cfg").write_text(texture_cfg(), encoding="utf-8")

    (sim_aircraft / "aircraft.cfg").write_text(
        aircraft_cfg(cfg, texture_name, unique_title), encoding="utf-8"
    )

    package_title = f"SkinMyBird A320neo — {name}"
    (package_root / "manifest.json").write_text(
        json.dumps(manifest_json(cfg, package_title), indent=2), encoding="utf-8"
    )
    (package_root / "README_INSTALL_RO.md").write_text(
        readme_ro(cfg, package_folder), encoding="utf-8"
    )
    # NOTE placeholder
    (tex_dir / "TEXTURES_README.txt").write_text(
        "PLACEHOLDER PNG albedo maps generated by SkinMyBird v0.\n"
        "Replace with DDS from official paintkit + texconv before real flights.\n"
        "See package README_INSTALL_RO.md\n",
        encoding="utf-8",
    )

    layout = build_layout(package_root)
    (package_root / "layout.json").write_text(
        json.dumps(layout, indent=2), encoding="utf-8"
    )

    # Rebuild layout once more so layout.json itself is excluded correctly (already is)
    # and sizes are final — layout is written last so CONTENT doesn't include itself typically;
    # MSFS layout should NOT list layout.json. Good.

    if zip_out:
        zip_path = out_dir / f"{package_folder}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in package_root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(out_dir).as_posix())
        return zip_path

    return package_root


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SkinMyBird MSFS Community package exporter")
    p.add_argument("--config", type=Path, help="Path to livery config JSON")
    p.add_argument("--preset", type=str, help="Preset id (e.g. eugen-orange)")
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    p.add_argument("--zip", action="store_true", help="Also write a .zip next to the folder")
    p.add_argument("--photo", type=Path, help="Optional soacră / decal image path")
    args = p.parse_args(argv)

    cfg = load_config(args.config, args.preset)
    args.out.mkdir(parents=True, exist_ok=True)
    result = export_package(cfg, args.out, zip_out=args.zip, photo=args.photo)
    print(f"OK: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
