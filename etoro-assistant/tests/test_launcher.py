import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import launcher  # noqa: E402


class R:
    def __init__(self, data=None, status=200):
        self._d, self.status_code, self.ok = data or {}, status, status < 400

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def setup(monkeypatch, running, texts, chat="42", age=60):
    sent, dispatched = [], []
    ups = [{"update_id": i + 1, "message": {"chat": {"id": int(chat)}, "text": t, "date": time.time() - age}} for i, t in enumerate(texts)]

    def get(url, **kw):
        if "actions/workflows" in url:
            return R({"workflow_runs": [{"status": "in_progress" if running else "completed"}]})
        return R({"result": ups})

    def post(url, **kw):
        if "dispatches" in url:
            dispatched.append(kw["json"])
            return R(status=204)
        sent.append(kw["json"]["text"])
        return R()

    monkeypatch.setenv("TELEGRAM_CHAT_ID", chat)
    monkeypatch.setattr(launcher.requests, "get", get)
    monkeypatch.setattr(launcher.requests, "post", post)
    return sent, dispatched


def test_text_helpers():
    assert launcher.wants_start("▶️ Pornește") and launcher.wants_start("porneste 24") and launcher.wants_start("/start")
    assert not launcher.wants_start("status")
    assert launcher.hours_from("pornește 24") == 24 and launcher.hours_from("▶️ Pornește") == 12 and launcher.hours_from("porneste 999") == 72


def test_start_request_dispatches(monkeypatch):
    sent, disp = setup(monkeypatch, running=False, texts=["▶️ Pornește"])
    launcher.main()
    assert disp == [{"ref": "master", "inputs": {"hours": "12", "continued": "0"}}] and "Am primit" in sent[0]


def test_nothing_when_already_running_or_no_message(monkeypatch):
    sent, disp = setup(monkeypatch, running=True, texts=["pornește"])
    launcher.main()
    assert not sent and not disp
    sent, disp = setup(monkeypatch, running=False, texts=[])
    launcher.main()
    assert not sent and not disp


def test_old_message_ignored_and_other_text_gets_hint(monkeypatch):
    sent, disp = setup(monkeypatch, running=False, texts=["pornește"], age=3 * 3600)
    launcher.main()
    assert not sent and not disp
    sent, disp = setup(monkeypatch, running=False, texts=["status"])
    launcher.main()
    assert not disp and "oprit" in sent[0]
