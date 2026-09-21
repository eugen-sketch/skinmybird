# Assumptions (Phase 1 v0.2 — DDS)

1. **base_container** = `..\Asobo_A320_NEO` — standard Official folder name for default A320neo.
2. **Texture filenames** match community / Official paint names:
   - `A320NEO_AIRFRAME_FUSELAGE_ALBD`
   - `A320NEO_AIRFRAME_WINGS_ALBD`
   - `A320NEO_AIRFRAME_ENGINES_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD`
3. **MSFS 2020 Community reality (validated):** the sim loads **`*.PNG.DDS` (BC7_UNORM + mips)** plus **`*.PNG.DDS.json`** sidecars (`Version` 2, `FL_BITMAP_COMPRESSION`, `FL_BITMAP_MIPMAP`), **`thumbnail.jpg` / `thumbnail_small.jpg`**, and **`texture.cfg`** with Asobo / DetailMap / Glass fallbacks. **Plain PNG albedo maps are ignored** → white/blue default airframe.
4. **Exporter default success path:** generate 2048² albedo PNG in memory → `wine texconv.exe -f BC7_UNORM` → rename to `*.PNG.DDS` → write JSON sidecars + thumbnails + `layout.json`. Typical size **~5.5 MB per map** (matches validated Eugen Orange build). Fallback `--force-png` + `convert_to_dds` helper is not the happy path.
5. **Tail color** on the fuselage texture is an approximation (real rudder UV is split across fuselage + wings).
6. **No redistribution** of unmodified Official Asobo DDS (~60MB+) in git. `output/` and `*.zip` are gitignored. User-PC recolor of Official albedos remains personal-use only.
7. **layout.json** date field uses Windows FILETIME-style integers (common Community tooling convention).
8. **Browser ZIP** cannot call texconv; it ships high-res PNG + thumbnails + `convert_to_dds.ps1`. Real in-sim liveries should come from the Python exporter on a box/PC with texconv.
9. **Product still needs** paintkit UV editor / Official albedo recolor for production-quality panel lines and logos. Current DDS maps are zone-colored SkinMyBird albedos that the sim *does* load (unlike PNG).
