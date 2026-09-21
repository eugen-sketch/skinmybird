# Assumptions (Phase 1)

1. **base_container** = `..\Asobo_A320_NEO` — standard Official folder name for default A320neo.
2. **Texture filenames** match community paint guides:
   - `A320NEO_AIRFRAME_FUSELAGE_ALBD`
   - `A320NEO_AIRFRAME_WINGS_ALBD`
   - `A320NEO_AIRFRAME_ENGINES_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_ALBD`
   - `A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD`
3. **PNG placeholders** are not flight-ready; MSFS expects DDS. Package structure is valid so the variation appears in the aircraft selector; textures may magenta/fallback until DDS.
4. **Tail color** on the 2D mock / fuselage placeholder is an approximation (real rudder UV is split).
5. **No redistribution** of Asobo copyrighted paintkit assets — only our generated placeholders.
6. **layout.json** date field uses Windows FILETIME-style integers (common Community tooling convention).
