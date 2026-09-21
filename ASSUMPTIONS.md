# Assumptions (v0.3.2 — PC scan 2026-09-21)

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

## FlyByWire A320neo (`flybywire-aircraft-a320-neo`) — PC SCAN 2026-09-21
- Package: `D:\MSFS2020\Community\flybywire-aircraft-a320-neo`
- Airplane folder: **`FlyByWire_A320_NEO`**
- `base_container = ..\FlyByWire_A320_NEO`
- Stems confirmed: `A320NEO_AIRFRAME_FUSELAGE_ALBD`, `WINGS`, `ENGINES`, `LIVERY`, `LIVERY_TEXTS` — **no separate TAIL**
- `texture.cfg` fallback.1=`..\..\FlyByWire_A320_NEO\TEXTURE`
- paint_mode still `whole_albedo` (UV can later reuse Asobo LIVERY_TEXTS)

## Asobo 787-10 (`asobo-boeing-787-10`) — PC SCAN PARTIAL 2026-09-21
- Airplane folder: **`Asobo_B787_10`** (export pattern kept)
- `base_container = ..\Asobo_B787_10`
- Stems (public templates, kept): `787_10_AIRFRAME_FUSELAGE1_ALBD`, `FUSELAGE2`, `TAIL`, `WINGS`, `ENGINE`, `LIVERY1`
- **Base package missing on this PC**; only liveries present (`Asobo_B787_10_Livery_*`). KLM ships `LIVERY1_ALBD` (+ LOD6) only → `verification.pc_scan_partial: true`

## Asobo 747-8i (`asobo-aircraft-b7478i`) — PC SCAN 2026-09-21
- Airplane folder: **`Asobo_B747_8i`**
- `base_container = ..\Asobo_B747_8i`
- **FUSELAGE confirmed** (not HULL): `747_8I_AIRFRAME_FUSELAGE_ALBD`, plus `ENGINEBODY`, `WING`, `WINGFLAPS`, `LIVERY`; `BELLY` kept from prior profile; BELLYDECAL skipped

## HPG H135 (`hpg-airbus-h135`) — PC SCAN 2026-09-21
- Package: `D:\MSFS2020\Community\hpg-airbus-h135`
- **`simObjectType = Airplanes`** (path uses `Simobjects\Airplanes`)
- Airplane folders: **`H-135 DEV SERIES PROJECT`** (main) + `H-135 DEV HIGH SKIDS`
- `airplane_folder` / `base_container = ..\H-135 DEV SERIES PROJECT`
- Main exterior stem: **`H135_ID1_DIFFUSE`** (texture.HPG, texture.POLICE, …)
- Fallback: `..\..\H-135 DEV SERIES PROJECT\texture`

## HPG Hot Air Balloon (`hpg-hotair-balloon`) — PC SCAN 2026-09-21
- Package: `D:\MSFS2020\Community\hpg-hotair-balloon`
- `Airplanes\hpg-hotair-balloon`; `base_container = ..\hpg-hotair-balloon`
- Envelope stem **CONFIRMED**: `BALLON_ENVELOPE_ALBEDO` (spelling BALLON); optional `BASKET_ALBEDO`
- Night: emissive layer required (paintkit Multiply workflow)

## PMDG 737-600 (`pmdg-aircraft-736`) — PC SCAN 2026-09-21
- Airplane folder / base: **`PMDG 737-600`**
- Fallbacks: `texture.vc`, `texture.common`, `texture.600`
- Exterior (texture.PMDG): `PMDG_NG3_F1_ALBD`, `F2`, `F3`, `TAIL`, `ENG`, `WINFR`
- Wings (texture.common): `PMDG_NG3_WINGL_ALBD`, `WINGR`

## LatinVFR A330-900 (`lvfr-a330-900`) — PC SCAN 2026-09-21
- Airplane folders: **`A330-900`**, `lvfr-339-rr`
- `base_container = ..\A330-900`
- Paint: `A330N1MAPPING_ALBEDO`, `N2`, `N3`, `A330TAIL_ALBEDO`, `330NEOENGINE_ALBEDO` (+ `_RIGHT`), `330NWINGLETS_ALBEDO`

