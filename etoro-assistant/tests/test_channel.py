"""Securitate: starea botului si jurnalul mesajelor sunt criptate (repo-ul e public); fara cheie nu se poate citi nimic."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import channel  # noqa: E402
import state  # noqa: E402
import telegram_bot  # noqa: E402

pytest.importorskip("cryptography")
from cryptography.fernet import Fernet  # noqa: E402

KEY = Fernet.generate_key().decode()
OTHER = Fernet.generate_key().decode()


def test_encrypt_round_trip_and_wrong_key_or_tampering_fails(monkeypatch):
    monkeypatch.delenv("HELGA_KEY", raising=False)                          # testul nu depinde de cheia reala din mediul PC-ului
    tok = channel.encrypt({"a": "Poziție EUR/USD +$2.50"}, KEY)
    assert "EUR/USD" not in tok and "2.50" not in tok                       # nimic citibil în text criptat
    assert channel.decrypt(tok, KEY) == {"a": "Poziție EUR/USD +$2.50"}
    assert channel.decrypt(tok, OTHER) is None                              # altă cheie: nu se poate citi
    assert channel.decrypt(tok[:-4] + "AAAA", KEY) is None                  # token modificat: respins
    assert channel.encrypt({"a": 1}, "") is None and channel.decrypt(tok, "") is None     # fără cheie: nimic


def test_journal_stores_messages_encrypted_and_helga_can_read_them(tmp_path):
    p = tmp_path / "journal.enc"
    j = channel.Journal(p, KEY)
    j.on_telegram("out", "🟢 Semnal pe EUR/USD: aș putea să CUMPĂR", [[("✅ OK, deschide", "open:1"), ("❌ NU", "skip:1")]])
    j.on_telegram("in", "buton: open:1")
    raw = p.read_text(encoding="utf-8")
    assert "EUR/USD" not in raw and "CUMPĂR" not in raw and KEY not in raw                    # pe disc/artefact: doar text criptat
    rows = channel.read(p, KEY)
    assert [r["k"] for r in rows] == ["out", "in"] and "CUMPĂR" in rows[0]["x"] and rows[0]["buttons"] == [["✅ OK, deschide", "❌ NU"]]
    assert channel.read(p, OTHER) == []                                                       # cine nu are cheia nu vede nimic


def test_journal_is_off_without_key_and_never_breaks_the_bot(tmp_path, monkeypatch):
    monkeypatch.delenv("HELGA_KEY", raising=False)
    assert channel.from_env(tmp_path / "j.enc") is None
    j = channel.Journal(tmp_path / "j.enc", None)
    j.add("out", "ceva")                                                                       # oprit: nu scrie, nu aruncă
    assert not (tmp_path / "j.enc").exists()
    bad = channel.Journal(tmp_path / "nu-exista" / "j.enc", KEY)
    bad.add("out", "ceva")                                                                     # cale invalidă: erorile sunt înghițite


def test_journal_does_not_grow_forever(tmp_path, monkeypatch):
    monkeypatch.setattr(channel, "MAX_BYTES", 3000)
    j = channel.Journal(tmp_path / "j.enc", KEY)
    for i in range(60):
        j.add("out", f"mesaj {i} " + "x" * 50)
    assert (tmp_path / "j.enc").stat().st_size < 6000
    assert channel.read(tmp_path / "j.enc", KEY)[-1]["x"].startswith("mesaj 59")               # păstrează cele mai noi


def test_state_is_encrypted_with_key_and_old_format_still_loads(tmp_path, monkeypatch):
    p = tmp_path / "state-real.json"
    monkeypatch.setenv("HELGA_KEY", KEY)
    state.save({"realized": 12.5, "history": {"2026-10-16": {"pnl": 1.42}}}, p)
    txt = p.read_text(encoding="utf-8")
    assert txt.startswith("f1:") and "1.42" not in txt and "realized" not in txt              # artefactul public nu arată nimic
    assert state.load(p)["realized"] == 12.5
    monkeypatch.delenv("HELGA_KEY")
    old = state.dumps({"realized": 3.0})                                                       # formatul vechi (fără cheie)
    assert not old.startswith("f1:")
    monkeypatch.setenv("HELGA_KEY", KEY)
    assert state.loads(old) == {"realized": 3.0}                                               # starea veche din artefact se încarcă fără pierderi
    monkeypatch.setenv("HELGA_KEY", OTHER)
    assert state.load(p) == {}                                                                 # cheie greșită: pornește curat, fără eroare


def test_telegram_messages_reach_the_journal_hook(tmp_path, monkeypatch):
    j = channel.Journal(tmp_path / "j.enc", KEY)
    monkeypatch.setattr(telegram_bot, "HOOKS", [j.on_telegram])
    tg = telegram_bot.Telegram("token-de-test", "123")
    monkeypatch.setattr(tg, "_call", lambda method, timeout=0, **p: {"message_id": 7} if method == "sendMessage" else
                        [{"update_id": 1, "message": {"chat": {"id": 123}, "text": "Status"}}])
    assert tg.send("Salut", [[("OK", "x:1")]]) == 7
    assert tg.poll() == [{"kind": "text", "text": "Status"}]
    rows = channel.read(tmp_path / "j.enc", KEY)
    assert [(r["k"], r["x"]) for r in rows] == [("out", "Salut"), ("in", "Status")]
    assert "token-de-test" not in (tmp_path / "j.enc").read_text(encoding="utf-8")            # tokenul botului nu ajunge în jurnal


def test_a_broken_hook_never_stops_telegram(monkeypatch):
    def boom(kind, text, buttons=None):
        raise RuntimeError("jurnal stricat")
    monkeypatch.setattr(telegram_bot, "HOOKS", [boom])
    tg = telegram_bot.Telegram("t", "1")
    monkeypatch.setattr(tg, "_call", lambda method, timeout=0, **p: {"message_id": 9})
    assert tg.send("Salut") == 9
