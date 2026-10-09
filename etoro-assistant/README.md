# Asistent de trading eToro (DEMO)

Un **asistent**, nu un robot autonom: **pornește doar când îl pornești tu**, te anunță pe Telegram când vede un semnal de intrare
și **nu deschide nimic fără „OK” de la tine**. Funcționează doar pe contul **demo** (codul refuză orice cale fără `/demo/`).

## Cum îl pornești
GitHub → Actions → **Asistent trading (îl pornești tu)** → *Run workflow* (alegi câte ore). Se oprește cu `/stop` pe Telegram,
cu *Cancel* în GitHub sau singur la sfârșitul sesiunii. Nu rulează niciodată singur.

## Ce face
- La **15 minute** scanează forex (7 majore) și petrol (WTI): spargerea intervalului asiatic la Londra, sau RSI(14) extrem.
- La semnal îți scrie: motivul, prețul, cât bagă, **țintă ≈ 2,75 $**, plasă de siguranță ≈ 6 $, cu butoane **✅ OK / ❌ NU**
  (iar dacă sunt mai multe: **OK la toate**). Maxim 3 în așteptare.
- La OK deschide pe demo, cu Take Profit și Stop Loss puse la eToro (rămân active și dacă asistentul se oprește).
- Singurul lucru automat: dacă ai **2 sau mai multe poziții** deschise și împreună ating **≈ 4,5 $**, le închide.
- Poți închide oricând, din eToro sau cu `/inchide`. Îți spune când s-a închis ceva și cu ce rezultat.
- Comenzi: `/status`, `/inchide tot`, `/inchide EURUSD`, `/scan`, `/stop`, `/ajutor`.

## Buget
140 $. eToro cere expunere minimă de 1.000 $ pe poziție: la forex (levier 30) ≈ 46,66 $ marjă (3 poziții încap),
la petrol (levier 10) ≈ 101 $ marjă (o singură poziție). Setările sunt în `config.json`.

## Rezultatele testelor de strategie (date reale)
Nu am găsit o strategie cu avantaj dovedit pe forex sau petrol; asistentul te ajută să decizi tu, nu promite profit.
Vezi `research_*.py`. Indicii, aurul și materiile prime cer sume mai mari și nu sunt incluse acum.