## LatinVFR A321neo (`lvfr-airbus-a321-neo`) — PC SCAN 2026-09-21
- Primary folder: **`A321neoLEAP`** (also PW/LR variants)
- `base_container = ..\A321neoLEAP`
- Paint-relevant MVP stems: `A320NEO_AIRFRAME_FUSELAGE_ALBD`, `A321FUSELAGEDETAIL`, `DETAIL2`, `DETAIL3_B`, `ELEVATORWING_ALBEDO`
- Many Community liveries are thumbnail-only (fallback to base)

## Browser vs server
- UI pe `python server.py` apelează `/api/export` → DDS real.
- `npm run start:static` (http.server) — previzualizare OK, Export DDS necesită API.

## Thumbnails
Card stil Asobo (siluetă airliner / helicopter / balloon pe fundal studio deschis).

## PC access note (2026-09-21)
Executor subagent was **box-scoped** (no `machineId` / ListMachines / CopyFromBox). Profile updates below come from a **real PC scan of Eugen's MSFS packages** relayed by the parent (confirmed facts). Desktop sync of `profiles/` is left to the parent (`CopyFromBox`).

## Color zones v0.5.4 (UI → texture roles)

Hangar / editor paint zones (grouped Body / Flying surfaces / Details). Defaults are two colors only; extra zones inherit primary (`#f2f4f7`) or secondary (`#1b2430`) until the user changes them. Team stripe is **off** by default.

| UI zone | Preview behaviour | Export mapping (when UV stub has no dedicated slot) |
|---------|-------------------|-----------------------------------------------------|
| `fuselage` | Procedural fuselage canvas base; GLB primary | → fuselage albedo |
| `nose` (radome) | Canvas forward band + procedural radome mesh; GLB role | → `fuselage` albedo |
| `belly` | Procedural lower band on fuselage canvas | → `fuselage` albedo |
| `tail` | Vertical fin material / GLB aft heuristic | → `tail` or fuselage stub |
| `wings` | Wing panels / rotor | → `wings` albedo |
| `winglet` | Tip boxes + GLB name/heuristic | → `wings` albedo |
| `stabilizer` | Horizontal stabilizer mesh (own mat); GLB `stabil*` role | → `wings` or `tail` stub (best-effort) |
| `engines` | Nacelles | → engines / fuselage stub |
| `doors` | Canvas door outlines; GLB `door` role | → `fuselage` albedo (stub) |
| `windowband` | Canvas cabin band behind windows; GLB heuristic | → `fuselage` albedo (stub) |
| `accent` (stripe / cheatline) | Team-stripe colour when Stickers → Team stripe is on | → stripe fill; fallback `tail` |

Dedicated UV rects for nose/belly/winglet/stabilizer/doors/windowband are **not** measured yet on Asobo / third-party packages. Export stubs therefore tint the nearest existing stem.

## Hangar GLB mapping v0.5.4

| Family | File | Notes |
|--------|------|-------|
| A320 / A319 / A321 / FBW | `web/models/a320.glb` | amvlab CC BY 4.0 (nologo) |
| 737 / PMDG | `b737.glb` | amvlab nologo |
| 787 | `b787.glb` | amvlab nologo |
| A350 | `a350.glb` | amvlab nologo |
| A330 | `a350.glb` | **stand-in** |
| 747 | *(none)* | **procedural only** — FetchCFD Korean Air `b747.glb` deleted v0.5.4 |
| Cessna / GA stub | `cessna.glb` | CC BY 4.0 GA stand-in |
| H135 / balloon | procedural | no third-party GLB |

amvlab GLBs are logo-free; `prepareGlbForSkinning` still strips maps / neutralizes materials as a safety net.

Could not find a clearly commercial-licensed **exact Cessna 172** GLB in CC0/CC-BY downloadable form within this pass; the Small Airplane asset is used with an on-screen **Preview stand-in** label.
