"""Calendar economic (flux gratuit ForexFactory): pauza de semnale in jurul evenimentelor importante (inflatie, locuri de munca, banci centrale).

Nu genereaza tranzactii: doar PROTEJEAZA. Cu o ora-doua inainte te anunta, iar pe moneda afectata nu mai propune/deschide nimic in fereastra
[inainte, dupa] eveniment. Daca fluxul nu raspunde, botul merge exact ca inainte (nu blocheaza nimic)."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import requests

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
OTHER = {"OIL": ("USD",), "GOLD": ("USD",), "SPX500": ("USD",), "NSDQ100": ("USD",), "DJ30": ("USD",), "GER40": ("EUR",)}


def currencies_for(name: str) -> tuple[str, ...]:
    """Monedele care misca un instrument: EURUSD -> (EUR, USD); indicii/petrolul/aurul -> USD (GER40 -> EUR)."""
    if name in OTHER:
        return OTHER[name]
    return (name[:3], name[3:6]) if len(name) == 6 and name.isalpha() else ("USD",)


def fetch_calendar() -> list[dict]:
    r = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


class NewsFeed:
    def __init__(self, cfg: dict | None = None, fetch=None):
        c = cfg or {}
        self.enabled = bool(c.get("enabled", False))
        self.impacts = {str(x).lower() for x in c.get("impacts", ["High"])}
        self.before = timedelta(minutes=c.get("before_min", 30))
        self.after = timedelta(minutes=c.get("after_min", 30))
        self.heads_up = timedelta(minutes=c.get("heads_up_min", 60))
        self.cache_s = c.get("cache_min", 60) * 60
        self.fetch = fetch or fetch_calendar
        self._ev: list[dict] = []
        self._at = 0.0
        self.notified: set[str] = set()

    def events(self) -> list[dict]:
        """Evenimentele importante ale saptamanii (cu cache); la eroare pastram ce stiam si nu aruncam exceptia."""
        if not self.enabled:
            return []
        if time.time() - self._at >= self.cache_s:
            self._at = time.time()                         # nu reincercam la fiecare scanare daca fluxul e cazut
            try:
                out = []
                for e in self.fetch():
                    if str(e.get("impact", "")).lower() not in self.impacts or str(e.get("country", "")).upper() in ("", "ALL"):
                        continue
                    t = datetime.fromisoformat(str(e["date"]))
                    if t.tzinfo is None:
                        continue
                    out.append({"id": f"{e['date']}|{e.get('country')}|{e.get('title')}", "time": t.astimezone(timezone.utc),
                                "cur": str(e["country"]).upper(), "title": str(e.get("title", "")), "impact": str(e.get("impact", ""))})
                self._ev = sorted(out, key=lambda x: x["time"])
            except Exception as ex:  # noqa: BLE001
                print(f"[!] Calendar stiri: {type(ex).__name__}")
        return self._ev

    def blocking(self, name: str, now: datetime) -> dict | None:
        """Evenimentul important care blocheaza acum instrumentul (in [inainte, dupa] fata de ora lui), sau None."""
        cur = currencies_for(name)
        for e in self.events():
            if e["cur"] in cur and e["time"] - self.before <= now <= e["time"] + self.after:
                return e
        return None

    def ahead(self, now: datetime) -> list[dict]:
        """Evenimentele importante care incep in urmatoarea ora si nu au fost anuntate inca (le marcheaza ca anuntate)."""
        out = [e for e in self.events() if now <= e["time"] <= now + self.heads_up and e["id"] not in self.notified]
        self.notified.update(e["id"] for e in out)
        return out
