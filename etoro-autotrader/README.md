# eToro Autotrader (DEMO)

Tranzacționează automat pe **contul DEMO eToro** (bani virtuali), cu Stop Loss pe fiecare ordin, și îți scrie pe Telegram la
fiecare pas. Rulează gratuit pe GitHub Actions (~la 18 minute, luni–vineri). Codul refuză orice cale de tranzacționare fără `/demo/`.

## Strategia actuală: revenire pe indici (RSI2 zilnic)
- Indici: S&P 500, Nasdaq 100, Dow Jones, DAX, FTSE 100 (eToro: SPX500, NSDQ100, DJ30, GER40, UK100).
- **Cumpără** când RSI(2) zilnic < 5 și prețul e peste media pe 100 de zile (scădere bruscă într-o piață în urcare).
- **Vinde (închide)** când RSI(2) > 50, sau după 10 zile, sau la Stop Loss (2,5 × volatilitatea zilnică).
- Doar cumpărări (long). Cont virtual de 140 $: expunere ~1.010 $ pe poziție (minim eToro), levier 20, **maxim 2 poziții**.
- Acționează o dată pe zi, după 07:30 UTC, pe baza ultimei bare zilnice încheiate.

## Ce arată testele (date reale, ~23 ani, costuri incluse)
- Alese pe ferestre 2005–2015, verificate pe ferestre 2016–2025. 100 din 144 variante au mediană pozitivă în ambele perioade.
- Pe 140 $ și ferestre de 1 an: ~16–26% din ani ies pe minus, mediana ≈ +50 $, cel mai rău decil ≈ −50 $.
- **Nimic din asta nu garantează profit.** Expunerea minimă de 1.000 $ înseamnă ~7× efect de levier pe un cont de 140 $.
- Forex, aur, argint și petrol (1h și zilnic) au ieșit slabe/negative în teste și nu mai sunt folosite. Vezi `research_*.py`.

## Fișiere
`trader.py` (motor), `etoro.py` (client demo), `config.json` (strategia actuală), `config_forex.json` (varianta veche),
`messages.py` (mesaje Telegram), `research_*.py` (teste), `daily_status.py` (semnale curente).
