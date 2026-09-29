# SkinMyBird v0.8.13 — MSFS export bake scale

## Verdict: fixed (bake pixels)

Hangar XXL/title at textScale 200% now bakes into **2× UV rects** with **accent/textColor** (orange). Fin logo diam **580** (~0.61 of mid-chord ~950px).

### Scale factors
| Item | Before (0.8.12) | After (0.8.13) |
|------|-----------------|----------------|
| Title UV (upper) | 820×90 | 1500×180 (×2.00) |
| Title color | #FFFFFF | #E85A00 |
| Font cap | 96px hard | fills rect height |
| Fin logo diam | 420 | 580 |
| Fin chord fraction | 0.44 | 0.61 |

### Bake formula
`bake_scale = clamp(textSizeMul(size) × textScale/100, 0.85, 2.0)`
- S/M/L/XL/XXL muls match hangar `textSizeMul`
- Default editor XL@200% → 2.30 → clamp **2.00**

### Previews
- Before fuselage: `work/export_diag/huc_FUSELAGE19.png`
- After fuselage: `work/scale_diag_0813/after_FUSELAGE19.png`
- Compare title: `work/scale_diag_0813/before_after_title.png`
- Compare tail: `work/scale_diag_0813/before_after_tail.png`
