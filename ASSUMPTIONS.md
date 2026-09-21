# Assumptions (Phase 1 v0.3 — Official UV + Asobo thumbs)

1. **base_container** = `..\Asobo_A320_NEO` — standard Official folder name for default A320neo.
2. **Texture filenames** match community / Official paint names:
   - `A320NEO_AIRFRAME_FUSELAGE_ALBD`
   - `A320NEO_AIRFRAME_WINGS_ALBD`
   - `A320NEO_AIRFRAME_ENGINES_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD`
3. **MSFS 2020 Community reality (validated):** the sim loads **`*.PNG.DDS` (BC7_UNORM + mips)** plus **`*.PNG.DDS.json`** sidecars (`Version` 2, `FL_BITMAP_COMPRESSION`, `FL_BITMAP_MIPMAP`), **`thumbnail.jpg` / `thumbnail_small.jpg`**, and **`texture.cfg`** with Asobo / DetailMap / Glass fallbacks. **Plain PNG albedo maps are ignored** → white/blue default airframe.
4. **Exporter default success path:** generate 2048² albedo PNG in memory → `wine texconv.exe -f BC7_UNORM` → rename to `*.PNG.DDS` → write JSON sidecars + thumbnails + `layout.json`. Typical size **~5.5 MB per map** (matches validated Eugen Orange / HUCULEAKS AIR builds). Fallback `--force-png` + `convert_to_dds` helper is not the happy path.
5. **LIVERY_TEXTS UV (critical — do not fake):** measured Official alpha blobs on `A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD` (see `exporter.export.A320NEO_TEXTS_UV`):
   - **Tail logos** (replace stylized “neo”): `neo_logo_upper` ≈ `(95,14)–(1991,283)` and `neo_logo_lower` ≈ `(95,284)–(1991,552)` — port + starboard vertical stabilizer.
   - **Fuselage SIDE titles** (replace “AIRBUS A320” / “unbeatable fuel efficiency”): `side_title_upper` ≈ `(52,603)–(1560,817)` and `side_title_lower` ≈ `(52,818)–(1560,1031)` — **never** paint large airline titles on the fuselage albedo (that maps to the **roof/top**).
   - Smaller glyph bands below → leave empty or use only for registration (`reg_slot`).
6. **Fuselage / wings / engines albedos:** prefer **luminance-multiply recolor of Official** maps (keeps panel shading). Flat fake UV fills are last resort.
7. **LIVERY_ALBD:** clear default blue neo / engine overlay paint to transparent (or charcoal-compatible) so it does not fight the recolored engines.
8. **Thumbnails MUST be Asobo-style cards:** ~`1618×582`, **3/4 aircraft on light gray studio background** with soft ground shadow — **not** black-on-black silhouette graphics. Prefer recoloring `official_thumbnail.jpg` or compositing a clean aircraft photo onto a light studio plate.
9. **No redistribution** of unmodified Official Asobo DDS (~60MB+) in git. `output/` and `*.zip` are gitignored. User-PC / box recolor of Official albedos remains personal-use only.
10. **layout.json** date field uses Windows FILETIME-style integers (common Community tooling convention).
11. **Browser ZIP** cannot call texconv; it ships high-res PNG + thumbnails + `convert_to_dds.ps1`. Real in-sim liveries should come from the Python exporter on a box/PC with texconv.
