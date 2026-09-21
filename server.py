#!/usr/bin/env python3
"""SkinMyBird local API — serves web/ + export / install / profiles."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
OUTPUT = ROOT / "output"
DEFAULT_COMMUNITY = Path(
    os.environ.get(
        "SKINMYBIRD_COMMUNITY",
        r"C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community",
    )
)

app = FastAPI(title="SkinMyBird", version="0.3.0")


class ExportRequest(BaseModel):
    profile_id: str = Field(..., description="Aircraft profile id")
    name: str = "Custom"
    registration: str = "YR-EUG"
    airline: str = "SkinMyBird"
    icao: str = "SMB"
    colors: dict[str, str] = Field(
        default_factory=lambda: {
            "fuselage": "#FF6A00",
            "wings": "#111111",
            "engines": "#222222",
            "tail": "#FF6A00",
        }
    )
    stickers: list[dict[str, Any]] = Field(default_factory=list)
    force_png: bool = False
    make_zip: bool = True
    logo: str | None = None


class InstallRequest(BaseModel):
    package_folder: str
    community: str | None = None


@app.get("/api/health")
def health() -> dict:
    from exporter.export import find_texconv

    tex = find_texconv()
    return {
        "ok": True,
        "version": "0.3.0",
        "texconv": str(tex) if tex else None,
        "wine": bool(shutil.which("wine")),
        "community_default": str(DEFAULT_COMMUNITY),
    }


@app.get("/api/profiles")
def api_profiles() -> dict:
    from exporter.profiles import list_profiles

    return {"profiles": list_profiles()}


@app.get("/api/profiles/{profile_id}")
def api_profile(profile_id: str) -> dict:
    from exporter.profiles import load_profile

    try:
        return load_profile(profile_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/presets")
def api_presets() -> dict:
    presets_dir = ROOT / "presets"
    items = []
    if presets_dir.is_dir():
        for p in sorted(presets_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            items.append({"id": p.stem, "name": data.get("name", p.stem), "data": data})
    return {"presets": items}


@app.post("/api/export")
def api_export(body: ExportRequest) -> dict:
    from exporter.export import export_package
    from exporter.profiles import load_profile

    try:
        profile = load_profile(body.profile_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e

    cfg = {
        "id": body.name,
        "name": body.name,
        "registration": body.registration,
        "airline": body.airline,
        "icao": body.icao,
        "colors": body.colors,
        "stickers": body.stickers
        or [
            {"type": "team_stripe", "enabled": True},
            {"type": "heart", "enabled": False},
            {"type": "custom_text", "enabled": True, "text": body.registration},
        ],
        "profile": body.profile_id,
        "logo": body.logo,
        "soacraPhoto": None,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        result = export_package(
            cfg,
            OUTPUT,
            zip_out=body.make_zip,
            force_png=body.force_png,
            profile=profile,
        )
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}") from e

    package_folder = result.stem if result.suffix == ".zip" else result.name
    package_path = OUTPUT / package_folder
    meta_path = package_path / "skinmybird_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    return {
        "ok": True,
        "result": str(result),
        "package_folder": package_folder,
        "zip": str(result) if result.suffix == ".zip" else None,
        "download_zip": f"/api/download/{package_folder}.zip" if body.make_zip else None,
        "used_dds": meta.get("used_dds"),
        "paint_mode": meta.get("paint_mode"),
        "texture_stems": meta.get("texture_stems"),
    }


@app.post("/api/export-form")
async def api_export_form(
    profile_id: str = Form(...),
    name: str = Form("Custom"),
    registration: str = Form("YR-EUG"),
    airline: str = Form("SkinMyBird"),
    icao: str = Form("SMB"),
    colors_json: str = Form("{}"),
    stickers_json: str = Form("[]"),
    force_png: bool = Form(False),
    make_zip: bool = Form(True),
    photo: UploadFile | None = File(None),
) -> dict:
    """Multipart export with optional logo/photo upload."""
    colors = json.loads(colors_json) if colors_json else {}
    stickers = json.loads(stickers_json) if stickers_json else []
    photo_path = None
    tmpdir = None
    if photo and photo.filename:
        tmpdir = tempfile.mkdtemp(prefix="smb_up_")
        photo_path = Path(tmpdir) / Path(photo.filename).name
        photo_path.write_bytes(await photo.read())

    body = ExportRequest(
        profile_id=profile_id,
        name=name,
        registration=registration,
        airline=airline,
        icao=icao,
        colors=colors
        or {
            "fuselage": "#FF6A00",
            "wings": "#111111",
            "engines": "#222222",
            "tail": "#FF6A00",
        },
        stickers=stickers,
        force_png=force_png,
        make_zip=make_zip,
    )
    try:
        from exporter.export import export_package
        from exporter.profiles import load_profile

        profile = load_profile(body.profile_id)
        cfg = {
            "id": body.name,
            "name": body.name,
            "registration": body.registration,
            "airline": body.airline,
            "icao": body.icao,
            "colors": body.colors,
            "stickers": body.stickers
            or [
                {"type": "team_stripe", "enabled": True},
                {"type": "custom_text", "enabled": True, "text": body.registration},
            ],
            "profile": body.profile_id,
            "soacraPhoto": str(photo_path) if photo_path else None,
        }
        OUTPUT.mkdir(parents=True, exist_ok=True)
        result = export_package(
            cfg,
            OUTPUT,
            zip_out=body.make_zip,
            photo=photo_path,
            force_png=body.force_png,
            profile=profile,
        )
        package_folder = result.stem if result.suffix == ".zip" else result.name
        return {
            "ok": True,
            "result": str(result),
            "package_folder": package_folder,
            "download_zip": f"/api/download/{package_folder}.zip" if body.make_zip else None,
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}") from e
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


@app.post("/api/install")
def api_install(body: InstallRequest) -> dict:
    from exporter.export import install_to_community

    package_root = OUTPUT / body.package_folder
    if not package_root.is_dir():
        # maybe zip-only
        raise HTTPException(404, f"Package folder not found: {body.package_folder}")
    community = Path(body.community) if body.community else DEFAULT_COMMUNITY
    try:
        target = install_to_community(package_root, community)
    except FileNotFoundError as e:
        # On Linux box Community path won't exist — return guidance
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": str(e),
                "hint": (
                    "Pe Windows, setează SKINMYBIRD_COMMUNITY sau folosește path-ul "
                    r"C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community"
                ),
                "package_folder": body.package_folder,
                "community": str(community),
            },
        )
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return {"ok": True, "installed": str(target)}


@app.get("/api/download/{filename}")
def api_download(filename: str):
    safe = Path(filename).name
    path = OUTPUT / safe
    if not path.is_file():
        # try folder zip
        raise HTTPException(404, f"File not found: {safe}")
    return FileResponse(path, filename=safe, media_type="application/zip")


# Static UI last so /api wins
if WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")


def main() -> None:
    import uvicorn

    host = os.environ.get("SKINMYBIRD_HOST", "127.0.0.1")
    port = int(os.environ.get("SKINMYBIRD_PORT", "5173"))
    print(f"SkinMyBird → http://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
