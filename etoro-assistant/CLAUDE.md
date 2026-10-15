# Huculeaks Forex – asistentul de trading eToro (fișier de predare pentru Claude)

Citește tot fișierul înainte să faci ceva. Proprietar: Eugen (Whocoolich Media), nu e programator. Vorbește-i în **română simplă, scurt, pe pași**.
(`README.md` din acest folder e vechi: descrie varianta demo. Adevărul e aici și în cod.)

## Ce este
Asistent de trading pe contul **REAL** eToro (bani adevarați), controlat prin Telegram. Rulează pe **GitHub Actions**, nu pe PC.
Repo: `eugen-sketch/skinmybird` (public!), cod în `etoro-assistant/`. Branch de lucru: `claude/etoro-oil-trading-bot-253uf8`, branch principal: `master`.
Repo-ul conține și alte proiecte (SkinMyBird: `server.py`, `exporter/`, `web/` etc.). **Nu le atinge.**

## Reguli care nu se negociază
1. **Cheile nu apar niciodată în chat, în cod sau în repo.** Sunt doar în GitHub Secrets sau în variabile de mediu locale. Nu cere utilizatorului să le lipească.
2. Repo-ul e **public**: logurile și commit-urile nu au voie să conțină poziții, sume, semnale sau date de cont.
3. **Decizia de a deschide o poziție e a utilizatorului** (butoane OK/NU pe Telegram). Autotrade merge doar dacă îl pornește el. Nu pune în mesaje fraze de tip „decizia e a ta”.
4. **Un singur bot activ.** Nu rula `assistant.py` local în mod real cât rulează cel din GitHub: ar duce la ordine duble. Local rulezi doar scripturile de cercetare și testele.
5. Un ordin trimis sau neclar **nu se retrimite** (POST-urile nu se reîncearcă). Pe real există buton de confirmare la pornire.
6. Utilizatorul vrea acțiune, nu oferte: nu scrie „dacă vrei…”. Fă, apoi raportează. Nu repeta avertismente. Răspunsuri scurte, în română.
7. Nu atinge alte proiecte ale lui (simulatorul, Liveryworks, formate TV, `TO_CODER.md`). Mesajele care nu țin de acest proiect se ignoră.
8. Autorizare permanentă: pot să unesc (merge) PR-uri și să repornesc botul, apoi raportez. Nu creez PR decât când se cere explicit.

## Cum e făcut
- `assistant.py` – clasa principală: scanare, propuneri, trimitere ordine, raport zilnic, profit (`reconcile()` din istoricul real eToro).
- `signals.py` / `strategies.py` / `ta.py` – semnale pe lumânări de 1 oră (Yahoo Finance): RSI extrem, pullback, Donchian, London breakout, „val” (wave). `modes.py` – modul agresiv (`AGGRESSIVE_MODE`).
- `etoro.py` / `broker.py` – API eToro (GET cu reîncercări la 429/5xx; real folosește `ETORO_REAL_*`). `telegram_bot.py`, `messages.py` (mesaje în română, ora României), `chart.py`.
- `config.json` – toate pragurile și lista instrumentelor. `state.py` – starea (profit zi/total, poziții) salvată ca artifact GitHub.
- `tests/` – 101 teste (`python -m pytest -q tests`). Rulează-le înainte de orice push.

## Workflow-uri GitHub (`.github/workflows/`)
- `assistant.yml` – botul. Intrări: `hours`, `continued`, `mode` (`real`/`demo`), `aggressive`. Grup de concurență `assistant`. Se re-lansează singur la capătul sesiunii.
- `oil-backtest.yml` („Unelte”) – rulează orice script din `etoro-assistant/` (`script`, `arg`) cu cheile reale. Așa se face cercetare pe date reale.
- `launcher.yml` – pornește botul din Telegram.
- **Repornire bot:** anulezi run-ul curent → aștepți să fie `completed/cancelled` (se salvează starea) → dai dispatch la `assistant.yml` pe `master` cu `{"hours":"12","continued":"1","mode":"real","aggressive":"true"}`. Un run anulat poate dura câteva minute.

## Mediu local (Windows / Mac / alt PC)
1. Instalează Git și Python 3.12 (pe Windows bifează „Add python.exe to PATH”).
2. `git clone https://github.com/eugen-sketch/skinmybird.git`, apoi `git checkout claude/etoro-oil-trading-bot-253uf8`.
3. `pip install requests pandas numpy matplotlib tzdata pytest`.
4. Teste: `cd etoro-assistant` apoi `python -m pytest -q tests` (trebuie să treacă toate).
5. Scripturi de cercetare: `python research_entry_policies.py`, `python replay_eurusd.py` etc. Datele de preț vin de la Yahoo, nu cer chei.
6. Dacă trebuie citit contul: variabile de mediu `ETORO_REAL_API_KEY` și `ETORO_REAL_USER_KEY`, de preferat chei **doar cu permisiune de citire**.
   Windows: `setx NUME valoare` (în PowerShell, apoi terminal nou). Mac: `export NUME=valoare` în `~/.zshrc`. Utilizatorul le setează singur, nu le lipește în chat.
   Pentru Telegram, în scripturile care trimit mesaje: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (la fel, doar local, niciodată în chat).

## Cum e setat acum (agresiv, nu „idiot”)
- Real, `aggressive=true`: RSI 36 pe forex / 30 pe petrol, pullback 50, val ≥1,3 ATR, maxim 3–4 poziții, țintă 1,1 ATR (≤10 $), plasă 3,5 ATR (≤25 $), oprire de pierdere zilnică 22 $.
- Dimensionare progresivă: marjă = sold/număr poziții (minim 50 $ pe poziție, expunere minimă 1000 $). Levier: 30 forex, 20 indici/aur, 10 petrol.
- Plasă de coș: la ≥2 poziții și total ≥ 4,5 $, botul închide tot fără să întrebe (limită cunoscută).
- Raport zilnic înainte de închiderea pieței, cu **PROFIT AZI** și **PROFIT TOTAL** separate (de la 12.10.2026, `since_real`).

## Ce știm din cercetare (date reale, 1 an, 13 instrumente)
- Nu există avantaj dovedit după costuri (~0,17–0,18 ATR dus-întors). Semnalele de val: −0,17 ATR/tranzacție în medie; pullback: −0,26.
- Intrarea mai târziu, pe retragere, pe confirmare sau inversă **nu** îmbunătățește nimic (`research_entry_timing.py`, `research_entry_policies.py`). Filtrele de „întindere”, ultima oră și RSI nu ajută.
- Semnalele contradictorii pe aceeași oră se anulează (side=0), iar un semnal RSI apare doar la prima oră sub prag. Ipoteză în verificare: din cauza asta botul a ratat revenirea EUR/USD după căderea din 14.10 (`replay_eurusd.py` reconstituie votul bară cu bară).

## Ordinea de lucru preferată de utilizator
Pași mici, câte unul; trecem la următorul când scrie „ok”. Mai întâi verifici pe date reale, apoi modifici; raportezi onest ce nu merge, fără înfrumusețări.
