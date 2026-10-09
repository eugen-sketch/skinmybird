# Oil Signal Bot (eToro)

Bot care analizează petrolul (WTI `CL=F` și Brent `BZ=F`, date Yahoo Finance) și îți trimite pe **Telegram** semnale **BUY / SELL** cu Stop Loss și Take Profit sugerate. Tu plasezi manual ordinul pe eToro (instrumentul **OIL**) — eToro nu oferă API public de trading pentru conturi retail, deci botul doar notifică.

## Cum decide
Scor de la -5 la +5 pe ultima oră închisă: trend EMA20/EMA50, încrucișare EMA, MACD, RSI (supravândut/supracumpărat), benzi Bollinger. `scor >= 3` → BUY, `scor <= -3` → SELL. SL = 1.5×ATR, TP = 3×ATR. Primești notificare doar când semnalul **se schimbă** (fără spam). Praguri în `config.json`.

## Pornire
```bash
cd oil-signal-bot
pip install -r requirements.txt
cp .env.example .env      # completează TELEGRAM_BOT_TOKEN și TELEGRAM_CHAT_ID
python oilbot.py --test   # notificare de test
python oilbot.py          # rulează continuu (verifică la 15 min)
python oilbot.py --once   # o singură verificare (pentru cron)
```
Telegram: scrie @BotFather → `/newbot` → token; trimite un mesaj botului, apoi deschide `https://api.telegram.org/bot<TOKEN>/getUpdates` și copiază `chat.id`.

Ca să ruleze 24/7: un VPS / Raspberry Pi, sau cron: `*/15 * * * * cd /cale/oil-signal-bot && python oilbot.py --once`.

## Test
`pytest tests`

> Indicatorii tehnici nu garantează profit. Folosește Stop Loss, risc mic per tranzacție, testează întâi pe contul Demo eToro. Nu este sfat financiar. Prețul futures diferă ușor de CFD-ul OIL de pe eToro.
