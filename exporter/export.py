#!/usr/bin/env python3
"""
SkinMyBird exporter — MSFS 2020 Community package from a livery config JSON.

Profile-driven (profiles/*.json): Asobo A320neo UV path + whole-albedo stubs
for other aircraft. Emits *.PNG.DDS (BC7_UNORM + mips) via wine+texconv when
available, plus Official-style *.PNG.DDS.json sidecars, thumbnails, texture.cfg,
layout.json, and optional ZIP.
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
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    print("Pillow required. Activate .venv and: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output"
DEFAULT_COMMUNITY = Path(
    os.environ.get(
        "SKINMYBIRD_COMMUNITY",
        r"C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community",
    )
)
TEXCONV_CANDIDATES = [
    Path(os.environ.get("SKINMYBIRD_TEXCONV", "")),
    ROOT / "tools" / "texconv.exe",
    Path("/workspace/tools/texconv.exe"),
    Path.home() / "tools" / "texconv.exe",
    Path(r"C:\Users\eugen\Downloads\texconv.exe"),
]

TEX_SIZE = 2048
ASOBO_THUMB_SIZE = (1618, 582)

# Official Asobo A320neo LIVERY_TEXTS UV (kept for back-compat imports)
A320NEO_TEXTS_UV = {
    "neo_logo_band": (95, 14, 1991, 552),
    "neo_logo_upper": (95, 14, 1991, 283),
    "neo_logo_lower": (95, 284, 1991, 552),
    "side_title_band": (52, 603, 1560, 1031),
    "side_title_upper": (52, 603, 1560, 817),
    "side_title_lower": (52, 818, 1560, 1031),
    "small_glyph_a": (42, 1062, 1679, 1257),
    "small_glyph_b": (57, 1311, 1640, 1444),
    "reg_slot": (12, 1509, 980, 1672),
    "small_glyph_c": (255, 1777, 784, 1875),
}

DDS_JSON_TEMPLATE = {
    "Version": 2,
    "SourceFileName": "",
    "Flags": ["FL_BITMAP_COMPRESSION", "FL_BITMAP_MIPMAP"],
}

DEFAULT_A320_PROFILE_ID = "asobo-aircraft-a320-neo"


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
            ROOT / "assets" / "fonts",
        ):
            candidate = base / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    pass
    # SpecialElite if present
    elite = ROOT / "assets" / "fonts" / "SpecialElite-Regular.ttf"
    if elite.exists():
        try:
            return ImageFont.truetype(str(elite), size)
        except OSError:
            pass
    return ImageFont.load_default()


def _role_color(colors: dict, role: str) -> str:
    mapping = {
        "fuselage": "fuselage",
        "wings": "wings",
        "engines": "engines",
        "tail": "tail",
        "livery": "fuselage",
        "texts": "fuselage",
        "primary": "fuselage",
    }
    key = mapping.get(role, "fuselage")
    defaults = {
        "fuselage": "#FF6A00",
        "wings": "#111111",
        "engines": "#222222",
        "tail": "#FF6A00",
    }
    return colors.get(key) or colors.get("accent") or defaults.get(key, "#888888")


# ---------------------------------------------------------------------------
# A320neo-specific painters (validated path)
# ---------------------------------------------------------------------------

def make_fuselage(
    colors: dict, stickers: list, registration: str, photo_path: Path | None
) -> Image.Image:
    """Fuselage albedo fill only. Titles/logos go on LIVERY_TEXTS UV."""
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (*hex_to_rgb(colors["fuselage"]), 255))
    draw = ImageDraw.Draw(img)
    tail = (*hex_to_rgb(colors["tail"]), 255)
    tw = int(TEX_SIZE * 0.18)
    draw.rectangle([TEX_SIZE - tw, 0, TEX_SIZE, TEX_SIZE], fill=tail)
    draw.ellipse([-160, TEX_SIZE // 3, 240, 2 * TEX_SIZE // 3], fill=(255, 255, 255, 36))
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
            continue

    if photo_path and photo_path.exists():
        try:
            photo = Image.open(photo_path).convert("RGBA")
            photo.thumbnail((320, 320))
            img.paste(photo, (TEX_SIZE // 2 - 160, TEX_SIZE // 2 + 140), photo)
        except OSError as e:
            print(f"Warning: could not place photo: {e}", file=sys.stderr)

    return img


def make_solid(color: str, label: str, size: int = TEX_SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (*hex_to_rgb(color), 255))
    draw = ImageDraw.Draw(img)
    font = _font(42)
    draw.text((40, 40), f"SkinMyBird\n{label}", fill=(255, 255, 255, 90), font=font)
    for i in range(0, size, 256):
        draw.line([(i, 0), (i, size)], fill=(0, 0, 0, 28), width=2)
        draw.line([(0, i), (size, i)], fill=(0, 0, 0, 28), width=2)
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


def make_texts_layer(
    registration: str,
    airline: str | None = None,
    uv: dict | None = None,
) -> Image.Image:
    """Paint titles/registration into LIVERY_TEXTS UV slots."""
    uv = uv or A320NEO_TEXTS_UV
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    title = (airline or registration or "SkinMyBird").strip()

    for key, mirror in (("side_title_upper", False), ("side_title_lower", True)):
        if key not in uv:
            continue
        rect = uv[key]
        x0, y0, x1, y1 = (tuple(rect) if not isinstance(rect, tuple) else rect)
        rw, rh = x1 - x0, y1 - y0
        layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        font = _font(max(28, min(110, rh // 2)), bold=True)
        bbox = ld.textbbox((0, 0), title, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        while tw > rw * 0.92 and getattr(font, "size", 24) > 24:
            font = _font(font.size - 4, bold=True)  # type: ignore[attr-defined]
            bbox = ld.textbbox((0, 0), title, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (rw - tw) // 2 - bbox[0]
        ty = (rh - th) // 2 - bbox[1]
        ld.text((tx, ty), title, fill=(255, 255, 255, 255), font=font)
        if mirror:
            layer = ImageOps.mirror(layer)
        img.paste(layer, (x0, y0), layer)

    if "reg_slot" in uv:
        x0, y0, x1, y1 = tuple(uv["reg_slot"])
        font = _font(64, bold=True)
        draw.text(
            (x0 + 40, y0 + (y1 - y0) // 3),
            registration,
            fill=(255, 255, 255, 240),
            font=font,
        )
    return img


def paste_centered_logo(
    img: Image.Image,
    logo_path: Path | None,
    *,
    max_frac: float = 0.35,
) -> Image.Image:
    if not logo_path or not logo_path.exists():
        return img
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except OSError:
        return img
    tw = int(img.width * max_frac)
    logo.thumbnail((tw, tw), Image.Resampling.LANCZOS)
    x = (img.width - logo.width) // 2
    y = (img.height - logo.height) // 2
    out = img.copy()
    out.paste(logo, (x, y), logo)
    return out


def paste_text_in_rect(
    img: Image.Image,
    text: str,
    rect: tuple[int, int, int, int] | list[int],
    *,
    invert: bool = False,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    x0, y0, x1, y1 = tuple(rect)
    rw, rh = max(1, x1 - x0), max(1, y1 - y0)
    layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    font = _font(max(16, min(96, rh - 4)), bold=True)
    bbox = ld.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    while tw > rw * 0.95 and getattr(font, "size", 16) > 12:
        font = _font(font.size - 2, bold=True)  # type: ignore[attr-defined]
        bbox = ld.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (rw - tw) // 2 - bbox[0]
    ty = (rh - th) // 2 - bbox[1]
    ld.text((tx, ty), text, fill=color, font=font)
    if invert:
        layer = layer.rotate(180)
    img.paste(layer, (x0, y0), layer)


def make_a319_style_map(
    stem: str,
    role: str,
    colors: dict,
    stickers: list,
    registration: str,
    airline: str,
    uv: dict | None,
    logo_path: Path | None,
    photo_path: Path | None,
    size: int,
) -> Image.Image:
    """Paint LatinVFR-style maps (fuselage/tail with UV titles when available)."""
    color = _role_color(colors, role)
    img = make_solid(color, stem, size=size)

    if role == "fuselage" and uv:
        title = airline or registration
        for key, invert in (
            ("title_upper", True),
            ("title_lower", False),
            ("reg_upper", False),
            ("reg_lower", True),
            ("belly", False),
        ):
            if key not in uv:
                continue
            txt = registration if key.startswith("reg") else (
                title if key != "belly" else (airline or "SkinMyBird")
            )
            paste_text_in_rect(img, txt, uv[key], invert=invert)

        for st in stickers:
            if st.get("enabled") and st.get("type") == "team_stripe":
                y = size // 2 + 60
                draw = ImageDraw.Draw(img)
                draw.rectangle([80, y, size - 80, y + 40], fill=(255, 255, 255, 230))

        if photo_path and photo_path.exists():
            try:
                photo = Image.open(photo_path).convert("RGBA")
                photo.thumbnail((280, 280))
                img.paste(photo, (size // 2 - 140, size // 2 + 100), photo)
            except OSError:
                pass

    if role == "tail" and uv:
        for key in ("tail_logo_upper", "tail_logo_lower"):
            if key not in uv or not logo_path or not logo_path.exists():
                continue
            x0, y0, x1, y1 = tuple(uv[key])
            rw, rh = x1 - x0, y1 - y0
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((int(rw * 0.7), int(rh * 0.7)), Image.Resampling.LANCZOS)
                lx = x0 + (rw - logo.width) // 2
                ly = y0 + (rh - logo.height) // 2
                img.paste(logo, (lx, ly), logo)
            except OSError:
                paste_text_in_rect(img, airline[:12] or "SMB", uv[key])

    if role == "fuselage" and (not uv) and logo_path:
        img = paste_centered_logo(img, logo_path)

    return img


def make_whole_albedo_map(
    stem: str,
    role: str,
    colors: dict,
    registration: str,
    airline: str,
    logo_path: Path | None,
    photo_path: Path | None,
    size: int,
) -> Image.Image:
    """Unknown-UV stub: solid role color + optional centered logo/text on primary."""
    color = _role_color(colors, role)
    img = make_solid(color, stem, size=size)
    if role in ("fuselage", "primary"):
        img = paste_centered_logo(img, logo_path, max_frac=0.4)
        draw = ImageDraw.Draw(img)
        label = airline or registration
        font = _font(72, bold=True)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((size - tw) // 2, int(size * 0.72)),
            label,
            fill=(255, 255, 255, 220),
            font=font,
        )
        if photo_path and photo_path.exists():
            try:
                photo = Image.open(photo_path).convert("RGBA")
                photo.thumbnail((280, 280))
                img.paste(photo, (size // 2 - 140, int(size * 0.55)), photo)
            except OSError:
                pass
    return img


def make_thumbnails(
    colors: dict,
    name: str,
    registration: str,
    silhouette: str = "airliner",
) -> tuple[Image.Image, Image.Image]:
    """Asobo-style list card on light studio background."""
    W, H = ASOBO_THUMB_SIZE
    img = Image.new("RGB", (W, H), (210, 212, 216))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(225 + (245 - 225) * t)
        g = int(226 + (246 - 226) * t)
        b = int(230 + (248 - 230) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    fus = hex_to_rgb(colors.get("fuselage", "#FF6A00"))
    wing = hex_to_rgb(colors.get("wings", "#111111"))
    eng = hex_to_rgb(colors.get("engines", "#222222"))
    tail = hex_to_rgb(colors.get("tail", "#FF6A00"))

    draw.ellipse(
        [int(W * 0.18), int(H * 0.78), int(W * 0.82), int(H * 0.92)],
        fill=(180, 182, 186),
    )

    cx, cy = int(W * 0.52), int(H * 0.52)

    if silhouette == "helicopter":
        # Simple H135-ish side view
        draw.rounded_rectangle([cx - 200, cy - 40, cx + 180, cy + 50], radius=30, fill=fus)
        draw.polygon(
            [(cx + 140, cy - 20), (cx + 280, cy - 10), (cx + 280, cy + 20), (cx + 140, cy + 30)],
            fill=tail,
        )
        draw.ellipse([cx - 40, cy - 160, cx + 40, cy - 40], outline=wing, width=8)
        draw.line([(cx, cy - 100), (cx, cy - 40)], fill=wing, width=6)
        draw.rounded_rectangle([cx - 60, cy + 40, cx + 40, cy + 70], radius=8, fill=eng)
        draw.rounded_rectangle([cx - 180, cy - 25, cx - 120, cy + 10], radius=6, fill=(40, 48, 60))
    elif silhouette == "balloon":
        draw.ellipse([cx - 160, cy - 220, cx + 160, cy + 40], fill=fus)
        draw.polygon(
            [(cx - 40, cy + 30), (cx + 40, cy + 30), (cx + 55, cy + 120), (cx - 55, cy + 120)],
            fill=wing,
        )
        draw.rounded_rectangle([cx - 50, cy + 120, cx + 50, cy + 170], radius=6, fill=eng)
        # panels
        for i in range(-2, 3):
            draw.arc(
                [cx - 160 + i * 8, cy - 220, cx + 160 + i * 8, cy + 40],
                200,
                340,
                fill=tail,
                width=3,
            )
    else:
        # airliner 3/4
        draw.polygon(
            [(cx - 40, cy - 10), (cx - 280, cy - 120), (cx - 250, cy - 95), (cx + 20, cy + 5)],
            fill=wing,
        )
        draw.ellipse([cx - 420, cy - 55, cx - 300, cy + 55], fill=fus)
        draw.rounded_rectangle([cx - 360, cy - 50, cx + 280, cy + 50], radius=40, fill=fus)
        draw.polygon(
            [(cx - 20, cy + 10), (cx + 260, cy + 70), (cx + 290, cy + 95), (cx - 40, cy + 40)],
            fill=wing,
        )
        draw.rounded_rectangle([cx - 30, cy + 28, cx + 70, cy + 78], radius=18, fill=eng)
        draw.rounded_rectangle([cx + 100, cy + 38, cx + 190, cy + 82], radius=16, fill=eng)
        draw.rounded_rectangle([cx - 340, cy - 38, cx - 270, cy - 8], radius=6, fill=(40, 48, 60))
        for i in range(12):
            x = cx - 230 + i * 36
            draw.rounded_rectangle([x, cy - 22, x + 18, cy - 4], radius=4, fill=(40, 48, 60))
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


def aircraft_cfg_from_profile(
    cfg: dict, profile: dict, texture_folder: str, unique_title: str
) -> str:
    reg = cfg.get("registration", "SMB-001")
    airline = cfg.get("airline", "SkinMyBird")
    icao = cfg.get("icao", "SMB")
    name = cfg.get("name", "Custom")
    base = profile.get("base_container", "..\\Asobo_A320_NEO")
    # Escape backslashes for cfg
    base_esc = base.replace("\\", "\\\\")
    return f"""[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "{base_esc}"

; SkinMyBird generated variation — profile {profile.get('id')}
[FLTSIM.0]
title = "{unique_title}"
model = ""
panel = ""
sound = ""
texture = "{texture_folder}"
kb_checklists = ""
kb_reference = ""
description = "SkinMyBird custom livery — {name}. BC7 DDS albedo textures."
wip_indicator = 0
ui_manufacturer = "{profile.get('ui_manufacturer', 'Airbus')}"
ui_type = "{profile.get('ui_type', 'Aircraft')}"
ui_variation = "{name}"
ui_typerole = "{profile.get('ui_typerole', 'Commercial Airliner')}"
ui_createdby = "SkinMyBird"
atc_id = "{reg}"
atc_airline = "{airline}"
atc_flight_number = "1"
icao_airline = "{icao}"
isAirTraffic = 0
isUserSelectable = 1
"""


def aircraft_cfg(cfg: dict, texture_folder: str, unique_title: str) -> str:
    """Legacy A320neo helper."""
    from exporter.profiles import load_profile

    return aircraft_cfg_from_profile(
        cfg, load_profile(DEFAULT_A320_PROFILE_ID), texture_folder, unique_title
    )


def texture_cfg(fallbacks: list[str] | None = None) -> str:
    lines = ["[fltsim]"]
    fb = fallbacks or [
        "..\\..\\..\\..\\texture\\DetailMap",
        "..\\..\\..\\..\\texture\\Glass",
        "..\\..\\..\\..\\texture\\Interiors",
        "..\\..\\..\\..\\texture",
        "..\\texture",
        "..\\..\\Asobo_A320_NEO\\texture",
    ]
    for i, path in enumerate(fb, start=1):
        lines.append(f"fallback.{i}={path}")
    return "\n".join(lines) + "\n"


def manifest_json(cfg: dict, package_title: str) -> dict:
    return {
        "dependencies": [],
        "content_type": "AIRCRAFT",
        "title": package_title,
        "manufacturer": cfg.get("_manufacturer", "Airbus"),
        "creator": "SkinMyBird",
        "package_version": "0.3.0",
        "minimum_game_version": "1.7.12",
        "release_notes": {
            "neutral": {
                "LastUpdate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "OlderHistory": (
                    "v0.3: multi-aircraft profiles + BC7 *.PNG.DDS + JSON sidecars. "
                    "A320neo UV titles; whole-albedo stubs for unknown UV models."
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


def readme_ro(cfg: dict, package_folder: str, used_dds: bool, profile: dict) -> str:
    name = cfg.get("name", "Custom")
    display = profile.get("displayName", profile.get("id", "Aircraft"))
    tex_note = (
        "Texturile sunt **BC7 `*.PNG.DDS`** (formatul pe care MSFS 2020 îl citește pentru Community). "
        "Nu lăsa doar PNG — sim-ul le ignoră și vezi alb/albastru default."
        if used_dds
        else "Acest pachet conține **PNG** temporar. Rulează `convert_to_dds.ps1` (sau exporterul cu texconv) "
        "înainte de zbor — PNG singur = texturi albe/albastre în joc."
    )
    community = (
        r"C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community"
    )
    return f"""# SkinMyBird — Instalare livery MSFS 2020

## Ce ai primit
Pachet Community pentru **{display}**: **{name}**.

Folder pachet: `{package_folder}`
Profil: `{profile.get('id')}` · paint_mode: `{profile.get('paint_mode')}`

## Instalare
1. Copiază întregul folder `{package_folder}` în **Community**:
   - `{community}`
   - (junction tipic: `D:\\MSFS2020\\Community`)
2. Repornește Microsoft Flight Simulator 2020.
3. Alege **{display}** → livery **{name}** (SkinMyBird).

## Texturi
{tex_note}

## Despre SkinMyBird
Instrument tip Canva — recolorează avioane/elicoptere/baloane, exportă Community ZIP cu DDS.

Creat cu SkinMyBird v0.3
"""


def find_texconv() -> Path | None:
    for p in TEXCONV_CANDIDATES:
        if p and p.is_file():
            return p
    return None


def wine_z_path(path: Path) -> str:
    resolved = path.resolve()
    return "Z:" + str(resolved).replace("/", "\\")


def convert_pngs_to_dds(png_paths: list[Path], out_dir: Path, texconv: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
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
        candidates = [
            out_dir / f"{png.stem}.DDS",
            out_dir / f"{png.stem}.dds",
            out_dir / f"{png.stem}.PNG.DDS",
        ]
        src = next((c for c in candidates if c.exists()), None)
        if src is None:
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
    script = package_root / "convert_to_dds.ps1"
    script.write_text(
        f"""# SkinMyBird — convert leftover PNG albedo maps to BC7 *.PNG.DDS
$ErrorActionPreference = 'Stop'
$Texconv = $env:SKINMYBIRD_TEXCONV
if (-not $Texconv) {{ $Texconv = 'C:\\Users\\eugen\\Downloads\\texconv.exe' }}
if (-not (Test-Path $Texconv)) {{ $Texconv = Join-Path $PSScriptRoot '..\\..\\tools\\texconv.exe' }}
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
Write-Host 'Done. Regenerare layout.json recomandată via SkinMyBird exporter.'
""",
        encoding="utf-8",
    )


def resolve_profile(cfg: dict, profile_id: str | None) -> dict[str, Any]:
    from exporter.profiles import load_profile

    pid = (
        profile_id
        or cfg.get("profile")
        or cfg.get("aircraft")
        or DEFAULT_A320_PROFILE_ID
    )
    # Map legacy preset aircraft keys
    aliases = {
        "lvfr-319-cfm": "lvfr-airbus-a319-ceo",
        "a320neo": DEFAULT_A320_PROFILE_ID,
        "asobo-a320-neo": DEFAULT_A320_PROFILE_ID,
    }
    pid = aliases.get(pid, pid)
    try:
        return load_profile(pid)
    except FileNotFoundError:
        if pid != DEFAULT_A320_PROFILE_ID:
            print(f"WARNING: profile {pid} missing — falling back to A320neo", file=sys.stderr)
        return load_profile(DEFAULT_A320_PROFILE_ID)


def build_images_for_profile(
    profile: dict,
    cfg: dict,
    photo_path: Path | None,
) -> dict[str, Image.Image]:
    colors = cfg.get("colors", {})
    stickers = cfg.get("stickers", [])
    registration = cfg.get("registration", "SMB-001")
    airline = cfg.get("airline") or cfg.get("name") or "SkinMyBird"
    size = int(profile.get("tex_size") or TEX_SIZE)
    paint_mode = profile.get("paint_mode", "whole_albedo")
    uv_raw = profile.get("uv_rects")
    uv = {k: tuple(v) for k, v in uv_raw.items()} if uv_raw else None

    logo_path = None
    if cfg.get("logo"):
        lp = Path(cfg["logo"])
        if not lp.is_absolute():
            lp = ROOT / lp
        logo_path = lp if lp.exists() else None

    images: dict[str, Image.Image] = {}
    textures = profile.get("textures") or []

    # Special-case validated A320neo pipeline
    if profile.get("id") == DEFAULT_A320_PROFILE_ID and paint_mode == "uv_rects":
        images = {
            "A320NEO_AIRFRAME_FUSELAGE_ALBD": make_fuselage(
                colors, stickers, registration, photo_path
            ),
            "A320NEO_AIRFRAME_WINGS_ALBD": make_solid(
                colors.get("wings", "#111111"), "WINGS", size
            ),
            "A320NEO_AIRFRAME_ENGINES_ALBD": make_solid(
                colors.get("engines", "#222222"), "ENGINES", size
            ),
            "A320NEO_AIRFRAME_LIVERY_ALBD": make_livery_layer(stickers, registration),
            "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD": make_texts_layer(
                registration, airline, uv or A320NEO_TEXTS_UV
            ),
        }
        return images

    for tex in textures:
        stem = tex["stem"]
        role = tex.get("role", "fuselage")
        if paint_mode == "uv_rects" and profile.get("id") == "lvfr-airbus-a319-ceo":
            images[stem] = make_a319_style_map(
                stem,
                role,
                colors,
                stickers,
                registration,
                airline,
                uv,
                logo_path,
                photo_path,
                size,
            )
        elif paint_mode == "uv_rects" and role == "texts":
            images[stem] = make_texts_layer(registration, airline, uv)
        elif paint_mode == "uv_rects" and role == "fuselage":
            images[stem] = make_a319_style_map(
                stem, role, colors, stickers, registration, airline, uv,
                logo_path, photo_path, size,
            )
        elif paint_mode == "uv_rects" and role == "tail":
            images[stem] = make_a319_style_map(
                stem, role, colors, stickers, registration, airline, uv,
                logo_path, photo_path, size,
            )
        elif paint_mode == "uv_rects" and role == "livery":
            images[stem] = make_livery_layer(stickers, registration)
        else:
            images[stem] = make_whole_albedo_map(
                stem, role, colors, registration, airline, logo_path, photo_path, size
            )
    return images


def export_package(
    cfg: dict,
    out_dir: Path,
    *,
    zip_out: bool = False,
    photo: Path | None = None,
    force_png: bool = False,
    profile_id: str | None = None,
    profile: dict | None = None,
) -> Path:
    prof = profile or resolve_profile(cfg, profile_id)
    name = cfg.get("name", "Custom")
    slug = slugify(cfg.get("id") or name)
    package_folder = f"{prof.get('package_prefix', 'skinmybird')}-{slug}"
    aircraft_folder = f"{prof.get('aircraft_folder_prefix', 'skinmybird')}_{slug}"
    texture_name = slug
    title_tpl = prof.get("title_template") or "SkinMyBird {name}"
    unique_title = title_tpl.replace("{name}", name)

    package_root = out_dir / package_folder
    if package_root.exists():
        shutil.rmtree(package_root)

    sim_type = prof.get("simObjectType", "Airplanes")
    sim_aircraft = package_root / "SimObjects" / sim_type / aircraft_folder
    tex_dir = sim_aircraft / f"texture.{texture_name}"
    tex_dir.mkdir(parents=True, exist_ok=True)

    colors = cfg.get("colors", {})
    registration = cfg.get("registration", "SMB-001")
    photo_path = photo
    if not photo_path and cfg.get("soacraPhoto"):
        candidate = Path(cfg["soacraPhoto"])
        photo_path = candidate if candidate.exists() else None

    images = build_images_for_profile(prof, cfg, photo_path)

    texconv = None if force_png else find_texconv()
    used_dds = False
    wine_ok = bool(shutil.which("wine"))

    with tempfile.TemporaryDirectory(prefix="smb_tex_") as tmp:
        tmp_path = Path(tmp)
        png_paths: list[Path] = []
        for stem, im in images.items():
            p = tmp_path / f"{stem}.png"
            im.save(p, format="PNG")
            png_paths.append(p)

        if texconv is not None and wine_ok:
            try:
                dds_list = convert_pngs_to_dds(png_paths, tex_dir, texconv)
                for dds in dds_list:
                    write_dds_json(dds)
                used_dds = True
                print(f"OK DDS via wine+{texconv.name}: {len(dds_list)} maps", flush=True)
            except Exception as e:
                print(
                    f"WARNING: DDS conversion failed ({e}); falling back to PNG.",
                    file=sys.stderr,
                )
                used_dds = False
        elif texconv is not None and not wine_ok and os.name == "nt":
            # Native Windows texconv
            try:
                dds_list = convert_pngs_native(png_paths, tex_dir, texconv)
                for dds in dds_list:
                    write_dds_json(dds)
                used_dds = True
            except Exception as e:
                print(f"WARNING: native texconv failed ({e})", file=sys.stderr)

        if not used_dds:
            for p in png_paths:
                shutil.copy2(p, tex_dir / p.name)
            write_convert_helper(
                package_root,
                f"SimObjects\\{sim_type}\\{aircraft_folder}\\texture.{texture_name}",
            )
            print(
                "PNG placeholders written — run convert_to_dds.ps1 or install wine+texconv.",
                file=sys.stderr,
            )

    thumb, thumb_small = make_thumbnails(
        colors, name, registration, silhouette=prof.get("silhouette", "airliner")
    )
    thumb.save(tex_dir / "thumbnail.jpg", quality=88, optimize=True)
    thumb_small.save(tex_dir / "thumbnail_small.jpg", quality=85, optimize=True)

    (tex_dir / "texture.cfg").write_text(
        texture_cfg(prof.get("texture_fallbacks")), encoding="utf-8"
    )
    (sim_aircraft / "aircraft.cfg").write_text(
        aircraft_cfg_from_profile(cfg, prof, texture_name, unique_title),
        encoding="utf-8",
    )

    cfg_man = dict(cfg)
    cfg_man["_manufacturer"] = prof.get("ui_manufacturer", "Airbus")
    package_title = f"SkinMyBird {prof.get('displayName', '')} — {name}".strip()
    (package_root / "manifest.json").write_text(
        json.dumps(manifest_json(cfg_man, package_title), indent=2), encoding="utf-8"
    )
    (package_root / "README_INSTALL_RO.md").write_text(
        readme_ro(cfg, package_folder, used_dds, prof), encoding="utf-8"
    )

    layout = build_layout(package_root)
    (package_root / "layout.json").write_text(
        json.dumps(layout, indent=2), encoding="utf-8"
    )

    meta = {
        "profile_id": prof.get("id"),
        "paint_mode": prof.get("paint_mode"),
        "used_dds": used_dds,
        "package_folder": package_folder,
        "texture_stems": list(images.keys()),
    }
    (package_root / "skinmybird_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    if zip_out:
        zip_path = out_dir / f"{package_folder}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in package_root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(out_dir).as_posix())
        return zip_path

    return package_root


def convert_pngs_native(png_paths: list[Path], out_dir: Path, texconv: Path) -> list[Path]:
    """Windows native texconv (no wine)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [str(texconv), "-f", "BC7_UNORM", "-y", "-o", str(out_dir)] + [
        str(p) for p in png_paths
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"texconv failed: {proc.stderr}")
    dds_out: list[Path] = []
    for png in png_paths:
        src = out_dir / f"{png.stem}.DDS"
        if not src.exists():
            src = out_dir / f"{png.stem}.dds"
        dest = out_dir / f"{png.stem}.PNG.DDS"
        if src.exists():
            if dest.exists():
                dest.unlink()
            src.rename(dest)
            dds_out.append(dest)
        else:
            raise FileNotFoundError(png.name)
    return dds_out


def install_to_community(
    package_root: Path,
    community: Path | None = None,
) -> Path:
    """Copy package folder into MSFS Community directory."""
    dest_root = community or DEFAULT_COMMUNITY
    if not dest_root.exists():
        raise FileNotFoundError(
            f"Community path not found: {dest_root}. "
            "Set SKINMYBIRD_COMMUNITY or pass community path."
        )
    target = dest_root / package_root.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(package_root, target)
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SkinMyBird MSFS Community package exporter")
    p.add_argument("--config", type=Path, help="Path to livery config JSON")
    p.add_argument("--preset", type=str, help="Preset id (e.g. eugen-orange)")
    p.add_argument("--profile", type=str, help="Aircraft profile id")
    p.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    p.add_argument("--zip", action="store_true", help="Also write a .zip next to the folder")
    p.add_argument("--photo", type=Path, help="Optional soacră / decal image path")
    p.add_argument(
        "--force-png",
        action="store_true",
        help="Skip texconv and emit PNG + convert_to_dds.ps1 helper",
    )
    p.add_argument(
        "--install",
        action="store_true",
        help="Copy package into Community after export",
    )
    p.add_argument(
        "--community",
        type=Path,
        default=None,
        help="Override Community install path",
    )
    p.add_argument("--list-profiles", action="store_true", help="Print available profiles")
    args = p.parse_args(argv)

    if args.list_profiles:
        from exporter.profiles import list_profiles

        for pr in list_profiles():
            uv = "UV" if pr["has_uv"] else "whole"
            print(f"{pr['id']:40s}  {pr['displayName']:28s}  {uv}  ({pr['category']})")
        return 0

    cfg = load_config(args.config, args.preset)
    args.out.mkdir(parents=True, exist_ok=True)
    result = export_package(
        cfg,
        args.out,
        zip_out=args.zip,
        photo=args.photo,
        force_png=args.force_png,
        profile_id=args.profile,
    )
    print(f"OK: {result}")

    if args.install:
        pkg = result if result.is_dir() else result.with_suffix("")
        # if zip, package folder is sibling without .zip — prefer folder
        if result.suffix == ".zip":
            pkg = args.out / result.stem
        try:
            installed = install_to_community(pkg, args.community)
            print(f"INSTALLED: {installed}")
        except FileNotFoundError as e:
            print(f"INSTALL SKIPPED: {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
