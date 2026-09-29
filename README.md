# SkinMyBird

**Canva for aircraft (and helicopters / balloons) in MSFS 2020** — no Photoshop required.

Commercial **one-time €9.99** tool: choose a model → colors / text / flags / custom textures / logo → live hangar preview → **Export ZIP** with real `*.PNG.DDS` (BC7) → **Install to Community**.

Brand: `brand/icon.png`.

---

## Preview disclaimer

The **3D hangar preview is approximate / for orientation only**. Materials, UVs, and lighting will not match MSFS. The real in-sim look comes from the **exported DDS livery** (Community package). When a mesh is a licensed stand-in (e.g. light GA for the Cessna stub, A350 GLB for A330), the UI shows a **Preview stand-in** badge.

---


### v0.8.9 notes
- **Aft hard-clip**: windowband / belly stop at `aftClipU=0.24` (mirror of nose cockpit clip). Tail fin + HT claim strengthened so fuselage/windowband colors no longer smear into empennage. Majority vote prefers tail on mixed triangles. Shader cache `smb_body_zone_shader_v089`.
- **Main text vs ID**: separate UI panels — Title/Slogan keep font/size/color/style; Registration has its own font, size, color (`regColor`), and style. Changing one never changes the other.
- **L/R text intensity**: MeshBasicMaterial `toneMapped:false` + explicit white; removed directional canvas drop-shadow that looked dimmer on the shaded fuselage side.
- **Textures → tail logos**: stickers UX rewritten — logo/image goes on the **vertical stabilizer only**, centered by default, with scale / opacity / rotate / fin nudge / side L|R|Both / optional tint. Free-body sticker placement removed.
- Cache-bust `?v=0.8.9`.

### v0.8.8 notes
- **Nose hard-clip** at cockpit line (`noseClipU = 0.78` + crown early): window band + fuselage stop behind windscreen; solid yellow nose forward.
- **Wing / HT bleed**: wings claim just outside tube shield with taller inboard root; tail/HT classified before wings so stabilizers stay Tail purple.
- **Registration** has its own Font + Size controls (independent of Title).
- Shader cache key `smb_body_zone_shader_v088c` (tube shield from v0.7.5 kept). Cache-bust `?v=0.8.8`.

### v0.8.7 notes
- **Title/slogan letter gap via measureText**: keep v0.8.6 world placement (`ht ≤ max(ht*1.18, bandH*1.2)`, `yAim += bandH*0.08`, no downward nudge). On the includeSlogan canvas: `descent = actualBoundingBoxDescent` (fb `titlePx*0.25`), slogan `ascent = actualBoundingBoxAscent` (fb `sPx*0.8`); `clearGap = max(titlePx*0.28, sPx*0.22, ch*0.045)`; `titleY ≈ ch*0.26`; `sloganY = titleY + descent + clearGap + ascent`; clamp slogan bottom ≤ `ch*0.58` and shrink fonts if needed (never drop into bottom half / grow world H). Mild nose-ward `xMain += fusLen*0.02` (solidMaxX clamped). Goal: clear gap under y-descender + full slogan on window band (not fairing) on A320/787.
- Paint zone shader cache key still `smb_body_zone_shader_v075`. Cache-bust `?v=0.8.7`

### v0.8.6 notes
- **Combined title+slogan wing-clear**: v0.8.5 `ht*1.62` + `yAim -= ht*0.14` dropped the panel into the wing-root fairing (A320/787 `wing_clear` FAIL). Keep world H near title-only (`ht*1.18` / `bandH*1.2`); nudge aim **up** (`yAim += bandH*0.08`); pack both lines in the **upper ~55%** of the texture (`titleY≈ch*0.28`, `gap=max(titlePx*0.82,sPx*0.55,ch*0.08)`, slogan `~0.34·titlePx`) with transparent bottom pad. Goal: A320+787 full “Fly your story” on window band ahead of wing + clear letter gap; 737 stays PASS.
- Paint zone shader cache key still `smb_body_zone_shader_v075`. Cache-bust `?v=0.8.6`

### v0.8.5 notes
- Combined title+slogan canvas: taller world panel + lower aim + larger 2D gap (letter clearance). Regressed A320/787 wing_clear — superseded by v0.8.6.
- Paint zone shader cache key still `smb_body_zone_shader_v075`. Cache-bust `?v=0.8.5`

