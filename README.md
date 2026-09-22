# SkinMyBird

**Canva for aircraft (and helicopters / balloons) in MSFS 2020** — no Photoshop required.

Commercial **one-time €9.99** tool: choose a model → colors / stickers / text / logo → live hangar preview → **Export ZIP** with real `*.PNG.DDS` (BC7) → **Install to Community**.

Brand: `brand/icon.png`.

---

## Preview disclaimer

The **3D hangar preview is approximate / for orientation only**. Materials, UVs, and lighting will not match MSFS. The real in-sim look comes from the **exported DDS livery** (Community package). When a mesh is a licensed stand-in (e.g. light GA for the Cessna stub, A350 GLB for A330), the UI shows a **Preview stand-in** badge.

---


### v0.6.0 notes
- **Face-solid GLB paint**: zones assigned per triangle (face centroid), split into one mesh/material per zone — **no vertex-color blur** between zones.
- **Crown/spine coverage** fixed (wider high-Y / low-|Z| classify) so the roof ridge is never left white.
- **Zone highlight**: hover or focus a Colors field to pulse that zone on the 3D model; click the plane to focus its zone input.
- Higher preview clarity: pixel ratio up to 2.5, brighter key/fill, flat solid materials.
- Cache-bust `?v=0.6.0`

### v0.5.8 notes
- **Two editions (one codebase)**: **Commercial** (default) = Airbus + Boeing fixed-wing airliners only; **Personal** = same + H135 helicopter, hot-air balloon, Cessna 172 stub.
- Launchers: `SkinMyBird.bat` → commercial on **:5173**; `SkinMyBird-Personal.bat` → personal on **:5174**. Env: `SKINMYBIRD_EDITION`, `SKINMYBIRD_PORT`.
- Profile JSON tagged with `"edition": "commercial"|"personal"`; UI header badge shows which edition is running.
- Cache-bust `?v=0.5.8`

### v0.5.6 notes
- **Hangar GLB paint zones**: single-material airframes (A320/737/747/787/…) recolor by **vertex geometry region** (wings / engines / tail / nose / belly / …), not the old fuselage-only tint. Procedural path unchanged.
- Cache-bust `?v=0.5.6`

### v0.5.5 notes
- **747**: clean CC-BY hangar GLB from **God's Eye View** (`airplane.glb` → `b747.glb`; credit zairiq-123). Plain light gray; Two-Tone paint overrides via `prepareGlbForSkinning`. FetchCFD Korean Air GLB stays removed.
- Cache-bust `?v=0.5.5`

### v0.5.4 notes
- **747**: FetchCFD Korean Air GLB **removed** — hangar uses **improved procedural 747** only (clear upper-deck hump, 4 engines, tall fin). No `b747.glb` is served; Korean Air branding cannot appear.
- Cold-start **Two-Tone** defaults: primary `#f2f4f7` (fuselage/nose/belly/tail/stab/doors/windowband/accent) + secondary `#1b2430` (wings/winglet/engines); **Team stripe OFF**
- **Eugen Orange preset removed** (UI button, `EUGEN` object, `presets/eugen-orange.json`)
- More paint zones grouped **Body / Flying surfaces / Details**: fuselage, nose, belly, tail, wings, winglets, horizontal stabilizer, engines, doors, cabin window band, stripe accent
- Cache-bust `?v=0.5.4`

### v0.5.3 notes
- **747 clean airframe**: FetchCFD 747 GLB still used (hump + 4 engines); at load we hide embossed Korean Air titles/logos and neutralize brand-colored materials so hangar paint is a blank canvas
- Cold-start **Pearl Grey** defaults (soft silver fuselage, charcoal wings, soft-blue accent) — no matte-black Graphite
- **Flags → Free** range widened to **−150…150** with stronger X/Y travel across the fuselage
- **Eugen Orange — 3 colors** preset: orange fuselage/nose, charcoal wings/engines/tail, cream accent stripe
- HQ text: fuselage **2048×1024**, reg **1024×256**, decals **2048×512**, mipmaps + anisotropy, higher base font px
- Cache-bust `?v=0.5.3`

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

## Models v0.6.0 (selector)

