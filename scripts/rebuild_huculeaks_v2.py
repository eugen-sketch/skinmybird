#!/usr/bin/env python3
"""Rebuild HUCULEAKS AIR A320neo livery using REAL Official Asobo UV maps.

Key lesson from v1 feedback:
- Do NOT paint titles/logos on fake fuselage UV (ends up on roof / clipped).
- Fuselage SIDE titles + tail logos live on A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.
- Recolor Official albedos (luminance multiply) so panel shading survives.
- Thumbnails must be Asobo-style 3/4 aircraft on light studio background.
"""
from __future__ import annotations

import json
import shutil
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exporter.export import (  # noqa: E402
    A320NEO_TEXTS_UV,
    TEX_SIZE,
    build_layout,
    find_texconv,
    hex_to_rgb,
    manifest_json,
    readme_ro,
    texture_cfg,
    wine_z_path,
    write_dds_json,
)

OUT = ROOT / "output"
REF = ROOT / "work" / "official_ref"
PACKAGE_FOLDER = "skinmybird-a320neo-huculeaks_air"
AIRCRAFT_FOLDER = "skinmybird_a320neo_huculeaks_air"
TEXTURE_NAME = "huculeaks_air"
UNIQUE_TITLE = "Airbus A320 Neo SkinMyBird HUCULEAKS AIR"

LOGO_PATH = ROOT / "work" / "huculeaks_logo.png"
FONT_PATH = ROOT / "assets" / "fonts" / "SpecialElite-Regular.ttf"
PRESET_PATH = ROOT / "presets" / "huculeaks-air.json"
PREVIEW = ROOT / "work" / "huculeaks_previews"

# Elegant charcoal range + accent
FUSELAGE_TARGET = (0x1A, 0x1A, 0x1A)  # midpoint of #141414–#1E1E1E
WINGS_TARGET = (0x0A, 0x0A, 0x0A)
ENGINES_TARGET = (0x2A, 0x2A, 0x2A)
ACCENT = (0xE8, 0x5A, 0x00)
WHITE = (255, 255, 255, 255)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        try:
            return ImageFont.truetype(str(FONT_PATH), size)
        except OSError:
            pass
    return ImageFont.load_default()


