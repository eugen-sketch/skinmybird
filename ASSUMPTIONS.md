# Assumptions (v0.3.1 — texture stems from packages / public verification)

## General MSFS 2020
1. Community textures must be **`*.PNG.DDS` (BC7_UNORM + mips)** + **`*.PNG.DDS.json`** + **`thumbnail.jpg` / `thumbnail_small.jpg`** + **`texture.cfg`**. Plain PNG → white/blue default.
2. Exporter: Pillow 2048² → `texconv -f BC7_UNORM` (wine pe Linux, nativ pe Windows) → rename `*.PNG.DDS`.
3. Default Community path (Eugen):  
   `C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community`  
   (junction → `D:\MSFS2020\Community`).
4. texconv tipic: `C:\Users\eugen\Downloads\texconv.exe` sau `tools/texconv.exe`.
5. **Nu redistribuim** Official DDS Asobo (~60MB+) în git. `output/` e gitignored.
6. PC scan helper: `work/pc_scripts/Scan-MSFS-Textures.ps1` → Desktop `\SkinMyBird\scan\texture_scan.json`.

## Profile paint modes
| Mode | Când | Comportament |
|------|------|----------------|
| `uv_rects` | UV cunoscute | Titluri / logo în recturi măsurate |
| `whole_albedo` | UV necunoscute | Recolor solid pe role + logo/text centrat pe fuselage |

Exporter path: `SimObjects/{simObjectType}/{aircraft_folder}/texture.{slug}/` — `simObjectType` from profile (`Airplanes` / `Rotorcraft` / `Misc`).

## Asobo A320neo (`asobo-aircraft-a320-neo`)
- `base_container = ..\Asobo_A320_NEO`
- Stem-uri Official `A320NEO_AIRFRAME_*_ALBD`
- **LIVERY_TEXTS UV** (nu pe plafonul fuselajului): vezi `exporter.export.A320NEO_TEXTS_UV` / `profiles/…uv_rects`
- Thumbnail Asobo-style ~1618×582 studio deschis

## LatinVFR A319 CEO (`lvfr-airbus-a319-ceo`)
- `base_container = ..\lvfr-319-cfm` (folderul de bază e adesea `lvfr-319-cfm`)
- Stem-uri: `FUSELAGE19`, `TAIL19`, `CFM56D`, aripi…
- UV din `work/build_a319_huculeaks.py` / preset `huculeaks-air-a319-lvfr.json`

## FlyByWire A320neo (`flybywire-aircraft-a320-neo`) — VERIFIED
- Package: `D:\MSFS2020\Community\flybywire-aircraft-a320-neo`
- Airplane folder: **`FlyByWire_A320_NEO`**
- `base_container = ..\FlyByWire_A320_NEO`
- Stems (same Asobo names): `A320NEO_AIRFRAME_FUSELAGE_ALBD`, `WINGS`, `ENGINES`, `LIVERY`, `LIVERY_TEXTS` — **no separate TAIL**
- Source: `flybywiresim/aircraft` `_FlyByWire_A320_NEO-LIVERY/TEXTURE.FBW`
- `texture.cfg` fallback.1=`..\..\FlyByWire_A320_NEO\TEXTURE`
- paint_mode still `whole_albedo` (UV can later reuse Asobo LIVERY_TEXTS)

## Asobo 787-10 (`asobo-boeing-787-10`) — VERIFIED (public templates)
- Airplane folder: **`Asobo_B787_10`**
- `base_container = ..\Asobo_B787_10`
- Stems: `787_10_AIRFRAME_FUSELAGE1_ALBD`, `FUSELAGE2`, `TAIL`, `WINGS`, `ENGINE`, `LIVERY1`
- Official Steam package may be named `asobo-aircraft-b787-10*` (confirm on PC); Newlight packages are lighting FX, not the airframe
- Source: Project-Mega-Pack/base-livery-templates + community Azur ZIP

## Asobo 747-8i (`asobo-aircraft-b7478i`) — VERIFIED (public templates + forum rename)
- Package hint: `...\Official\Steam\asobo-aircraft-b7478i`
- Airplane folder: **`Asobo_B747_8i`**
- `base_container = ..\Asobo_B747_8i`
- Stems: `747_8I_AIRFRAME_FUSELAGE_ALBD` (post-SU; old kits used `HULL_ALBD`), `BELLY`, `ENGINEBODY`, `WING`, `WINGFLAPS`, `LIVERY`
- Confirm on PC that Official uses **FUSELAGE** not **HULL**

## HPG H135 (`hpg-airbus-h135`) — PARTIAL
- Package: `D:\MSFS2020\Community\hpg-airbus-h135`
- **`simObjectType = Airplanes`** (NOT Rotorcraft — community liveries prove this)
- Main exterior stem: **`H135_ID1_DIFFUSE`**
- `base_container` / exact airplane folder name under `SimObjects\Airplanes\` **must be confirmed on PC** (varies by HPG build)
- Additional `H135_ID*` maps likely — PC scan required

## HPG Hot Air Balloon (`hpg-hotair-balloon`) — PARTIAL
- Package: `D:\MSFS2020\Community\hpg-hotair-balloon`
- Official guide: `base_container` → `hpg-hotair-balloon`; fallback `..\..\hpg-hotair-balloon\texture`
- Tentative envelope stem: `BALLON_ENVELOPE_ALBEDO` (spelling BALLON) — **confirm on PC**
- `simObjectType` set to Airplanes pending PC confirm (was Misc stub)
- Night: emissive layer required (paintkit Multiply workflow)

## PMDG 737-600 (`pmdg-aircraft-736`) — PARTIAL
- Package: `...\Official\Steam\pmdg-aircraft-736`
- Airplane folder / base: **`PMDG 737-600`**
- Fallbacks (official HowTo): `texture.vc`, `texture.common`, `texture.600`
- **`textures[]` empty** until PC scan — do not guess ALBD stems

## LatinVFR A321neo / A330-900 — PENDING PC
- Packages under Official Steam: `lvfr-airbus-a321-neo`, `lvfr-a330-900`
- **`textures[]` empty** until PC scan (A319 pattern FUSELAGE19 is not assumed for neo/330)
- `base_container` may be a short SimObjects folder name (cf. A319 `lvfr-319-cfm`)

## Browser vs server
- UI pe `python server.py` apelează `/api/export` → DDS real.
- `npm run start:static` (http.server) — previzualizare OK, Export DDS necesită API.

## Thumbnails
Card stil Asobo (siluetă airliner / helicopter / balloon pe fundal studio deschis).

## PC access note (2026-09-21)
Executor subagent was **box-scoped** (no `machineId` / ListMachines / CopyToBox). Profiles above for FBW/787/747/H135/Balloon/PMDG use public package/docs verification where possible; **LVFR A321/A330 + PMDG ALBD stems + exact H135/Balloon airplane folders still need Desktop PC scan**. Sync to `C:\Users\eugen\Desktop\SkinMyBird\profiles` also requires machine tools.