| # | Profile | Paint | Hangar GLB |
|---|---------|-------|------------|
| 1 | Asobo A320neo | UV measured (LIVERY_TEXTS) | a320.glb (amvlab) |
| 2 | LatinVFR A319 CEO | UV (FUSELAGE19 / TAIL19) | a320.glb |
| 3 | LatinVFR A321neo | whole-albedo stub | a320.glb |
| 4 | LatinVFR A330-900 | whole-albedo stub | a350.glb *(stand-in)* |
| 5 | FlyByWire A320neo | whole-albedo stub | a320.glb |
| 6 | Asobo Boeing 787-10 | whole-albedo stub | b787.glb |
| 7 | Asobo Boeing 747-8i | whole-albedo stub | b747.glb (God's Eye View CC BY 4.0) |
| 8 | PMDG 737-600 | whole-albedo stub | b737.glb |
| 9 | HPG Hot Air Balloon *(personal)* | whole-albedo stub | procedural |
| 10 | HPG Airbus H135 *(personal)* | whole-albedo stub | procedural |
| 11 | Cessna 172 preview stub *(personal)* | whole-albedo stub | cessna.glb *(GA stand-in)* |

Rows 1–8 ship in **commercial** (product for sale). Rows 9–11 are **personal-only** extras (still in the repo; hidden when `SKINMYBIRD_EDITION=commercial`).

Profile JSON: `profiles/*.json` (`"edition"` field). UV / stub details: `ASSUMPTIONS.md`.

### 3D model attribution

- **amvlab** A320 / 737 / 787 / A350 — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — https://github.com/amvlab/aircraft-models
- **Boeing 747** hangar — God's Eye View `airplane.glb` ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), zairiq-123) → `b747.glb`
- **Cessna 172** (light-GA) — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — https://github.com/bilawalsidhu/gods-eye-view

Full notes: `web/models/ATTRIBUTION.txt`.

---

## Editions (Commercial vs Personal)

One codebase — two launchers. Do **not** fork the repo.

| Launcher | Edition | Port | Aircraft |
|----------|---------|------|----------|
| **`SkinMyBird.bat`** | **Commercial** (default, for sale) | **5173** | Airbus + Boeing **fixed-wing airliners** only |
| **`SkinMyBird-Personal.bat`** | **Personal** (Eugen private) | **5174** | Commercial set **+** H135 helicopter, hot-air balloon, Cessna 172 stub |

- Env: `SKINMYBIRD_EDITION=commercial|personal`, `SKINMYBIRD_PORT` (defaults above).
- Commercial hides personal profiles in the selector / API; profile JSON files stay in `profiles/`.
- Header badge shows **Commercial** or **Personal** so you know which instance is open.
- Note: H135 is Airbus-branded but a **helicopter** → personal only. Commercial = airliners only.

## Run (Windows — recommended)

1. Install Python 3.11+ and (optional) create `.venv`, then:
   ```bat
   pip install -r requirements.txt
   ```
2. Ensure `texconv.exe` (DirectXTex) exists, typically:
   `C:\Users\eugen\Downloads\texconv.exe`
3. Double-click **`SkinMyBird.bat`** (commercial / sale) or **`SkinMyBird-Personal.bat`** (private extras).
4. Browser opens with cache-bust:
   - Commercial → `http://127.0.0.1:5173/?v=0.6.0`
   - Personal → `http://127.0.0.1:5174/?v=0.6.0`

Optional env vars:
- `SKINMYBIRD_EDITION` — `commercial` (default) or `personal`
- `SKINMYBIRD_PORT` — default `5173` (commercial bat) / `5174` (personal bat)
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
export SKINMYBIRD_EDITION=commercial   # or personal
export SKINMYBIRD_PORT=5173            # 5174 for personal
python server.py
# → http://127.0.0.1:$SKINMYBIRD_PORT
```

Or: `./scripts/start_dev.sh` · `npm start`

### CLI export

```bash
python -m exporter.export --list-profiles
python -m exporter.export --preset two-tone --profile asobo-aircraft-a320-neo --zip
python -m exporter.export --preset two-tone --profile hpg-airbus-h135 --zip --force-png
```

---

## API

| Method | Path | Role |
|--------|------|------|
| GET | `/api/profiles` | Profile list |
| GET | `/api/profiles/{id}` | Full profile |
| POST | `/api/export` | Community export (+ ZIP) |
| POST | `/api/install` | Copy into Community |
| GET | `/api/health` | version, **edition**, texconv / wine |
| GET | `/api/edition` | `{ edition, version }` |

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
  SkinMyBird.bat              # Commercial (:5173)
  SkinMyBird-Personal.bat     # Personal (:5174)
  scripts/Start-SkinMyBird.ps1
  presets/
  ASSUMPTIONS.md
```

Remote: https://github.com/eugen-sketch/skinmybird

© SkinMyBird v0.6.0 — commercial + personal editions · GLB hangar · Two-Tone
