import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import state  # noqa: E402


import news  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "PATH", tmp_path / "state.json")
    monkeypatch.setattr(news, "fetch_calendar", lambda: [])        # testele nu ating internetul