### v0.8.4 notes
- **Under-title slogan = title canvas (no separate decal)**: when Slogan zone is Mid / under-title, do **not** mount a second slogan panel. Draw “Fly your story” as a second line on the same `makeRoleTexture` title canvas (clear 2D gap) and project only that one panel at the title window-band hit — slogan inherits title X/Y/orientation, so it cannot drift into the wing-root fairing (fixes A320/787 mirrored fairing ghost). Other slogan zones (aft, nose, belly, …) keep a separate `mountRole`. Registration stays aft.
- Text raycasts exclude wing / fairing / engine meshes when multi-mesh targets exist (single-mesh GLBs unchanged).
- Paint zone shader cache key still `smb_body_zone_shader_v075`. Cache-bust `?v=0.8.4`

### v0.8.3 notes
- **Under-title slogan wing-root fix**: Mid / under-title slogan no longer uses large `titlePanelH/2 + ~0.32·panelH + sloganH/2` drop into the wing-root fairing. Prefer Y just below title bottom with a **modest gap** (~0.10·titleH / ~0.14·bandH); share title X (forward of wing LE, never slide aft); clamp Y above `wingY + margin` when craft metrics exist. A320neo + 787 must show full “Fly your story”; 737 still clear; no title overlap.
- Mid zone `yBias` softened −0.55 → −0.18. Paint zone shader cache key still `smb_body_zone_shader_v075`. Cache-bust `?v=0.8.3`

### v0.8.2 notes
- **Under-title slogan clearance**: when Slogan zone is Mid / under title (or near the title), aim Y is forced below the title decal using title panel height — gap ≥ ~0.32·titlePanelH (~0.55–0.7 glyph) or ~0.40·bandH; slogan shares title X; raycasts that climb into the title fall back to a plane at the lower Y.
- Slightly smaller slogan canvas font (0.42× title px) and panel scale (0.58) so “Fly your story” fits under “SkinMyBird” on Window band.
- Paint zone shader cache key still `smb_body_zone_shader_v075` (tube shield unchanged). Cache-bust `?v=0.8.2`

### v0.8.1 notes
- Hangar `fitAircraftToHangar`: fuselage axis from vertical-fin offset (not merely longest extent) so A350/787 no longer map wings→+X; always flip so nose=+X (fixes 747 aft/nose).
- Text/sticker raycasts: all craft meshes + looser Ny + PlaneGeometry flank fallback; role Y stacking (slogan below title, reg lower); panel auto-shrink inside solid fuselage interval.
- Fonts: canvas `ctx.font` prefers exact Google Font family names after `document.fonts.load`.
- Paint zone shader cache key still `smb_body_zone_shader_v075` (tube shield unchanged).

### v0.8.0 notes
- **Text UX redesign**: named positioning zones per Title / Slogan / Registration (Window band, Forward cabin, Mid, Aft, Nose, Tail fin, Belly). Separate decals per role so zones actually move text.
- **Airline fonts**: Montserrat (default), Oswald, Bebas Neue, Anton, Roboto Condensed, PT Sans Narrow, Helvetica-like; Comic Sans removed. Google Fonts loaded before canvas draw (`document.fonts.ready`).
- **Larger title**: default XL / 200% scale (up to XXL / 350%); `fitFontPx` floor raised so long airline names stay readable along the fuselage.
- **Stickers / logos**: removed fixed Place-on Fuselage/Wings/Tail/Belly. Free Nose↔Tail + Low↔High aim with raycast on craft surface; Side Left/Right/Both; Scale / Opacity / Rotate.
- Paint zone shader (v0.7.5 tube shield / body classify) untouched. Cache-bust `?v=0.8.0`

### v0.7.5 notes
- **Fuselage tube shield**: if `absZ <= fuseHalf*1.25`, skip geometric under-wing pod, geometric pylon, and wings rules (tube points never become wings/engines). Seed hits still allowed only when `absZ > fuseHalf`.
- **Wings**: require `absZ > fuseHalf*1.6` (~`halfZ*0.35`) and tighten near-plane to `abs(y-wingY) < sy*0.06` (was `0.15`). Winglet tip rule kept.
- **Geometric pylon**: `fuseHalf*1.45 < absZ < halfZ*0.48`, `y ∈ [wingY-sy*0.28, wingY+sy*0.015]`, and `y < bandLo` (no climb into windowband).
- **Under-wing pod**: `absZ > fuseHalf*1.35` and `y < wingY - sy*0.03` (strictly below wing).
- Windowband stripe unchanged. Cache key `smb_body_zone_shader_v075`. Cache-bust `?v=0.7.5`

