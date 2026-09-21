#!/usr/bin/env python3
"""
SkinMyBird exporter — MSFS 2020 Community package from a livery config JSON.

Emits *.PNG.DDS (BC7_UNORM + mips) via wine+texconv when available, plus
Official-style *.PNG.DDS.json sidecars, thumbnails, texture.cfg fallbacks,
layout.json, and optional ZIP. Plain PNGs alone are ignored by MSFS → white/blue.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
TEXCONV_CANDIDATES = [
    Path(os.environ.get("SKINMYBIRD_TEXCONV", "")),
    ROOT / "tools" / "texconv.exe",
    Path("/workspace/tools/texconv.exe"),
    Path.home() / "tools" / "texconv.exe",
]

# 2048² BC7 + mips ≈ 5.5 MB — matches validated Eugen Orange Community package.
TEX_SIZE = 2048

TEXTURE_STEMS = [
    "A320NEO_AIRFRAME_FUSELAGE_ALBD",
    "A320NEO_AIRFRAME_WINGS_ALBD",
    "A320NEO_AIRFRAME_ENGINES_ALBD",
    "A320NEO_AIRFRAME_LIVERY_ALBD",
    "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD",
]


# ---------------------------------------------------------------------------
# Official Asobo A320neo LIVERY_TEXTS UV rects (2048²), measured from
# work/official_ref/A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.PNG.png alpha blobs.
# Titles + logos MUST go here — never fake fuselage-top UV.
# Rects are (x0, y0, x1, y1) inclusive-ish pixel bounds.
# ---------------------------------------------------------------------------
A320NEO_TEXTS_UV = {
    # Tail "neo" logo slots → port + starboard vertical stabilizer
    "neo_logo_band": (95, 14, 1991, 552),
    "neo_logo_upper": (95, 14, 1991, 283),
    "neo_logo_lower": (95, 284, 1991, 552),
    # Fuselage SIDE titles ("AIRBUS A320" / "unbeatable fuel efficiency")
    "side_title_band": (52, 603, 1560, 1031),
    "side_title_upper": (52, 603, 1560, 817),
    "side_title_lower": (52, 818, 1560, 1031),
    # Smaller Official glyph bands — leave empty unless placing registration
    "small_glyph_a": (42, 1062, 1679, 1257),
    "small_glyph_b": (57, 1311, 1640, 1444),
    "reg_slot": (12, 1509, 980, 1672),
    "small_glyph_c": (255, 1777, 784, 1875),
}

# Thumbnail card target (Official Asobo list preview aspect)
ASOBO_THUMB_SIZE = (1618, 582)

DDS_JSON_TEMPLATE = {
    "Version": 2,
    "SourceFileName": "",  # filled per file
    "Flags": ["FL_BITMAP_COMPRESSION", "FL_BITMAP_MIPMAP"],
}


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


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]
        if bold
        else ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]
    )
    for name in names:
        for base in (
            Path("/usr/share/fonts/truetype/dejavu"),
            Path("/usr/share/fonts/TTF"),
            Path("C:/Windows/Fonts"),
        ):
            candidate = base / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    pass
    return ImageFont.load_default()


def make_fuselage(
    colors: dict, stickers: list, registration: str, photo_path: Path | None
) -> Image.Image:
    """Fuselage albedo fill only. Titles/logos go on LIVERY_TEXTS UV (sides/tail), not here."""
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (*hex_to_rgb(colors["fuselage"]), 255))
    draw = ImageDraw.Draw(img)
    tail = (*hex_to_rgb(colors["tail"]), 255)
    tw = int(TEX_SIZE * 0.18)
    draw.rectangle([TEX_SIZE - tw, 0, TEX_SIZE, TEX_SIZE], fill=tail)
    # Soft nose highlight
    draw.ellipse([-160, TEX_SIZE // 3, 240, 2 * TEX_SIZE // 3], fill=(255, 255, 255, 36))
    # Cabin windows
    for i in range(14):
        x = 280 + i * 100
        draw.rounded_rectangle(
            [x, TEX_SIZE // 2 - 28, x + 64, TEX_SIZE // 2 + 14],
            radius=10,
            fill=(30, 40, 60, 220),
        )

    for st in stickers:
        if not st.get("enabled"):
            continue
        t = st.get("type")
        if t == "team_stripe":
            y = TEX_SIZE // 2 + 80
            draw.rectangle([120, y, TEX_SIZE - tw - 40, y + 48], fill=(255, 255, 255, 235))
            draw.rectangle(
                [120, y + 48, TEX_SIZE - tw - 40, y + 84],
                fill=(*hex_to_rgb(colors["tail"]), 255),
            )
        elif t == "heart":
            cx, cy = TEX_SIZE // 3, TEX_SIZE // 3
            draw.ellipse([cx - 70, cy - 50, cx, cy + 20], fill=(220, 40, 60, 255))
            draw.ellipse([cx, cy - 50, cx + 70, cy + 20], fill=(220, 40, 60, 255))
            draw.polygon(
                [(cx - 80, cy), (cx + 80, cy), (cx, cy + 100)],
                fill=(220, 40, 60, 255),
            )
        elif t == "custom_text":
            # Titles belong on LIVERY_TEXTS side UV — painting here lands on the roof/top.
            continue

    if photo_path and photo_path.exists():
        try:
            photo = Image.open(photo_path).convert("RGBA")
            photo.thumbnail((320, 320))
            img.paste(photo, (TEX_SIZE // 2 - 160, TEX_SIZE // 2 + 140), photo)
        except OSError as e:
            print(f"Warning: could not place photo: {e}", file=sys.stderr)

    return img


def make_solid(color: str, label: str) -> Image.Image:
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (*hex_to_rgb(color), 255))
    draw = ImageDraw.Draw(img)
    font = _font(42)
    draw.text((40, 40), f"SkinMyBird\n{label}", fill=(255, 255, 255, 90), font=font)
    for i in range(0, TEX_SIZE, 256):
        draw.line([(i, 0), (i, TEX_SIZE)], fill=(0, 0, 0, 28), width=2)
        draw.line([(0, i), (TEX_SIZE, i)], fill=(0, 0, 0, 28), width=2)
    return img


def make_livery_layer(stickers: list, registration: str) -> Image.Image:
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for st in stickers:
        if st.get("enabled") and st.get("type") == "heart":
            cx, cy = TEX_SIZE // 2, TEX_SIZE // 2
            draw.ellipse([cx - 90, cy - 70, cx, cy + 20], fill=(220, 40, 60, 255))
            draw.ellipse([cx, cy - 70, cx + 90, cy + 20], fill=(220, 40, 60, 255))
            draw.polygon(
                [(cx - 100, cy), (cx + 100, cy), (cx, cy + 130)],
                fill=(220, 40, 60, 255),
            )
    return img


def make_texts_layer(registration: str, airline: str | None = None) -> Image.Image:
    """Paint titles/registration into Official LIVERY_TEXTS UV slots (fuselage SIDES).

    Never place large titles on the fuselage albedo — that maps to the roof/top.
    Tail logos belong in neo_logo_upper/lower; side titles in side_title_*.
    """
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    title = (airline or registration or "SkinMyBird").strip()
    # Side-title UV copies (L/R). Keep text inside measured rects.
    for key, mirror in (("side_title_upper", False), ("side_title_lower", True)):
        x0, y0, x1, y1 = A320NEO_TEXTS_UV[key]
        rw, rh = x1 - x0, y1 - y0
        layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        font = _font(max(28, min(110, rh // 2)), bold=True)
        bbox = ld.textbbox((0, 0), title, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        # shrink if needed
        while tw > rw * 0.92 and font.size > 24:  # type: ignore[attr-defined]
            font = _font(font.size - 4, bold=True)  # type: ignore[attr-defined]
            bbox = ld.textbbox((0, 0), title, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (rw - tw) // 2 - bbox[0]
        ty = (rh - th) // 2 - bbox[1]
        ld.text((tx, ty), title, fill=(255, 255, 255, 255), font=font)
        if mirror:
            from PIL import ImageOps
            layer = ImageOps.mirror(layer)
        img.paste(layer, (x0, y0), layer)
    # Registration in dedicated small slot
    x0, y0, x1, y1 = A320NEO_TEXTS_UV["reg_slot"]
    font = _font(64, bold=True)
    draw.text((x0 + 40, y0 + (y1 - y0) // 3), registration, fill=(255, 255, 255, 240), font=font)
    return img


def make_thumbnails(colors: dict, name: str, registration: str) -> tuple[Image.Image, Image.Image]:
    """Asobo-style list card: 3/4 aircraft on light studio background (not black silhouette).

    MSFS Community list previews match Official cards (~1618x582 light gray studio
    + soft ground shadow). Dark-on-dark graphic silhouettes look wrong next to Asobo.
    """
    W, H = ASOBO_THUMB_SIZE
    # Light studio gradient
    img = Image.new("RGB", (W, H), (210, 212, 216))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        # subtle top→floor gradient
        r = int(225 + (245 - 225) * t)
        g = int(226 + (246 - 226) * t)
        b = int(230 + (248 - 230) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    fus = hex_to_rgb(colors.get("fuselage", "#FF6A00"))
    wing = hex_to_rgb(colors.get("wings", "#111111"))
    eng = hex_to_rgb(colors.get("engines", "#222222"))
    tail = hex_to_rgb(colors.get("tail", "#FF6A00"))

    # Soft ground shadow
    draw.ellipse([int(W * 0.18), int(H * 0.78), int(W * 0.82), int(H * 0.92)], fill=(180, 182, 186))

    # Simplified 3/4 aircraft (nose-right) — readable on light bg
    cx, cy = int(W * 0.52), int(H * 0.52)
    # far wing
    draw.polygon(
        [(cx - 40, cy - 10), (cx - 280, cy - 120), (cx - 250, cy - 95), (cx + 20, cy + 5)],
        fill=wing,
    )
    # fuselage tube
    draw.ellipse([cx - 420, cy - 55, cx - 300, cy + 55], fill=fus)  # nose
    draw.rounded_rectangle([cx - 360, cy - 50, cx + 280, cy + 50], radius=40, fill=fus)
    # near wing + engines
    draw.polygon(
        [(cx - 20, cy + 10), (cx + 260, cy + 70), (cx + 290, cy + 95), (cx - 40, cy + 40)],
        fill=wing,
    )
    draw.rounded_rectangle([cx - 30, cy + 28, cx + 70, cy + 78], radius=18, fill=eng)
    draw.rounded_rectangle([cx + 100, cy + 38, cx + 190, cy + 82], radius=16, fill=eng)
    # cockpit windows
    draw.rounded_rectangle([cx - 340, cy - 38, cx - 270, cy - 8], radius=6, fill=(40, 48, 60))
    for i in range(12):
        x = cx - 230 + i * 36
        draw.rounded_rectangle([x, cy - 22, x + 18, cy - 4], radius=4, fill=(40, 48, 60))
    # vertical stabilizer
    draw.polygon(
        [(cx + 200, cy - 48), (cx + 240, cy - 200), (cx + 320, cy - 200), (cx + 290, cy - 48)],
        fill=tail,
    )
    draw.polygon(
        [(cx + 230, cy - 10), (cx + 400, cy - 30), (cx + 400, cy - 2), (cx + 250, cy + 14)],
        fill=tail,
    )

    font = _font(26, bold=True)
    draw.text((28, 22), f"{name}  ·  {registration}", fill=(50, 54, 62), font=font)
    draw.text((28, H - 40), "SkinMyBird", fill=(110, 118, 130), font=_font(18))

    small = img.resize((256, 144), Image.Resampling.LANCZOS)
    return img, small


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

; SkinMyBird generated variation — base_container assumes Official Asobo_A320_NEO.
[FLTSIM.0]
title = "{unique_title}"
model = ""
panel = ""
sound = ""
texture = "{texture_folder}"
kb_checklists = ""
kb_reference = ""
description = "SkinMyBird custom A320neo livery — {name}. BC7 DDS albedo textures."
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
    # Match validated in-game Eugen Orange package fallbacks.
    return """[fltsim]
