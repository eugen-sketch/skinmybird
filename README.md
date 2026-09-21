# SkinMyBird

**Canva pentru avioane (și elicoptere / baloane) în MSFS 2020** — fără Photoshop.

Instrument comercial **one-time €9.99**: alegi modelul → culori / stickere / text / logo → previzualizare live → **Export ZIP** cu `*.PNG.DDS` (BC7) real → **Instalează în Community**.

Brand: `brand/icon.png`.

---

## Modele v1 (selector)

| # | Profil | Paint |
|---|--------|-------|
| 1 | Asobo A320neo | UV măsurat (LIVERY_TEXTS) |
| 2 | LatinVFR A319 CEO | UV (FUSELAGE19 / TAIL19) |
| 3 | LatinVFR A321neo | whole-albedo stub |
| 4 | LatinVFR A330-900 | whole-albedo stub |
| 5 | FlyByWire A320neo | whole-albedo stub |
| 6 | Asobo Boeing 787-10 | whole-albedo stub |
| 7 | Asobo Boeing 747-8i | whole-albedo stub |
| 8 | PMDG 737-600 | whole-albedo stub |
| 9 | HPG Hot Air Balloon | whole-albedo stub |
| 10 | **HPG Airbus H135** | whole-albedo stub |

Profile JSON: `profiles/*.json`. Detalii UV / stub: `ASSUMPTIONS.md`.

---

## Cum rulezi (Windows — recomandat)

1. Instalează Python 3.11+ și (opțional) creează `.venv`, apoi:
   ```bat
   pip install -r requirements.txt
   ```
2. Asigură-te că există `texconv.exe` (DirectXTex), tipic:
   `C:\Users\eugen\Downloads\texconv.exe`
3. Dublu-click pe **`SkinMyBird.bat`** (sau `scripts\Start-SkinMyBird.ps1`).
4. Browser: `http://127.0.0.1:5173`

Variabile opționale:
- `SKINMYBIRD_TEXCONV` — cale texconv
- `SKINMYBIRD_COMMUNITY` — default  
  `C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community`  
  (junction tipic: `D:\MSFS2020\Community`)

### Flux UI (RO)
1. **Alege modelul** (carduri)
2. **Culori / Stickere / Identitate** (înmatriculare, airline, logo)
3. **Export ZIP (DDS)** → descarcă pachet Community
4. **Instalează în Community** → copiază în folderul Community (doar pe Windows cu calea setată)

---

## Cum rulezi (Linux / box de dezvoltare)

```bash
cd /path/to/skinmybird
source .venv/bin/activate
pip install -r requirements.txt
export SKINMYBIRD_TEXCONV=/workspace/tools/texconv.exe   # sau tools/texconv.exe
python server.py
# → http://127.0.0.1:5173
```

Sau: `./scripts/start_dev.sh` · `npm start`

### Export CLI
```bash
python -m exporter.export --list-profiles
python -m exporter.export --preset eugen-orange --profile asobo-aircraft-a320-neo --zip
python -m exporter.export --preset eugen-orange --profile hpg-airbus-h135 --zip --force-png
```

---

## API

| Metodă | Path | Rol |
|--------|------|-----|
| GET | `/api/profiles` | Lista celor 10 profile |
| GET | `/api/profiles/{id}` | Profil complet |
| POST | `/api/export` | Export Community (+ ZIP) |
| POST | `/api/install` | Copiază în Community |
| GET | `/api/health` | texconv / wine status |

---

## Instalare în MSFS 2020

1. Copiază folderul din `output/skinmybird-…` în **Community**.
2. Restart MSFS 2020.
3. Selectează modelul → variația SkinMyBird.

**Fără `*.PNG.DDS` (BC7) + `.json` + thumbnail → fuselaj alb/albastru.**

---

## Structură

```
skinmybird/
  profiles/           # JSON per aeronavă (10)
  web/                # UI Canva RO
  exporter/export.py  # Pillow → wine/native texconv BC7
  server.py           # FastAPI
  SkinMyBird.bat      # launcher Windows
  scripts/Start-SkinMyBird.ps1
  presets/
  ASSUMPTIONS.md
```

Remote: https://github.com/eugen-sketch/skinmybird

© SkinMyBird v0.3 — multi-aircraft MVP