### v0.7.4 notes
- **Single-mesh nacelles**: under-wing pod rule (`absZ > fuseHalf*1.2`, below wing plane, wing-station `u`) + larger `engineR` so A320-style one-mesh airliners paint solid engines (not fuselage white on nacelles). Seeds/pylons kept as extras.
- **Constant-height windowband**: `bandLo/Hi = wingY + span*{0.30,0.52}` on fuselage tube sides (exclude crown/belly); synced JS `classifyPoint` + GLSL `smbClassifyCraft`. Cache key `smb_body_zone_shader_v074`.
- Custom textures / text layout unchanged. Cache-bust `?v=0.7.4`

### v0.7.3 notes
- **Smooth parametric zones**: body meshes use `MeshStandardMaterial` + `onBeforeCompile` fragment classification (craft-local `classifyPoint`) — continuous windowband / belly edges; no face-split stair-steps. Wings / winglets / engines stay solid role materials (no white nacelle teeth).
- **Custom textures visible**: fuselage aim matches title path (forward of wing LE + windowband mid); multi-X side raycasts; PlaneGeometry hard fallback if raycast misses.
- Stage height clamped so Textures tab does not blow hangar canvas tall. Cache-bust `?v=0.7.3`

### v0.7.2 notes
- Custom texture uploads remount when Image finishes loading (no silent skip); larger default decal; wider fuselage/windowband raycast targets.
- Paint zones: vertex majority vote + light body-mesh subdivision + tighter parametric bands (less jagged windowband).
- Larger fuselage title/slogan/registration defaults (`panelLen` ~0.24·fusLen, `textScale` 155%, title ~0.90·bandH). Cache-bust `?v=0.7.2`

### v0.7.1 notes
- **Simpler paint zones** (8 face zones): Fuselage, Nose, Belly, Window band, Wings, Winglets, Engines, Tail. Merged accent/doors/fairings/crown/cockpit/stabilizer/pylons into nearest parent.
- **Stickers removed** from UI and hangar drawing. **Flags kept** and expanded (~49 nations, EU focus + major world).
- **3 custom texture slots** (upload PNG/JPG, opacity/scale/X/Y, place on Fuselage/Wings/Tail/Belly).
- **3 text zones**: Title (large on window band), Slogan (under title), Registration (aft). Larger default title scale / panel height.
- Keep wing-relative windowband height from v0.6.16 for title placement. Cache-bust `?v=0.7.1`

### v0.6.14 notes
- **QA fix FAIL_TITLE_CLIPPED (left S missing on white)**: shared title X hit both sides blindly; left band steps earlier into nose taper / off-band white.
- Fit title in solid interval (nose=+X): `gap=max(0.06·fusLen,0.22)`, `xAftMin=wingLeX+gap`, `xFwdMax=center.x+size.x·0.14`, `panelLen≈fusLen·0.17` clamped to `0.88·span`; `xMain` mid-interval with aft/fwd edge guarantees.
- **Per-side title X**: independent candidate ladder (`xMain±…`, `center.x+size.x·{0.12,0.10,0.08}`); prefer hit with `userData.paintZone==='windowband'`; fallback accent/fuselage at band Y.
- Vertical: keep band-mid `yAim`; `titlePanelH` ≤ **0.60×bandH**. Long airline names (>10 chars): `panelLen×0.92`.
- Keep wing-relative windowband height + zone paint `tWing` ranges. Cache-bust `?v=0.6.14`

### v0.6.13 notes
- Title mid-cabin on solid windowband (clear of nose taper); shorter panel; wing-LE safe clamps.
- Cache-bust `?v=0.6.13`

### v0.6.12 notes
- **QA fix FAIL_TITLE_CLIPPED + band too low**: raising `vTube` alone still put the cyan belt near the wing root because band height is relative to craft `min.y` (gear/belly), not the wing plane.
- Root fix: `classifyPoint` windowband / accent / crown use **wing-relative** `tWing = (y − wingY) / (fuseTop − wingY)` — windowband **tWing 0.28–0.55**, accent **0.18–0.28**, crown **tWing > 0.62**; doors **tWing 0.02–0.18** (below accent); belly keeps `vTube < 0.22`; band only for **u 0.18–0.88** (avoid nose-taper jag).
- Title: nose-ward `xMax = center.x + size.x×0.30` (was 0.38); keep `yAim` = band mid **0.50** + prefer hit nearest yAim; `titlePanelH` ≤ **0.65×bandH**; stronger decal stroke `px×0.08` / `rgba(0,0,0,0.55)`.
- Keep multi-X / wing-LE `xMain`. Cache-bust `?v=0.6.12`

