import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import state  # noqa: E402


import news  # noqa: E402

os.environ["BOT_SIMPLE_OFF"] = "1"
os.environ["BOT_RISK_RULES_OFF"] = "1"    # testele vechi verifica marimea si numarul de pozitii de dinainte; regulile noi au test_risk_rules.py        # testele vechi verifica strategia de dinainte; modul simplu are testele lui (test_simple_mode.py)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "PATH", tmp_path / "state.json")
    monkeypatch.setattr(news, "fetch_calendar", lambda: [])        # testele nu ating internetul
