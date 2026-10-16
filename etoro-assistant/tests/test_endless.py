"""«Să se repornească singur»: cu hours=0 sesiunea se relansează la nesfârșit (până apeși «Oprește»), nu se oprește după 12 ore."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import assistant as A  # noqa: E402
import launcher  # noqa: E402
import messages as msg  # noqa: E402


def test_endless_session_always_hands_over():
    this, remaining = A.plan_session(0)
    assert this == A.MAX_RUN_HOURS and remaining > 0.01                      # mereu mai rămâne o sesiune => handover
    assert A.plan_session(12) == (5.5, 6.5) and A.plan_session(3) == (3, 0.0)    # sesiunile cu limită se comportă ca înainte


def test_launcher_button_starts_without_time_limit():
    assert launcher.DEFAULT_HOURS == 0 and launcher.hours_from("▶️ Pornește") == 0
    assert launcher.hours_from("pornește 24") == 24                         # cine scrie ore, primește ore


def test_messages_for_endless_mode_make_sense():
    assert "fără limită de timp" in msg.started(0, 150.0, 15, 4.5, real=True) and "0 ore" not in msg.started(0, 150.0, 15, 4.5, real=True)
    assert "fără limită de timp" in msg.continued(0) and "Mai sunt 0" not in msg.continued(0)
    assert "fără limită de timp" in msg.handover(float("inf"), 1) and "inf" not in msg.handover(float("inf"), 1)
    assert "încă 6.5 ore" in msg.handover(6.5, 1)                            # cu limită: ca înainte
