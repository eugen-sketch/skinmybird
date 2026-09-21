# SkinMyBird

**Recolorează livery-urile default Asobo A320neo în MSFS 2020 — fără Photoshop, fără drama.**

Instrument comercial **one-time €9.99** (Windows-friendly): UI local tip Canva în browser + exporter Python CLI. Alegi culorile pe zone (fuselaj / aripi / motoare / coadă), adaugi stickere sau o poză, apeși Generate → pachet **Community** gata de copiat.

Brand: iconița bird-pilot din `brand/icon.png`.

---

## English (short)

SkinMyBird is a commercial **€9.99 one-time** tool: recolor the default Asobo A320neo, add stickers/photos, export a ready Community folder package.

**Critical MSFS fact:** Community textures must be **`*.PNG.DDS` (BC7)** + **`*.PNG.DDS.json`** + **`thumbnail.jpg` / `thumbnail_small.jpg`** + **`texture.cfg`** with Asobo fallbacks. Plain PNG placeholders are **ignored** → white/blue default fuselage. The Python exporter emits real DDS via **wine + texconv** when available.

Validated in-game: **Eugen Orange** (`#FF6A00` fuselage, `YR-EUG`).

### Run the UI
```bash
npm start
# or: cd web && python3 -m http.server 5173
# open http://localhost:5173
```

### Export with Python (DDS — recommended)
```bash
cd /path/to/skinmybird
source .venv/bin/activate
python -m exporter.export --preset eugen-orange --zip
# → output/skinmybird-a320neo-eugen_orange/  (+ .zip)
# Files: A320NEO_AIRFRAME_*_ALBD.PNG.DDS + .json + thumbnails
```

Requires: `Pillow`, and for DDS: `wine` + `/workspace/tools/texconv.exe` (or `SKINMYBIRD_TEXCONV`).  
Fallback: `--force-png` writes PNG + `convert_to_dds.ps1` / `scripts/convert_to_dds.sh`.

### Install in MSFS 2020
1. Copy the package folder into **Community**.
2. Restart MSFS 2020.
3. Select Airbus A320neo → your SkinMyBird variation.

---

## Produs (RO)

| | |
|---|---|
| Preț | **€9.99** one-time |
| Platformă | Windows (UI în browser + CLI Python) |
| Avion | Asobo A320neo (variație `base_container`) |
| Demo | **Eugen Orange** — fuselaj/coadă `#FF6A00`, aripi `#111111`, motoare `#222222`, `YR-EUG` |

### Cum rulezi UI-ul
```bash
npm start
```
Deschide `http://localhost:5173`. Layout Canva: unelte stânga, previzualizare live în centru.

### Cum exporți pachetul
- **UI:** Descarcă pachet ZIP — Community-shaped, thumbnail-uri din canvas, PNG 2K + `convert_to_dds.ps1`.
- **CLI (recomandat pentru joc):** `python -m exporter.export --preset eugen-orange --zip` → **DDS BC7** real.

### Instalare în MSFS 2020
1. Copiază folderul pachet (ex. `skinmybird-a320neo-eugen_orange`) în **Community**.
2. Restart MSFS.
3. Alege A320neo → livery-ul tău.

**Fără `*.PNG.DDS` texturile nu apar** (alb/albastru). Citește `README_INSTALL_RO.md` din pachet.

---

## Structură pachet (validată)

```
skinmybird-a320neo-<slug>/
  manifest.json
  layout.json
  README_INSTALL_RO.md
  SimObjects/Airplanes/skinmybird_a320neo_<slug>/
    aircraft.cfg          # [VARIATION] base_container = "..\Asobo_A320_NEO"
    texture.<slug>/
      texture.cfg         # fallback Asobo + DetailMap/Glass/...
      A320NEO_AIRFRAME_FUSELAGE_ALBD.PNG.DDS
      A320NEO_AIRFRAME_FUSELAGE_ALBD.PNG.DDS.json
      A320NEO_AIRFRAME_WINGS_ALBD.PNG.DDS (+ .json)
      A320NEO_AIRFRAME_ENGINES_ALBD.PNG.DDS (+ .json)
      A320NEO_AIRFRAME_LIVERY_ALBD.PNG.DDS (+ .json)
      A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.PNG.DDS (+ .json)
      thumbnail.jpg
      thumbnail_small.jpg
```

Dimensiuni tipice DDS: **~2–6 MB / mapă** (2048² BC7 + mips). Nu commităm texturi Official (~60MB+) în git; `output/` e gitignored.

---

## Asumpții / reguli UV (v0.3)
Vezi `ASSUMPTIONS.md`. Pe scurt:

- **Titlurile** (ex. HUCULEAKS AIR) → pe **`LIVERY_TEXTS`** UV (laterale fuselaj), **nu** pe albedo-ul de fuselaj (ajung pe plafon/top).
- **Logo-uri pe coadă** → sloturile Official **neo** (`neo_logo_upper` / `neo_logo_lower`) pe `LIVERY_TEXTS`.
- **Thumbnail-uri** → carduri stil Asobo: avion 3/4 pe fundal studio deschis (~1618×582), **nu** siluete pe negru.
- Constante UV: `exporter.export.A320NEO_TEXTS_UV`.
- DDS + sidecars + thumbnail = obligatorii pentru MSFS 2020.

---

## Roadmap
1. Editor UV pe albedo Official (recolor pe PC-ul utilizatorului, fără redistribuire).
2. Mai multe avioane default Asobo.
3. Suport **MSFS 2024**.
4. Instalare one-click Windows + licență €9.99.

---

## Dev

```
skinmybird/
  brand/icon.png
  web/                 # UI static Canva-like (RO)
  exporter/export.py   # CLI → PNG.DDS via wine+texconv
  scripts/convert_to_dds.sh
  presets/eugen-orange.json
  output/              # generate (gitignored)
```

Remote: `https://github.com/eugen-sketch/skinmybird`

```bash
npm start
python -m exporter.export --preset eugen-orange --zip
```

© SkinMyBird — Phase 1 v0.2 (DDS)