fallback.1=..\\..\\..\\..\\texture\\DetailMap
fallback.2=..\\..\\..\\..\\texture\\Glass
fallback.3=..\\..\\..\\..\\texture\\Interiors
fallback.4=..\\..\\..\\..\\texture
fallback.5=..\\texture
fallback.6=..\\..\\Asobo_A320_NEO\\texture
"""


def manifest_json(cfg: dict, package_title: str) -> dict:
    return {
        "dependencies": [],
        "content_type": "AIRCRAFT",
        "title": package_title,
        "manufacturer": "Airbus",
        "creator": "SkinMyBird",
        "package_version": "0.2.0",
        "minimum_game_version": "1.7.12",
        "release_notes": {
            "neutral": {
                "LastUpdate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "OlderHistory": (
                    "v0.2: BC7 *.PNG.DDS albedo + JSON sidecars + thumbnails. "
                    "LIVERY_TEXTS UV slots for side titles + neo/tail logos; Asobo-style light thumbnails."
                ),
            }
        },
    }


def build_layout(package_root: Path) -> dict:
    entries = []
    for path in sorted(package_root.rglob("*")):
        if path.is_file() and path.name != "layout.json":
            rel = path.relative_to(package_root).as_posix()
            st = path.stat()
            date = int((st.st_mtime + 11644473600) * 10000000)
            entries.append({"path": rel, "size": st.st_size, "date": date})
    return {"content": entries}


def readme_ro(cfg: dict, package_folder: str, used_dds: bool) -> str:
    name = cfg.get("name", "Custom")
    tex_note = (
        "Texturile sunt **BC7 `*.PNG.DDS`** (formatul pe care MSFS 2020 îl citește pentru Community). "
        "Nu lăsa doar PNG — sim-ul le ignoră și vezi alb/albastru default."
        if used_dds
        else "Acest pachet conține **PNG** temporar. Rulează `convert_to_dds` (sau exporterul Python cu texconv) "
        "înainte de zbor — PNG singur = texturi albe/albastre în joc."
    )
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

## Texturi
{tex_note}

Fișiere tipice în `texture.*`:
- `A320NEO_AIRFRAME_*_ALBD.PNG.DDS` + `.PNG.DDS.json`
- `thumbnail.jpg` / `thumbnail_small.jpg`
- `texture.cfg` cu fallback Asobo

## Despre SkinMyBird
Instrument comercial one-time **€9.99** — recolorează livery-uri default Asobo și adaugă stickere/poze, apoi exportă pachet Community gata de copiat.

Creat cu SkinMyBird v0.2
"""


