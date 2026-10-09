"""Telegram: trimite mesaje cu butoane si citeste raspunsurile (doar de la chat-ul tau)."""
from __future__ import annotations

import os

import requests


class Telegram:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat = str(chat_id or os.getenv("TELEGRAM_CHAT_ID", ""))
        if not (self.token and self.chat):
            raise RuntimeError("Lipsesc TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        self.base = f"https://api.telegram.org/bot{self.token}"
        self.offset: int | None = None

    def _call(self, method: str, timeout: int = 0, **payload):
        r = requests.post(f"{self.base}/{method}", json=payload, timeout=timeout + 20)
        r.raise_for_status()
        return r.json().get("result")

    def send(self, text: str, buttons: list[list[tuple[str, str]]] | None = None, menu: list[list[str]] | None = None) -> int | None:
        """buttons = butoane sub mesaj (inline); menu = meniul permanent de sub casuta de scris."""
        payload = {"chat_id": self.chat, "text": text[:4000]}
        if menu:
            payload["reply_markup"] = {"keyboard": [[{"text": t} for t in row] for row in menu], "resize_keyboard": True,
                                       "is_persistent": True, "input_field_placeholder": "Alege un buton sau scrie /ajutor"}
        elif buttons:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
        try:
            res = self._call("sendMessage", **payload)
            return res.get("message_id") if res else None
        except requests.RequestException as e:
            print(f"[!] Telegram: {type(e).__name__}")
            return None

    def clear_buttons(self, message_id: int | None) -> None:
        if not message_id:
            return
        try:
            self._call("editMessageReplyMarkup", chat_id=self.chat, message_id=message_id, reply_markup={"inline_keyboard": []})
        except requests.RequestException:
            pass

    def answer(self, callback_id: str, text: str = "") -> None:
        try:
            self._call("answerCallbackQuery", callback_query_id=callback_id, text=text[:150])
        except requests.RequestException:
            pass

    def drain(self) -> None:
        """Ignora tot ce s-a apasat/scris inainte de pornirea sesiunii (ca sa nu executam comenzi vechi)."""
        try:
            ups = self._call("getUpdates", offset=-1, timeout=0) or []
            if ups:
                self.offset = ups[-1]["update_id"] + 1
        except requests.RequestException:
            pass

    def poll(self, timeout: int = 15) -> list[dict]:
        """Mesaje noi: {'kind': 'text', 'text'} sau {'kind': 'button', 'id', 'data', 'msg_id'}. Doar din chat-ul tau."""
        try:
            ups = self._call("getUpdates", timeout=timeout, offset=self.offset, allowed_updates=["message", "callback_query"]) or []
        except requests.RequestException as e:
            print(f"[!] Telegram poll: {type(e).__name__}")
            return []
        out = []
        for u in ups:
            self.offset = u["update_id"] + 1
            cb, m = u.get("callback_query"), u.get("message")
            if cb and str(cb.get("message", {}).get("chat", {}).get("id")) == self.chat:
                out.append({"kind": "button", "id": cb["id"], "data": cb.get("data", ""), "msg_id": cb["message"]["message_id"]})
            elif m and str(m.get("chat", {}).get("id")) == self.chat and m.get("text"):
                out.append({"kind": "text", "text": m["text"].strip()})
        return out
