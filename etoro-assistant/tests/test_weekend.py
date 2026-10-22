"""Weekend (decizia lui Eugen, 18 oct): botul se opreste singur vineri seara si porneste singur duminica seara, PE MANUAL."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import assistant as A  # noqa: E402
import launcher  # noqa: E402
from test_assistant import CFG, FakeBroker, FakeTG  # noqa: E402
from test_launcher import R  # noqa: E402

SUN = datetime(2026, 10, 25, 20, 10, tzinfo=timezone.utc)


def setup(monkeypatch, now, runs):
    sent, disp = [], []
    monkeypatch.setattr(launcher, "NOW", lambda: now)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(launcher.requests, "get", lambda url, **kw: R({"workflow_runs": runs}) if "actions/workflows" in url else R({"result": []}))

    def post(url, **kw):
        if "dispatches" in url:
            disp.append(kw["json"])
            return R(status=204)
        sent.append(kw["json"]["text"])
        return R()
    monkeypatch.setattr(launcher.requests, "post", post)
    return sent, disp


def test_sunday_evening_starts_once_on_manual(monkeypatch):
    sent, disp = setup(monkeypatch, SUN, [{"status": "completed", "created_at": "2026-10-23T10:00:00Z"}])
    monkeypatch.setattr(launcher, "weekend_cfg", lambda: {"enabled": True, "start_utc": "20:00", "window_min": 90})   # fara proba pe demo
    launcher.main()
    assert disp == [{"ref": "master", "inputs": {"hours": "0", "continued": "0", "mode": "real", "aggressive": "true", "scheduled": "1"}}]
    assert "PE MANUAL" in sent[0]


def test_no_scheduled_start_if_running_started_since_or_outside_window(monkeypatch):
    for now, runs in ((SUN, [{"status": "in_progress", "created_at": "2026-10-25T19:00:00Z"}]),          # ruleaza deja
                      (SUN, [{"status": "completed", "created_at": "2026-10-25T20:05:00Z"}]),            # pornit/oprit de tine dupa 20:00
                      (SUN.replace(hour=19), [{"status": "completed", "created_at": "2026-10-23T10:00:00Z"}]),   # prea devreme
                      (SUN.replace(hour=22), [{"status": "completed", "created_at": "2026-10-23T10:00:00Z"}]),   # dupa fereastra
                      (SUN.replace(day=26), [{"status": "completed", "created_at": "2026-10-23T10:00:00Z"}])):   # luni
        sent, disp = setup(monkeypatch, now, runs)
        launcher.main()
        assert not disp


def bot(now):
    a = A.Assistant(CFG, FakeTG(), FakeBroker(), fetch=lambda *x, **k: None, now_fn=lambda: now, sleep=lambda s: None)
    return a


def test_friday_evening_stop_only_for_sessions_started_before():
    fri = datetime(2026, 10, 23, 20, 15, tzinfo=timezone.utc)
    a = bot(fri)
    a.session_start = fri.replace(hour=9)
    assert a.weekend_due(fri) and not a.weekend_due(fri.replace(hour=20, minute=5))
    a.session_start = fri.replace(hour=21)                                # pornit de tine vineri noaptea: ramane pornit
    assert not a.weekend_due(fri.replace(hour=21, minute=30))
    a.session_start = fri.replace(day=22)
    assert not a.weekend_due(fri.replace(day=22))                         # joi: nimic


def test_sunday_start_goes_to_demo_during_the_demo_trial(monkeypatch):
    sent, disp = setup(monkeypatch, SUN, [{"status": "completed", "created_at": "2026-10-23T10:00:00Z"}])
    monkeypatch.setattr(launcher, "weekend_cfg", lambda: {"enabled": True, "start_utc": "20:00", "window_min": 90, "demo_until": "2026-11-05"})
    launcher.main()
    assert disp and disp[0]["inputs"]["mode"] == "demo" and "DEMO" in sent[0]


def test_sunday_start_back_to_real_after_the_trial(monkeypatch):
    late = SUN.replace(month=11, day=8)
    sent, disp = setup(monkeypatch, late, [{"status": "completed", "created_at": "2026-11-06T10:00:00Z"}])
    monkeypatch.setattr(launcher, "weekend_cfg", lambda: {"enabled": True, "start_utc": "20:00", "window_min": 90, "demo_until": "2026-11-05"})
    launcher.main()
    assert disp and disp[0]["inputs"]["mode"] == "real" and "PE MANUAL" in sent[0]