### v0.6.11 notes
- **QA fix FAIL_BAND_TOO_LOW**: cyan windowband paint sat below the true cabin window line; title aimed mid-upper so white glyphs straddled the band top onto white fuselage (half invisible).
- Raise `classifyPoint` windowband to `vTube` **0.54–0.66** (thicker + higher); accent **0.48–0.54**; crown only `vTube > 0.68` (low w); doors upper bound **<0.48** so they do not steal the band; belly `<0.22`; cockpit unchanged.
- Title `yAim`: after local wb union, **`min.y + bandH×0.50`** + `bandH×(posY×0.12)`; `titlePanelH` clamp **~0.55–0.70 of bandH** (prefer ~0.62); hit ranking = minimize `|point.y − yAim|` (not max Y).
- Keep multi-X title fallback, `maxNy` 0.52, wing-LE `xMain`, `panelLen≈fusLen×0.24`. Cache-bust `?v=0.6.11`

### v0.6.10 notes
- **QA fix FAIL title missing**: v0.6.9 `yAim` at band `0.72` + high probe + `maxNy` 0.4 rejected upper-tube side normals at forward `xMain` → zero title hits (reg aft still OK).
- Title **multi-X fallback** (like reg): try `xMain`, `xMain−0.04/0.08×fusLen`, then `center.x+0.20/0.16/0.12×size.x`; prefer X forward of `wingLeX−panelLen×0.25`, last-resort closer to LE; log which X hit.
- Softer **mid-band yAim** `min.y+bandH×0.58` (+`posY`); Y ladder aim/−8%/+8%/−18%/+15%/mid; prefer highest among hits `≥min.y+bandH×0.35`; `yBandFloor=min.y+bandH×0.15`.
- Title casts `maxNy` **0.52** (reg stays 0.4); `panelLen≈fusLen×0.24`; wing LE from **root-near** wing AABBs (close to `center.z`).
- Keep windowband paint **0.50–0.60**. Cache-bust `?v=0.6.10`

### v0.6.9 notes
- **QA fix FAIL_TOO_LOW**: cyan windowband paint + title sat on the lowest forward tube / wing-root line.
- Raise `classifyPoint` windowband to `vTube` **0.50–0.60** (true cabin window line); accent **0.44–0.50**; belly `<0.22`, crown `>0.62` unchanged.
- Title `yAim`: union of windowband meshes near title X (`±max(panelLen*0.6, 0.15*fusLen)`), aim **upper third** `min.y + bandH*0.72` + `bandH*(posY*0.15)`; prefer higher cast hits; allow fuselage side meshes at that height.
- Keep v0.6.8 wing-LE `xMain`, `panelLen ≈ fusLen*0.22`, clamps, aft registration filter.
- Cache-bust `?v=0.6.9`

### v0.6.8 notes
- **QA fix FAIL_CROPPED_BY_WING**: compute wing leading-edge X from wing mesh AABBs (`max.x`, nose=+X) and place title forward of that with a visible gap, instead of a fixed `center.x + size.x * 0.24`.
- Shorter panel: `panelLen ≈ fusLen * 0.22` (was 0.28) so the panel aft edge stays clear of the wing LE.
- Clamp `xMain` to cabin (`0.08…0.38 × size.x` ahead of center); keep v0.6.6/0.6.7 windowband `yAim`, band-height probes, `maxNy` 0.4. Registration stays aft (`x < xMain - 0.05×size.x`).
- Cache-bust `?v=0.6.8`

### v0.6.7 notes
- **QA fix FAIL_CROPPED_BY_WING**: title was still clipped by the wing LE on some side views (even on cyan windowband).
- Move title further forward: `xMain ≈ center.x + size.x * 0.24` (range 0.22–0.26, was 0.18).
- Shorter panel: `panelLen ≈ fusLen * 0.28` (range 0.26–0.30, was 0.33) so the panel cannot overlap the wing root.
- Keep v0.6.6 windowband-only `yAim` (band AABB mid) and band-height Y probes; registration stays aft on the same band.
- Both sides, L→R, no crown.
- Cache-bust `?v=0.6.7`

