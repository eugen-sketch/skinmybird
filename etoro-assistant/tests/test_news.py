import sys
from datetime import timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import news  # noqa: E402
from test_aggressive import build  # noqa: E402
from test_spec_audit import T1, wave_df  # noqa: E402

CFG = {"enabled": True, "impacts": ["High"], "before_min": 30, "after_min": 30, "heads_up_min": 60, "cache_min": 60}


def ev(minutes, cur="USD", impact="High", title="US CPI y/y"):
    t = (T1 + timedelta(minutes=minutes)).astimezone(timezone(timedelta(hours=-4)))
    return {"title": title, "country": cur, "impact": impact, "date": t.isoformat()}


def test_currencies_for_instruments():
    assert news.currencies_for("EURUSD") == ("EUR", "USD") and news.currencies_for("USDJPY") == ("USD", "JPY")
    assert news.currencies_for("GOLD") == ("USD",) and news.currencies_for("OIL") == ("USD",) and news.currencies_for("GER40") == ("EUR",)


def test_blocking_window_and_currency_match():
    f = news.NewsFeed(CFG, fetch=lambda: [ev(20)])
    assert f.blocking("GBPUSD", T1) and f.blocking("EURUSD", T1 + timedelta(minutes=45))      # in fereastra [-30, +30]
    assert f.blocking("GBPUSD", T1 - timedelta(minutes=30)) is None and f.blocking("GBPUSD", T1 + timedelta(minutes=51)) is None
    assert f.blocking("GER40", T1) is None                                                      # USD nu atinge indicele german


def test_only_important_events_and_feed_errors_never_block():
    f = news.NewsFeed(CFG, fetch=lambda: [ev(10, impact="Low"), ev(10, impact="Medium"), ev(10, cur="All")])
    assert f.blocking("EURUSD", T1) is None
    def boom():
        raise RuntimeError("fara internet")
    g = news.NewsFeed(CFG, fetch=boom)
    assert g.blocking("EURUSD", T1) is None and g.ahead(T1) == []                               # nicio exceptie, nicio blocare
    assert news.NewsFeed({"enabled": False}, fetch=lambda: [ev(10)]).blocking("EURUSD", T1) is None


def test_ahead_announces_each_event_once():
    f = news.NewsFeed(CFG, fetch=lambda: [ev(40), ev(300)])
    assert len(f.ahead(T1)) == 1 and f.ahead(T1) == []                                          # al doilea e peste o ora


def test_scan_pauses_signal_during_news_and_announces_once(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.news = news.NewsFeed(CFG, fetch=lambda: [ev(20)])
    a.scan()
    a.scan()
    assert not [x for x in tg.texts if "Semnal pe" in x] and not br.pos
    assert len([x for x in tg.texts if "🗓️" in x]) == 1


def test_scan_without_news_still_signals(monkeypatch):
    a, tg, br = build(monkeypatch, wave_df(3.0, 0.00002, T1))
    a.news = news.NewsFeed(CFG, fetch=lambda: [ev(300)])                                        # stire peste 5 ore: nu blocheaza
    a.scan()
    assert [x for x in tg.texts if "Semnal pe" in x]