def find_texconv() -> Path | None:
    for p in TEXCONV_CANDIDATES:
        if p and p.is_file():
            return p
    return None


def wine_z_path(path: Path) -> str:
    """Map absolute Linux path to wine Z:\\... (Z: is usually /)."""
    resolved = path.resolve()
    return "Z:" + str(resolved).replace("/", "\\")


def convert_pngs_to_dds(png_paths: list[Path], out_dir: Path, texconv: Path) -> list[Path]:
    """Run wine texconv BC7 on all PNGs; rename outputs to *.PNG.DDS. Returns DDS paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Batch one wine call — startup is expensive.
    cmd = [
        "wine",
        str(texconv),
        "-f",
        "BC7_UNORM",
        "-y",
        "-o",
        wine_z_path(out_dir),
    ] + [wine_z_path(p) for p in png_paths]
    env = os.environ.copy()
    env.setdefault("WINEDEBUG", "-all")
    print(f"texconv: converting {len(png_paths)} PNG → BC7 DDS …", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(
            f"texconv failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        )

    dds_out: list[Path] = []
    for png in png_paths:
        # texconv writes stem.dds (often lowercase)
        candidates = [
            out_dir / f"{png.stem}.DDS",
            out_dir / f"{png.stem}.dds",
            out_dir / f"{png.stem}.PNG.DDS",
        ]
        src = next((c for c in candidates if c.exists()), None)
        if src is None:
            # search case-insensitive
            lower = {f.name.lower(): f for f in out_dir.iterdir() if f.is_file()}
            src = lower.get(f"{png.stem.lower()}.dds")
        if src is None:
            raise FileNotFoundError(f"texconv did not produce DDS for {png.name}")
        dest = out_dir / f"{png.stem}.PNG.DDS"
        if src.resolve() != dest.resolve():
            if dest.exists():
                dest.unlink()
            src.rename(dest)
        dds_out.append(dest)
    return dds_out


def write_dds_json(dds_path: Path) -> None:
    data = dict(DDS_JSON_TEMPLATE)
    data["SourceFileName"] = dds_path.name
    (dds_path.parent / f"{dds_path.name}.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def write_convert_helper(package_root: Path, tex_rel: str) -> None:
    """Windows helper if DDS step was skipped — convert PNG leftovers to PNG.DDS."""
    script = package_root / "convert_to_dds.ps1"
    script.write_text(
        f"""# SkinMyBird — convert leftover PNG albedo maps to BC7 *.PNG.DDS
