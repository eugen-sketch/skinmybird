# eToro Autotrader (DEMO)

Bot care tranzacționează automat pe **contul DEMO eToro** (bani virtuali), cu Stop Loss și Take Profit pe fiecare ordin,
și îți scrie pe Telegram la fiecare deschidere/închidere. Rulează gratuit pe GitHub Actions, la 10 minute, luni–vineri.

**Siguranță:** codul refuză orice cale de tranzacționare care nu conține `/demo/` (vezi `etoro.py`), deci nu poate atinge contul real.

## Cum funcționează
- Semnal: RSI(14) pe bare de 1 oră, din date Yahoo. RSI < 20 → BUY, RSI > 80 → SELL (revenire din extreme).
- Mărime: calculată pe un cont virtual de **140 $** (`virtual_equity`), risc ~4% pe tranzacție, marjă ≤ 40%, levier ≤ 10 (petrol).
- Ieșire: SL (3.5×ATR), TP (2.5×ATR) sau după 48 h. Max 2 poziții, oprire zilnică la -8%, oprire totală sub 60% din cont.
- Fără chei eToro rulează în **mod hârtie** (simulare locală), cu aceleași reguli.

## Rezultate din teste (date reale, 2 ani, 1h)
Nu am găsit o strategie cu avantaj dovedit. Pe forex/aur/commodities, simulările stricte (intrare la deschiderea barei următoare,
costuri incluse, antrenare/test separate) au ieșit sub 1.0 profit factor. Setările din `config.json` sunt cele mai bune găsite pe
petrol, dar au ieșit pe minus în prima jumătate a perioadei. Botul este deci un **test pe demo**, nu o strategie validată.

## Pornire
1. eToro → creează chei API (Demo) → `ETORO_API_KEY`, `ETORO_USER_KEY`.
2. GitHub → Settings → Secrets → Actions: adaugă cele 2 chei (+ `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
3. Actions → *Oil backtest* → Run workflow, `script = etoro_check.py` → verifică conexiunea (și cu `test_trade = 1` un ordin de test pe demo).
4. Actions → *eToro autotrader (demo)* → pornește singur la 10 minute.

Fișiere: `trader.py` (motor), `etoro.py` (client demo), `etoro_check.py` (verificare), `research_*.py` (teste de strategie), `config.json`.
