"""
core/hotstrings.py — Expansão de atalhos de texto (estilo AutoHotkey hotstrings).

Usa lib `keyboard` (já presente). Mantém buffer dos últimos N chars digitados;
quando o buffer termina com um trigger registrado, simula Backspace × len(trigger)
e digita o expand via WindowsDriver.

Atomic write em save() — evita corromper o JSON se o app crashar no meio.
"""
from __future__ import annotations
import json
import os
import threading
import time
from typing import Callable

import keyboard


class HotstringManager:
    BUFFER_SIZE = 64

    def __init__(self, driver) -> None:
        self._driver = driver
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        # Serializa expansions concorrentes: se usuário dispara 2 triggers em
        # sequência rapida, o save/restore do clipboard de uma não corrompe a
        # outra. Sem esse lock, OpenClipboard race entre threads.
        self._expand_lock = threading.Lock()
        self._hotstrings: list[dict] = []   # [{"trigger":":em:","expand":"...","enabled":True}]
        self._listening = False
        self._hook = None
        # Callback opcional pra UI saber que disparou (estatística/visual)
        self.on_expand: Callable[[str], None] | None = None

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            self._hotstrings = []
            return
        try:
            with open(path, encoding="utf-8") as f:
                self._hotstrings = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._hotstrings = []

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._hotstrings, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def get_all(self) -> list[dict]:
        with self._lock:
            return list(self._hotstrings)

    def set_all(self, hotstrings: list[dict]) -> None:
        with self._lock:
            self._hotstrings = list(hotstrings)
            self._buffer.clear()

    def start(self) -> None:
        if self._listening:
            return
        self._listening = True
        self._buffer.clear()
        self._hook = keyboard.on_press(self._on_press)

    def stop(self) -> None:
        if not self._listening:
            return
        self._listening = False
        if self._hook is not None:
            try:
                keyboard.unhook(self._hook)
            except Exception:
                pass
            self._hook = None

    @property
    def is_running(self) -> bool:
        return self._listening

    def _on_press(self, event) -> None:
        # Roda na thread do hook do `keyboard` — evitar trabalho pesado
        name = event.name or ""
        with self._lock:
            if name == "backspace":
                if self._buffer:
                    self._buffer.pop()
                return
            if name == "space":
                self._buffer.append(" ")
            elif name == "enter":
                self._buffer.clear()
                return
            elif len(name) == 1:
                self._buffer.append(name)
            else:
                # Tecla especial (shift, ctrl, F1, etc) — limpa buffer
                self._buffer.clear()
                return
            if len(self._buffer) > self.BUFFER_SIZE:
                del self._buffer[: len(self._buffer) - self.BUFFER_SIZE]
            text = "".join(self._buffer)
            for hs in self._hotstrings:
                if not hs.get("enabled", True):
                    continue
                trig = hs.get("trigger", "")
                if trig and text.endswith(trig):
                    expand = hs.get("expand", "")
                    self._buffer.clear()
                    # Schedule fora do hook pra não bloquear o keyboard
                    threading.Thread(
                        target=self._expand, args=(len(trig), expand),
                        daemon=True,
                    ).start()
                    if self.on_expand:
                        try: self.on_expand(trig)
                        except Exception: pass
                    return

    def _expand(self, trigger_len: int, expand_text: str) -> None:
        # Serializa: se duas expansions disparam quase juntas, a segunda espera
        # a primeira terminar de salvar/restaurar o clipboard.
        with self._expand_lock:
            self._do_expand(trigger_len, expand_text)

    def _do_expand(self, trigger_len: int, expand_text: str) -> None:
        # 1. Apaga o trigger (backspaces individuais — rápido o suficiente)
        for _ in range(trigger_len):
            self._driver.perform_type("key", "backspace")
        if not expand_text:
            return
        # 2. Paste mode via driver (save/restore clipboard interno).
        # Fallback char-by-char se clipboard falhar.
        if not self._driver.paste_text(expand_text):
            for ch in expand_text:
                self._driver.perform_type("char", ch)
