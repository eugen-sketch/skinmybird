#!/usr/bin/env bash
# Convert PNG albedo maps in a texture folder to BC7 *.PNG.DDS via wine+texconv.
set -euo pipefail
TEXDIR="${1:?Usage: $0 <texture.folder>}"
TEXCONV="${SKINMYBIRD_TEXCONV:-/workspace/tools/texconv.exe}"
OUT="$(cd "$TEXDIR" && pwd)"
mapfile -t PNGS < <(find "$OUT" -maxdepth 1 -iname '*.png' | sort)
[[ ${#PNGS[@]} -gt 0 ]] || { echo "No PNGs in $OUT"; exit 1; }
ZOUT="Z:${OUT}"
ZPNGS=()
for p in "${PNGS[@]}"; do ZPNGS+=("Z:${p}"); done
WINEDEBUG=-all wine "$TEXCONV" -f BC7_UNORM -y -o "$ZOUT" "${ZPNGS[@]}"
for p in "${PNGS[@]}"; do
  stem=$(basename "$p" .png); stem=$(basename "$stem" .PNG)
  for cand in "$OUT/${stem}.DDS" "$OUT/${stem}.dds"; do
    if [[ -f "$cand" ]]; then mv -f "$cand" "$OUT/${stem}.PNG.DDS"; break; fi
  done
  cat > "$OUT/${stem}.PNG.DDS.json" <<JSON
{
  "Version": 2,
  "SourceFileName": "${stem}.PNG.DDS",
  "Flags": [
    "FL_BITMAP_COMPRESSION",
    "FL_BITMAP_MIPMAP"
  ]
}
JSON
  rm -f "$p"
done
echo "Done: $OUT"