### v0.6.6 notes
- **Deterministic window-band placement**: title + registration aim only at the cabin window line — not the teal strip above the wing root.
- **`sideBeltMeshes`**: only `paintZone` in `{windowband, accent}`; fallback `fuselage` **only if no windowband**. Never belly / crown / cockpit / fairings / wings for side casts.
- **`yAim`**: midpoint of windowband world AABB union `(min.y+max.y)/2`. Y probes ±8%/±15% of **band height** only (no craft-`size.y` dives). Reject hits with `|Ny|>0.4` or `point.y < yAim - bandH`.
- Title X forward cabin `center.x + size.x * 0.18`; panelLen `fusLen * 0.33`; panelH ~0.55–0.75 of band height. Reg ~0.9–1.2 m wide on same `yAim` ladder (aft multi-X; fuselage side OK if band missing aft).
- Removed soft miss path that accepted belly/low fuselage. L→R, both sides, no crown.
- Cache-bust `?v=0.6.6`

### v0.6.5 notes
- **QA fix**: v0.6.4 raised aim Y into crown/shoulder so hard-rejects (`paintZone crown` / `|Ny|>0.45`) dropped **both** SkinMyBird and YR-EUG on both sides.
- Aim Y preferred **`paintZone==="windowband"`** mesh world bbox center (slightly below); craft-bbox fallback used moderate `beltBase` **0.04**.
- Broader Y probe ladder (modest down −0.04…−0.12×size.y) + soft miss pass (`|Ny|<=0.55`). Superseded by v0.6.6 band-height probes.
- Keep airliner layout: forward `xMain` (~0.13), shorter panel (`fusLen * 0.38`), no crown, L→R flips, multi-X aft registration.
- Identity airline/registration projects without requiring Stickers→Text.
- Cache-bust `?v=0.6.5`

### v0.6.4 notes
- **Airline title placement (A320-style)**: title aims at the **window-band** on the mid-side wall, **forward of the wing** (between nose and wing LE) — not at the wing root.
- Raised defaults: `textPosY` **+8**, `beltBase` **0.10**; shorter fuselage panel (`fusLen * 0.36`); forward X (`center.x + size.x * 0.15`).
- Y probes prefer belt → slight up → modest down; removed aggressive low probes (`-0.22/-0.28`); reject hits below wing-plane estimate.
- Registration stays aft on the **same raised belt** (not dropped toward the wing).
- Cache-bust `?v=0.6.4` (superseded by 0.6.5/0.6.6/0.6.7)

### v0.6.3 notes
- **Aft registration visibility**: Live hangar now probes several aft X stations (0.18 / 0.22 / 0.28 / 0.32 × fuselage length behind center) plus lower-Y belt samples so YR-… marks land on true lateral skin when the window-band ends aft of the wing.
- Forward fallback (still aft of airline title) if all aft probes miss; hard-rejects crown/cockpit/belly and `|worldNormal.y| > 0.45` unchanged. Airline title placement from v0.6.2 is untouched.
- Cache-bust `?v=0.6.3`

### v0.6.2 notes
- **Fuselage side text (critical)**: airline title + aft registration project onto the **true lateral fuselage** (window-band / side skin), never the crown/roof ridge.
- Side-decal targets prefer `windowband` > `fuselage` > `accent` > `doors` (optional fairings); **exclude** `crown`, `cockpit`, `belly`, wings, engines, tail.
- Raycast hard-rejects crown/cockpit/belly zones and faces with `|worldNormal.y| > 0.45`; aims at mid-tube window belt with lower-Y fallbacks.
- Flip checkboxes stay default **unchecked** (v0.6.1 orientation). Default `textPosY` remains **-10** (slightly below mid-side on the wall).
- Cache-bust `?v=0.6.2`

### v0.6.1 notes
- **Hangar text orientation**: after face-split DecalGeometry U, neither fuselage side needs a default U-flip — airline + registration read L→R from outside with both Text-tab flip checkboxes **unchecked**. Checkboxes remain as manual "fix if still mirrored" overrides (XOR auto, which is none).
- Side decal raycast prefers windowband/fuselage (penalizes crown ridge); zone-split meshes get bounding volumes for reliable hits.
- Cache-bust `?v=0.6.1`

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

## Models v0.6.14 (selector)

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
   - Commercial → `http://127.0.0.1:5173/?v=0.6.14`
   - Personal → `http://127.0.0.1:5174/?v=0.6.14`

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

© SkinMyBird v0.6.14 — commercial + personal editions · GLB hangar · Two-Tone
