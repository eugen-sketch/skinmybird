# SkinMyBird

**Canva for aircraft (and helicopters / balloons) in MSFS 2020** — no Photoshop required.

Commercial **one-time €9.99** tool: choose a model → colors / stickers / text / logo → live hangar preview → **Export ZIP** with real `*.PNG.DDS` (BC7) → **Install to Community**.

Brand: `brand/icon.png`.

---

## Preview disclaimer

The **3D hangar preview is approximate / for orientation only**. Materials, UVs, and lighting will not match MSFS. The real in-sim look comes from the **exported DDS livery** (Community package). When a mesh is a licensed stand-in (e.g. light GA for the Cessna stub, A350 GLB for A330), the UI shows a **Preview stand-in** badge.

---


### v0.5.2 notes
- **Single registration** aft on each side (no stacked double YR-… marks)
- **Flags → Free**: X/Y sliders show only in Free mode; Left/Both/Right unchanged
- Cold-start defaults are **graphite / dark grey** (Eugen Orange stays a preset)
- UI polish + cache-bust `?v=0.5.2`

### v0.5.1 notes
- English category badges: **Aircraft / Helicopter / Balloon** (no Romanian leftovers)
- Stickers default larger + **S / M / L** size control (canvas + GLB decals)
- **Flags** tab: ~33 country flags, placement left / right / both / free
- Text + stickers + flags use the same decal pipeline on all families (A320, 737, 787, 747, A330, Cessna, helo, balloon)
- 747 hangar: FetchCFD Boeing 747-3B5 GLB (hump + 4 engines); procedural fallback improved

## Models v0.5.2 (selector)

| # | Profile | Paint | Hangar GLB |
|---|---------|-------|------------|
| 1 | Asobo A320neo | UV measured (LIVERY_TEXTS) | a320.glb (amvlab) |
| 2 | LatinVFR A319 CEO | UV (FUSELAGE19 / TAIL19) | a320.glb |
| 3 | LatinVFR A321neo | whole-albedo stub | a320.glb |
| 4 | LatinVFR A330-900 | whole-albedo stub | a350.glb *(stand-in)* |
| 5 | FlyByWire A320neo | whole-albedo stub | a320.glb |
| 6 | Asobo Boeing 787-10 | whole-albedo stub | b787.glb |
| 7 | Asobo Boeing 747-8i | whole-albedo stub | **b747.glb** (FetchCFD 747-3B5 CC BY 4.0) |
| 8 | PMDG 737-600 | whole-albedo stub | b737.glb |
| 9 | HPG Hot Air Balloon | whole-albedo stub | procedural |
| 10 | HPG Airbus H135 | whole-albedo stub | procedural |
| 11 | Cessna 172 (preview stub) | whole-albedo stub | cessna.glb *(GA stand-in)* |

Profile JSON: `profiles/*.json`. UV / stub details: `ASSUMPTIONS.md`.

### 3D model attribution

- **amvlab** A320 / 737 / 787 / A350 — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — https://github.com/amvlab/aircraft-models
- **Boeing 747-3B5** via FetchCFD — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — https://www.fetchcfd.com/view/4833-boeing-747-3b5-3d-model
- **Cessna 172** (light-GA) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — https://github.com/bilawalsidhu/gods-eye-view

Full notes: `web/models/ATTRIBUTION.txt`.

---

## Run (Windows — recommended)

1. Install Python 3.11+ and (optional) create `.venv`, then:
   ```bat
   pip install -r requirements.txt
   ```
2. Ensure `texconv.exe` (DirectXTex) exists, typically:
   `C:\Users\eugen\Downloads\texconv.exe`
3. Double-click **`SkinMyBird.bat`** (or `scripts\Start-SkinMyBird.ps1`).
4. Browser: `http://127.0.0.1:5173`

Optional env vars:
- `SKINMYBIRD_TEXCONV` — texconv path
- `SKINMYBIRD_COMMUNITY` — default  
  `C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community`  
  (typical junction: `D:\MSFS2020\Community`)

### UI flow (English)

1. **Choose aircraft** (cards)
2. **Colors / Text / Stickers / Flags / Identity** (registration, airline, logo, country flags)
3. **Export ZIP (DDS)** → download Community package
4. **Install** → copy into Community (Windows only when path is set)

---

## Run (Linux / dev box)

```bash
cd /path/to/skinmybird
source .venv/bin/activate
pip install -r requirements.txt
export SKINMYBIRD_TEXCONV=/workspace/tools/texconv.exe   # or tools/texconv.exe
python server.py
# → http://127.0.0.1:5173
```

Or: `./scripts/start_dev.sh` · `npm start`

### CLI export

```bash
python -m exporter.export --list-profiles
python -m exporter.export --preset eugen-orange --profile asobo-aircraft-a320-neo --zip
python -m exporter.export --preset eugen-orange --profile hpg-airbus-h135 --zip --force-png
```

---

## API

| Method | Path | Role |
|--------|------|------|
| GET | `/api/profiles` | Profile list |
| GET | `/api/profiles/{id}` | Full profile |
| POST | `/api/export` | Community export (+ ZIP) |
| POST | `/api/install` | Copy into Community |
| GET | `/api/health` | texconv / wine status |

---

## Install in MSFS 2020

1. Copy the folder from `output/skinmybird-…` into **Community**.
2. Restart MSFS 2020.
3. Select the aircraft → SkinMyBird variation.

**Without `*.PNG.DDS` (BC7) + `.json` + thumbnail → white/blue default fuselage.**

---

## Structure

```
skinmybird/
  profiles/           # JSON per aircraft
  web/                # English Canva UI + GLB hangar
  exporter/export.py  # Pillow → wine/native texconv BC7
  server.py           # FastAPI
  SkinMyBird.bat      # Windows launcher
  scripts/Start-SkinMyBird.ps1
  presets/
  ASSUMPTIONS.md
```

Remote: https://github.com/eugen-sketch/skinmybird

© SkinMyBird v0.5.2 — single registration · flag free pos · grey defaults · English UI