def luminance(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def recolor_luminance_multiply(
    img: Image.Image,
    target_rgb: tuple[int, int, int],
    *,
    keep_dark_lt: float = 0.06,
    preserve_blue_logos: bool = False,
) -> Image.Image:
    """Keep Official panel shading via luminance * target color."""
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)
    rgb = arr[..., :3]
    a = arr[..., 3]
    L = luminance(rgb)

    out = rgb.copy()
    # Base multiply
    for i in range(3):
        out[..., i] = np.clip(target_rgb[i] * (L / 0.55), 0, 255)
    # Soft floor so charcoal isn't crushed pure black on mid panels
    out = np.clip(out, 0, 255)

    # Preserve near-black panel lines / vents
    dark = L < keep_dark_lt
    out[dark] = rgb[dark] * 0.35

    if preserve_blue_logos:
        mx = rgb.max(axis=-1)
        mn = rgb.min(axis=-1)
        sat = np.where(mx > 1, (mx - mn) / mx, 0)
        blueish = (rgb[..., 2] > rgb[..., 0] + 20) & (rgb[..., 2] > rgb[..., 1] + 10) & (sat > 0.3)
        out[blueish] = rgb[blueish]

    result = np.dstack([out, a]).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def recolor_engines_with_orange_lip(img: Image.Image) -> Image.Image:
    """Charcoal engines; gently tint brightest metallic lip pixels toward accent orange."""
    base = recolor_luminance_multiply(img, ENGINES_TARGET, keep_dark_lt=0.05)
    arr = np.array(base, dtype=np.float32)
    src = np.array(img.convert("RGBA"), dtype=np.float32)
    L = luminance(src[..., :3])
    # Bright metallic lips / spinner rings on Official map
    lip = (L > 0.72) & (src[..., 3] > 200)
    # Mix a thin orange accent into those lips (not full replace)
    accent = np.array(ACCENT, dtype=np.float32)
    mix = 0.55
    for i in range(3):
        arr[..., i] = np.where(
            lip,
            np.clip(arr[..., i] * (1 - mix) + accent[i] * mix * (L / 0.9), 0, 255),
            arr[..., i],
        )
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def crop_owl_emblem(logo: Image.Image) -> Image.Image:
    """Crop circular owl; exclude HUCULEAKS wordmark below (~y670+)."""
    # Measured content ~227,144–772,699; wordmark starts ~y670
    box = (210, 130, 790, 660)
    emblem = logo.crop(box).convert("RGBA")
    w, h = emblem.size
    # Square canvas
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(emblem, ((side - w) // 2, (side - h) // 2), emblem)
    mask = Image.new("L", (side, side), 0)
    md = ImageDraw.Draw(mask)
    pad = 6
    md.ellipse([pad, pad, side - pad - 1, side - pad - 1], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(3))
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(square, (0, 0), mask)
    return out


def paste_centered(base: Image.Image, overlay: Image.Image, cx: int, cy: int) -> None:
    ow, oh = overlay.size
    base.paste(overlay, (int(cx - ow // 2), int(cy - oh // 2)), overlay)


def fit_text_width(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, max_size: int, min_size: int = 28
) -> ImageFont.ImageFont:
    size = max_size
    while size >= min_size:
        font = load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 4
    return load_font(min_size)


def draw_title_in_rect(
    img: Image.Image,
    text: str,
    rect: tuple[int, int, int, int],
    *,
    mirror: bool = False,
    fill=WHITE,
) -> None:
    x0, y0, x1, y1 = rect
    rw, rh = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = fit_text_width(d, text, int(rw * 0.92), max_size=min(140, int(rh * 0.55)))
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (rw - tw) // 2 - bbox[0]
    ty = (rh - th) // 2 - bbox[1]
    # Soft shadow for charcoal readability
    d.text((tx + 3, ty + 3), text, fill=(0, 0, 0, 140), font=font)
    d.text((tx, ty), text, fill=fill, font=font)
    if mirror:
        layer = ImageOps.mirror(layer)
    img.paste(layer, (x0, y0), layer)


def make_livery_texts(logo: Image.Image, registration: str) -> Image.Image:
    """Rebuild LIVERY_TEXTS from transparent using discovered Official UV rects."""
    img = Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))
    emblem = crop_owl_emblem(logo)

    # --- Tail neo slots → full owl emblem (port + starboard) ---
    for rect in (A320NEO_TEXTS_UV["neo_logo_upper"], A320NEO_TEXTS_UV["neo_logo_lower"]):
        x0, y0, x1, y1 = rect
        rw, rh = x1 - x0, y1 - y0
        # Fit whole circle inside slot (height-limited); leave margin so UV doesn't clip
        diam = int(min(rw, rh) * 0.92)
        owl = emblem.resize((diam, diam), Image.Resampling.LANCZOS)
        paste_centered(img, owl, x0 + rw // 2, y0 + rh // 2)

    # --- Fuselage SIDE titles (both UV copies for L/R) ---
    title = "HUCULEAKS AIR"
    draw_title_in_rect(img, title, A320NEO_TEXTS_UV["side_title_upper"], mirror=False)
    # Lower slot often maps the opposite side — mirror so lettering reads correctly
    draw_title_in_rect(img, title, A320NEO_TEXTS_UV["side_title_lower"], mirror=True)

    # Registration — tasteful small glyph in former small-AIRBUS band
    reg_rect = A320NEO_TEXTS_UV["reg_slot"]
    draw_title_in_rect(
        img,
        registration,
        reg_rect,
        mirror=False,
        fill=(235, 235, 235, 240),
    )

    # Smaller Official glyph bands intentionally left empty (no junk).
    return img


def make_livery_albd_clear() -> Image.Image:
    """Neutral/transparent — clears default blue neo engine/livery paint."""
    return Image.new("RGBA", (TEX_SIZE, TEX_SIZE), (0, 0, 0, 0))


def make_asobo_thumbnail(logo: Image.Image, registration: str) -> tuple[Image.Image, Image.Image]:
    """Asobo-style list card: light studio bg + soft shadow + 3/4 charcoal aircraft + owl on fin.

    Photo-recolor of official_thumbnail proved fragile (white nose / ground shadow).
    Drawn card matches Official list aspect (~1618x582) and never goes black-on-black.
    """
    from exporter.export import make_thumbnails as _exporter_thumbs

    colors = {
        "fuselage": "#1A1A1A",
        "wings": "#0A0A0A",
        "engines": "#2A2A2A",
        "tail": "#121212",
    }
    thumb, _small = _exporter_thumbs(colors, "HUCULEAKS AIR", registration)
    thumb = thumb.convert("RGBA")
    d = ImageDraw.Draw(thumb)
    W, H = thumb.size
    cx, cy = int(W * 0.52), int(H * 0.52)
    accent_a = ACCENT + (220,)
    d.ellipse([cx - 28, cy + 32, cx + 68, cy + 74], outline=accent_a, width=3)
    d.ellipse([cx + 102, cy + 42, cx + 188, cy + 78], outline=accent_a, width=3)
    d.rectangle([cx - 300, cy + 18, cx + 200, cy + 22], fill=ACCENT + (200,))
    emblem = crop_owl_emblem(logo).resize((70, 70), Image.Resampling.LANCZOS)
    paste_centered(thumb, emblem, cx + 270, cy - 130)
    thumb_rgb = ImageEnhance.Contrast(thumb.convert("RGB")).enhance(1.05)
    small = thumb_rgb.resize((256, 144), Image.Resampling.LANCZOS)
    return thumb_rgb, small


def aircraft_cfg() -> str:
    return f"""[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\\\Asobo_A320_NEO"

; SkinMyBird generated variation — base_container assumes Official Asobo_A320_NEO.
[FLTSIM.0]
title = "{UNIQUE_TITLE}"
model = ""
panel = ""
sound = ""
texture = "{TEXTURE_NAME}"
kb_checklists = ""
kb_reference = ""
description = "SkinMyBird custom A320neo livery — HUCULEAKS AIR. Charcoal Official-albedo recolor, HUCULEAKS AIR on LIVERY_TEXTS side UV, full owl on neo/tail UV slots. BC7 DDS."
wip_indicator = 0
ui_manufacturer = "Airbus"
ui_type = "A320neo"
ui_variation = "HUCULEAKS AIR"
ui_typerole = "Commercial Airliner"
ui_createdby = "SkinMyBird"
atc_id = "YR-HUC"
atc_airline = "HUCULEAKS AIR"
atc_flight_number = "1"
icao_airline = "HUC"
isAirTraffic = 0
isUserSelectable = 1
"""


def convert_pngs_to_dds_m0(png_paths: list[Path], out_dir: Path, texconv: Path) -> list[Path]:
    """wine texconv BC7_UNORM -m 0 (all mips), rename to *.PNG.DDS."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "wine",
        str(texconv),
        "-f",
        "BC7_UNORM",
        "-m",
        "0",
        "-y",
        "-o",
        wine_z_path(out_dir),
    ] + [wine_z_path(p) for p in png_paths]
    env = {**os.environ, "WINEDEBUG": "-all"}
    print(f"texconv: converting {len(png_paths)} PNG → BC7 DDS (-m 0) …", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"texconv failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}")

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


def main() -> int:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(PRESET_PATH.read_text(encoding="utf-8"))
    registration = cfg.get("registration", "YR-HUC")

    for req in (
        LOGO_PATH,
        FONT_PATH,
        REF / "A320NEO_AIRFRAME_FUSELAGE_ALBD.PNG.png",
        REF / "A320NEO_AIRFRAME_WINGS_ALBD.PNG.png",
        REF / "A320NEO_AIRFRAME_ENGINES_ALBD.PNG.png",
        REF / "A320NEO_AIRFRAME_LIVERY_ALBD.PNG.png",
        REF / "official_thumbnail.jpg",
    ):
        if not req.exists():
            print(f"ERROR: missing {req}", file=sys.stderr)
            return 1

    logo = Image.open(LOGO_PATH).convert("RGBA")

    print("Recoloring Official albedos (luminance multiply) …", flush=True)
    fus = recolor_luminance_multiply(
        Image.open(REF / "A320NEO_AIRFRAME_FUSELAGE_ALBD.PNG.png"),
        FUSELAGE_TARGET,
        keep_dark_lt=0.07,
    )
    wings = recolor_luminance_multiply(
        Image.open(REF / "A320NEO_AIRFRAME_WINGS_ALBD.PNG.png"),
        WINGS_TARGET,
        keep_dark_lt=0.05,
    )
    engines = recolor_engines_with_orange_lip(
        Image.open(REF / "A320NEO_AIRFRAME_ENGINES_ALBD.PNG.png")
    )
    livery = make_livery_albd_clear()
    texts = make_livery_texts(logo, registration)

    images = {
        "A320NEO_AIRFRAME_FUSELAGE_ALBD": fus,
        "A320NEO_AIRFRAME_WINGS_ALBD": wings,
        "A320NEO_AIRFRAME_ENGINES_ALBD": engines,
        "A320NEO_AIRFRAME_LIVERY_ALBD": livery,
        "A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD": texts,
    }

    for stem, im in images.items():
        im.save(PREVIEW / f"{stem}.png", format="PNG")
        im.resize((512, 512), Image.Resampling.LANCZOS).convert("RGBA").save(
            PREVIEW / f"preview_{stem}.png"
        )

    package_root = OUT / PACKAGE_FOLDER
    if package_root.exists():
        shutil.rmtree(package_root)
    sim_aircraft = package_root / "SimObjects" / "Airplanes" / AIRCRAFT_FOLDER
    tex_dir = sim_aircraft / f"texture.{TEXTURE_NAME}"
    tex_dir.mkdir(parents=True, exist_ok=True)

    texconv = find_texconv()
    if texconv is None or not shutil.which("wine"):
        print("ERROR: wine+texconv required for BC7 DDS", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="huc_v2_") as tmp:
        tmp_path = Path(tmp)
        png_paths: list[Path] = []
        for stem, im in images.items():
            p = tmp_path / f"{stem}.png"
            im.save(p, format="PNG")
            png_paths.append(p)
        dds_list = convert_pngs_to_dds_m0(png_paths, tex_dir, texconv)
        for dds in dds_list:
            write_dds_json(dds)
        print(f"OK DDS: {len(dds_list)} maps via wine+{texconv.name}", flush=True)

    print("Building Asobo-style thumbnail …", flush=True)
    thumb, thumb_small = make_asobo_thumbnail(logo, registration)
    thumb.save(tex_dir / "thumbnail.jpg", quality=92, optimize=True)
    thumb_small.save(tex_dir / "thumbnail_small.jpg", quality=88, optimize=True)
    thumb.save(PREVIEW / "thumbnail.jpg", quality=92)
    thumb_small.save(PREVIEW / "thumbnail_small.jpg", quality=88)

    (tex_dir / "texture.cfg").write_text(texture_cfg(), encoding="utf-8")
    (sim_aircraft / "aircraft.cfg").write_text(aircraft_cfg(), encoding="utf-8")

    package_title = "SkinMyBird A320neo — HUCULEAKS AIR"
    (package_root / "manifest.json").write_text(
        json.dumps(manifest_json(cfg, package_title), indent=2), encoding="utf-8"
    )
    (package_root / "README_INSTALL_RO.md").write_text(
        readme_ro(cfg, PACKAGE_FOLDER, True), encoding="utf-8"
    )

    layout = build_layout(package_root)
    (package_root / "layout.json").write_text(json.dumps(layout, indent=2), encoding="utf-8")

    zip_path = OUT / f"{PACKAGE_FOLDER}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in package_root.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(OUT).as_posix())

    # DDS magic check
    for dds in tex_dir.glob("*.PNG.DDS"):
        magic = dds.read_bytes()[:4]
        ok = magic == b"DDS "
        print(f"  DDS magic {'OK' if ok else 'BAD'}: {dds.name} ({dds.stat().st_size} bytes)")
        if not ok:
            return 1

    print(f"PACKAGE: {package_root}")
    print(f"ZIP:     {zip_path}")
    print("UV placement:")
    print(f"  neo/tail owls → {A320NEO_TEXTS_UV['neo_logo_upper']} + {A320NEO_TEXTS_UV['neo_logo_lower']}")
    print(f"  side titles   → {A320NEO_TEXTS_UV['side_title_upper']} + mirrored {A320NEO_TEXTS_UV['side_title_lower']}")
    print(f"  registration  → {A320NEO_TEXTS_UV['reg_slot']}")
    print("Thumbnail: Official Asobo card recolored charcoal + owl on fin (light studio bg).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
