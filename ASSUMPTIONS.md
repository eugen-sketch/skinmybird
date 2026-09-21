# Assumptions (v0.3 — multi-aircraft)

## General MSFS 2020
1. Community textures must be **`*.PNG.DDS` (BC7_UNORM + mips)** + **`*.PNG.DDS.json`** + **`thumbnail.jpg` / `thumbnail_small.jpg`** + **`texture.cfg`**. Plain PNG → white/blue default.
2. Exporter: Pillow 2048² → `texconv -f BC7_UNORM` (wine pe Linux, nativ pe Windows) → rename `*.PNG.DDS`.
3. Default Community path (Eugen):  
   `C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community`  
   (junction → `D:\MSFS2020\Community`).
4. texconv tipic: `C:\Users\eugen\Downloads\texconv.exe` sau `tools/texconv.exe`.
5. **Nu redistribuim** Official DDS Asobo (~60MB+) în git. `output/` e gitignored.

## Profile paint modes
| Mode | Când | Comportament |
|------|------|----------------|
| `uv_rects` | UV cunoscute | Titluri / logo în recturi măsurate |
| `whole_albedo` | UV necunoscute | Recolor solid pe role + logo/text centrat pe fuselage |

## Asobo A320neo (`asobo-aircraft-a320-neo`)
- `base_container = ..\Asobo_A320_NEO`
- Stem-uri Official `A320NEO_AIRFRAME_*_ALBD`
- **LIVERY_TEXTS UV** (nu pe plafonul fuselajului): vezi `exporter.export.A320NEO_TEXTS_UV` / `profiles/…uv_rects`
- Thumbnail Asobo-style ~1618×582 studio deschis

## LatinVFR A319 CEO (`lvfr-airbus-a319-ceo`)
- `base_container = ..\lvfr-319-cfm` (folderul de bază e adesea `lvfr-319-cfm`)
- Stem-uri: `FUSELAGE19`, `TAIL19`, `CFM56D`, aripi…
- UV din `work/build_a319_huculeaks.py` / preset `huculeaks-air-a319-lvfr.json`

## Stub-uri (whole_albedo) — v1 MVP
Pentru A321neo, A330-900, FBW A320, B787-10, B747-8i, PMDG 736, HPG Balloon, **HPG H135**:
- Stem-urile din `profiles/*.json` sunt **approximate** — Eugen trebuie să le alinieze cu `texture.cfg` / folderul de pe PC după instalarea add-on-ului.
- `base_container` poate diferi pe instalări (PMDG, HPG, FBW). Verifică numele folderului din `SimObjects`.
- H135 → `SimObjects/Rotorcraft`; Balloon → `SimObjects/Misc`.
- Paint: solid pe role (fuselage/wings/engines/tail) + logo centrat pe corp + text airline jos.

## Browser vs server
- UI pe `python server.py` apelează `/api/export` → DDS real.
- `npm run start:static` (http.server) — previzualizare OK, Export DDS necesită API.

## Thumbnails
Card stil Asobo (siluetă airliner / helicopter / balloon pe fundal studio deschis).
