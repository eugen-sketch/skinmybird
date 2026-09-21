# SkinMyBird

**Recolorează livery-urile default Asobo A320neo în MSFS 2020 — fără Photoshop, fără drama.**

Instrument comercial **one-time €9.99** (Windows-friendly): UI local în browser + exporter Python CLI. Alegi culorile pe zone (fuselage / wings / engines / tail), adaugi stickere sau poza soacră, apeși Generate → pachet **Community** gata de copiat.

---

## English (short)

SkinMyBird is a commercial **€9.99 one-time** tool for lazy MSFS 2020 users: recolor the default Asobo A320neo, slap on stickers/photos, export a ready Community folder package. Phase 1 = local web UI + Python exporter with **placeholder PNG** albedo maps. Real DDS + official paintkit UV = next.

### Run the UI
```bash
cd web
python3 -m http.server 5173
# open http://localhost:5173
```

### Export with Python (recommended for `output/`)
```bash
cd /path/to/skinmybird
source .venv/bin/activate   # or: python3 -m venv .venv && pip install -r requirements.txt
python -m exporter.export --preset eugen-orange
python -m exporter.export --config presets/eugen-orange.json --zip
# → output/skinmybird-a320neo-eugen_orange/
```

### Install livery in MSFS 2020
1. Copy the generated package folder into your **Community** directory.
2. Restart MSFS 2020.
3. Select Airbus A320neo → your SkinMyBird variation.

**Note:** v0 ships PNG placeholders. The sim usually wants DDS — package may show in the menu while textures fall back to Asobo until you convert.

---

## Produs (RO)

| | |
|---|---|
| Preț | **€9.99** one-time |
| Platformă | Windows (UI în browser + CLI Python) |
| Avion v0 | Asobo A320neo (variație `base_container`) |
| Demo | **Eugen Orange** — fuselage/tail `#FF6A00`, wings `#111111`, engines `#222222` |

### Cum rulezi UI-ul
```bash
cd web
python3 -m http.server 5173
```
Deschide `http://localhost:5173`. Brand icon: `brand/icon.png`.

### Cum exporți pachetul
- Din UI: **Generate package (ZIP)** — descarcă un zip Community-shaped.
- Din CLI: `python -m exporter.export --preset eugen-orange` → scrie în `output/`.

### Instalare în MSFS 2020
1. Copiază folderul pachet (ex. `skinmybird-a320neo-eugen_orange`) în **Community**.
   - Steam tipic: `%APPDATA%\Microsoft Flight Simulator\Packages\Community\`
   - MS Store tipic: `%LOCALAPPDATA%\Packages\Microsoft.FlightSimulator_8wekyb3d8bbwe\LocalCache\Packages\Community\`
2. Restart MSFS.
3. Alege A320neo → livery-ul tău.

Citește și `README_INSTALL_RO.md` din pachetul generat.

---

## Structură pachet (Asobo variation)

```
skinmybird-a320neo-<slug>/
  manifest.json
  layout.json
  README_INSTALL_RO.md
  SimObjects/Airplanes/skinmybird_a320neo_<slug>/
    aircraft.cfg          # [VARIATION] base_container = "..\Asobo_A320_NEO"
    texture.<slug>/
      texture.cfg         # fallback către Asobo_A320_NEO\texture
      A320NEO_AIRFRAME_FUSELAGE_ALBD.png   # PLACEHOLDER
      A320NEO_AIRFRAME_WINGS_ALBD.png
      A320NEO_AIRFRAME_ENGINES_ALBD.png
      A320NEO_AIRFRAME_LIVERY_ALBD.png
      A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png
```

### Asumpții etichetate
- Numele folderului oficial: `Asobo_A320_NEO` (documentat pe larg în ghiduri Community).
- Numele texturilor urmează convenția din ghidurile de paint A320neo pe forumuri MSFS.
- Tail color pe placeholder = bandă aft pe „fuselage UV” mock (în realitate rudder-ul e split pe fuselage+wings).
- **Nu redistribuim paintkit Asobo** — doar template-uri / placeholder generate de noi.

---

## Roadmap
1. **DDS pipeline** — texconv (BC7/DXT5) + layout.json regenerat.
2. Paintkit UV real (legal) mapat pe zonele din UI.
3. Mai multe avioane default Asobo.
4. Suport **MSFS 2024** (materiale/texturi diferite față de 2020).
5. Instalare one-click Windows + licență €9.99.

---

## Dev

```
skinmybird/
  brand/icon.png
  web/                 # UI static
  exporter/export.py   # CLI
  presets/eugen-orange.json
  output/              # pachete generate (gitignored)
  requirements.txt
```

Remote hint: `https://github.com/eugen-sketch/skinmybird.git`

### Next steps pe PC-ul tău
1. Rulează exporterul, copiază în Community, verifică că livery-ul apare în listă.
2. Extrage DDS din Official (doar pentru uz personal) sau folosește paintkit legal → aliniază UV.
3. `texconv -f BC7_UNORM -y *.png` (sau DXT5) → înlocuiește PNG → regenerează `layout.json`.
4. Test in-sim pe fuselage/wings/engines/tail + stickere.

---

© SkinMyBird — MVP Phase 1