# Usage (PowerShell, with texconv.exe on PATH or edit $Texconv):
#   .\\convert_to_dds.ps1
$ErrorActionPreference = 'Stop'
$Texconv = $env:SKINMYBIRD_TEXCONV
if (-not $Texconv) {{ $Texconv = Join-Path $PSScriptRoot '..\\..\\tools\\texconv.exe' }}
if (-not (Test-Path $Texconv)) {{ $Texconv = 'texconv.exe' }}
$TexDir = Join-Path $PSScriptRoot '{tex_rel}'
Get-ChildItem $TexDir -Filter '*.png' | ForEach-Object {{
  Write-Host "Converting $($_.Name)"
  & $Texconv -f BC7_UNORM -y -o $TexDir $_.FullName
  $dds = Join-Path $TexDir ($_.BaseName + '.DDS')
  if (-not (Test-Path $dds)) {{ $dds = Join-Path $TexDir ($_.BaseName + '.dds') }}
  $dest = Join-Path $TexDir ($_.BaseName + '.PNG.DDS')
  if (Test-Path $dds) {{ Move-Item -Force $dds $dest }}
  $json = @{{
    Version = 2
    SourceFileName = (Split-Path $dest -Leaf)
    Flags = @('FL_BITMAP_COMPRESSION','FL_BITMAP_MIPMAP')
  }} | ConvertTo-Json
  Set-Content -Path ($dest + '.json') -Value $json -Encoding UTF8
  Remove-Item $_.FullName -Force
}}
Write-Host 'Done. Regenerate layout.json with the SkinMyBird exporter if needed.'
""",
        encoding="utf-8",
    )


def export_package(
    cfg: dict,
    out_dir: Path,
    *,
    zip_out: bool = False,
    photo: Path | None = None,
    force_png: bool = False,
) -> Path:
    name = cfg.get("name", "Custom")
    slug = slugify(cfg.get("id") or name)
    package_folder = f"skinmybird-a320neo-{slug}"
    aircraft_folder = f"skinmybird_a320neo_{slug}"
    texture_name = slug
    unique_title = f"Airbus A320 Neo SkinMyBird {name}"

    package_root = out_dir / package_folder
    if package_root.exists():
        shutil.rmtree(package_root)
    sim_aircraft = package_root / "SimObjects" / "Airplanes" / aircraft_folder
    tex_dir = sim_aircraft / f"texture.{texture_name}"
    tex_dir.mkdir(parents=True, exist_ok=True)

    colors = cfg.get("colors", {})
    stickers = cfg.get("stickers", [])
    registration = cfg.get("registration", "SMB-001")
    photo_path = photo
    if not photo_path and cfg.get("soacraPhoto"):
        photo_path = Path(cfg["soacraPhoto"])

    # Build albedo PNGs in a temp dir, then convert / move into tex_dir.
    images: dict[str, Image.Image] = {
        "A320NEO_AIRFRAME_FUSELAGE_ALBD": make_fuselage(
            colors, stickers, registration, photo_path
        ),
        "A320NEO_AIRFRAME_WINGS_ALBD": make_solid(colors.get("wings", "#111111"), "WINGS"),
        "A320NEO_AIRFRAME_ENGINES_ALBD": make_solid(
            colors.get("engines", "#222222"), "ENGINES"
        ),
        "A320NEO_AIRFRAME_LIVERY_ALBD": make_livery_layer(stickers, registration),
        "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD": make_texts_layer(
            registration, cfg.get("airline") or cfg.get("name")
        ),
    }

    texconv = None if force_png else find_texconv()
    used_dds = False

    with tempfile.TemporaryDirectory(prefix="smb_tex_") as tmp:
        tmp_path = Path(tmp)
        png_paths: list[Path] = []
        for stem, im in images.items():
            p = tmp_path / f"{stem}.png"
            im.save(p, format="PNG")
            png_paths.append(p)

        if texconv is not None and shutil.which("wine"):
            try:
                dds_list = convert_pngs_to_dds(png_paths, tex_dir, texconv)
                for dds in dds_list:
                    write_dds_json(dds)
                used_dds = True
                print(f"OK DDS via wine+{texconv.name}: {len(dds_list)} maps", flush=True)
            except Exception as e:
                print(f"WARNING: DDS conversion failed ({e}); falling back to PNG.", file=sys.stderr)
                used_dds = False

        if not used_dds:
            for p in png_paths:
                shutil.copy2(p, tex_dir / p.name)
            write_convert_helper(
                package_root,
                f"SimObjects\\Airplanes\\{aircraft_folder}\\texture.{texture_name}",
            )
            print(
                "PNG placeholders written — run convert_to_dds.ps1 or install wine+texconv.",
                file=sys.stderr,
            )

    thumb, thumb_small = make_thumbnails(colors, name, registration)
    thumb.save(tex_dir / "thumbnail.jpg", quality=88, optimize=True)
    thumb_small.save(tex_dir / "thumbnail_small.jpg", quality=85, optimize=True)

    (tex_dir / "texture.cfg").write_text(texture_cfg(), encoding="utf-8")
    (sim_aircraft / "aircraft.cfg").write_text(
        aircraft_cfg(cfg, texture_name, unique_title), encoding="utf-8"
    )

    package_title = f"SkinMyBird A320neo — {name}"
    (package_root / "manifest.json").write_text(
        json.dumps(manifest_json(cfg, package_title), indent=2), encoding="utf-8"
    )
    (package_root / "README_INSTALL_RO.md").write_text(
        readme_ro(cfg, package_folder, used_dds), encoding="utf-8"
    )

    layout = build_layout(package_root)
    (package_root / "layout.json").write_text(
        json.dumps(layout, indent=2), encoding="utf-8"
    )

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
    p.add_argument(
        "--force-png",
        action="store_true",
        help="Skip texconv and emit PNG + convert_to_dds.ps1 helper",
    )
    args = p.parse_args(argv)

    cfg = load_config(args.config, args.preset)
    args.out.mkdir(parents=True, exist_ok=True)
    result = export_package(
        cfg, args.out, zip_out=args.zip, photo=args.photo, force_png=args.force_png
    )
    print(f"OK: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
