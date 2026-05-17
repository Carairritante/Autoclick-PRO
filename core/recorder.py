"""
core/recorder.py — Gravador de macro via pynput.

Captura eventos de mouse e teclado em tempo real, convertendo-os em
lista de MacroStep com timing automático (delay_ms = tempo entre ações).
"""
from __future__ import annotations

import time
import threading
from typing import Callable

from core.macro_schema import MacroStep

try:
    from pynput import mouse as _mouse, keyboard as _keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# Mapa pynput Key → nome do pyautogui/keyboard. Cobre TODAS as teclas
# que o pynput emite como Key.* — para nomes de chars normais, ver fallback abaixo.
_PYNPUT_KEY_MAP: dict[str, str] = {
    # Navegação / edição
    "Key.enter":        "enter",
    "Key.tab":          "tab",
    "Key.space":        "space",
    "Key.backspace":    "backspace",
    "Key.delete":       "delete",
    "Key.escape":       "escape",
    "Key.up":           "up",
    "Key.down":         "down",
    "Key.left":         "left",
    "Key.right":        "right",
    "Key.home":         "home",
    "Key.end":          "end",
    "Key.page_up":      "pageup",
    "Key.page_down":    "pagedown",
    "Key.insert":       "insert",
    # Função F1-F24
    "Key.f1":  "f1",  "Key.f2":  "f2",  "Key.f3":  "f3",  "Key.f4":  "f4",
    "Key.f5":  "f5",  "Key.f6":  "f6",  "Key.f7":  "f7",  "Key.f8":  "f8",
    "Key.f9":  "f9",  "Key.f10": "f10", "Key.f11": "f11", "Key.f12": "f12",
    "Key.f13": "f13", "Key.f14": "f14", "Key.f15": "f15", "Key.f16": "f16",
    "Key.f17": "f17", "Key.f18": "f18", "Key.f19": "f19", "Key.f20": "f20",
    # Modificadores (genérico + L/R explícito)
    "Key.shift":    "shift",
    "Key.shift_l":  "shiftleft",
    "Key.shift_r":  "shiftright",
    "Key.ctrl":     "ctrl",
    "Key.ctrl_l":   "ctrlleft",
    "Key.ctrl_r":   "ctrlright",
    "Key.alt":      "alt",
    "Key.alt_l":    "altleft",
    "Key.alt_r":    "altright",
    "Key.alt_gr":   "altright",   # AltGr em ABNT2 = alt direito
    "Key.cmd":      "win",
    "Key.cmd_l":    "winleft",
    "Key.cmd_r":    "winright",
    # Locks
    "Key.caps_lock":    "capslock",
    "Key.num_lock":     "numlock",
    "Key.scroll_lock":  "scrolllock",
    # Mídia / utilidades
    "Key.print_screen": "printscreen",
    "Key.pause":        "pause",
    "Key.menu":         "apps",        # tecla "context menu"
    "Key.media_play_pause":  "playpause",
    "Key.media_volume_mute": "volumemute",
    "Key.media_volume_down": "volumedown",
    "Key.media_volume_up":   "volumeup",
    "Key.media_previous":    "prevtrack",
    "Key.media_next":        "nexttrack",
}

# Botões do mouse pynput → string interna
_BTN_MAP: dict[str, str] = {
    "Button.left":   "left",
    "Button.right":  "right",
    "Button.middle": "middle",
}


class MacroRecorder:
    """Grava eventos de mouse e teclado e converte para lista de MacroStep.

    Uso:
        rec = MacroRecorder()
        rec.start(capture_keyboard=True)
        # ... usuário age ...
        steps = rec.stop()   # retorna list[MacroStep] com timings reais
    """

    def __init__(self) -> None:
        self._steps: list[MacroStep] = []
        self._last_t: float = 0.0
        self._running = False
        self._mouse_listener = None
        self._key_listener = None
        self._lock = threading.Lock()

    # ─────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────
    def start(self, capture_keyboard: bool = True, stop_key: str | None = None) -> bool:
        """Inicia gravação. Retorna False se pynput não está instalado."""
        if not HAS_PYNPUT:
            return False
        self._steps = []
        self._last_t = time.monotonic()
        self._running = True
        self._stop_key = stop_key  # tecla que dispara o stop — não é gravada

        self._mouse_listener = _mouse.Listener(
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._mouse_listener.start()

        if capture_keyboard:
            self._key_listener = _keyboard.Listener(
                on_press=self._on_key_press,
            )
            self._key_listener.start()

        return True

    def stop(self) -> list[MacroStep]:
        """Para a gravação e retorna os steps coletados."""
        self._running = False
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None
        if self._key_listener:
            try:
                self._key_listener.stop()
            except Exception:
                pass
            self._key_listener = None
        with self._lock:
            return list(self._steps)

    # ─────────────────────────────────────────────────────────────
    # INTERNAL LISTENERS
    # ─────────────────────────────────────────────────────────────
    def _elapsed(self) -> int:
        """Retorna ms desde o último evento e atualiza o timer."""
        now = time.monotonic()
        ms = int((now - self._last_t) * 1000)
        self._last_t = now
        return ms

    def _on_mouse_click(self, x, y, button, pressed) -> None:
        if not self._running or not pressed:
            return
        btn_str = _BTN_MAP.get(str(button), "left")
        ms = self._elapsed()
        with self._lock:
            self._steps.append(MacroStep(
                action="click",
                x=x, y=y,
                delay_ms=ms,
                button=btn_str,
            ))

    def _on_mouse_scroll(self, x, y, dx, dy) -> None:
        if not self._running:
            return
        ms = self._elapsed()
        with self._lock:
            self._steps.append(MacroStep(
                action="scroll",
                x=x, y=y,
                delay_ms=ms,
                scroll_dy=dy if dy != 0 else (1 if dy >= 0 else -1),
            ))

    def _on_key_press(self, key) -> None:
        if not self._running:
            return
        key_str = str(key)

        # Ignora a tecla de stop para não poluir o macro
        if self._stop_key and key_str in (self._stop_key, f"Key.{self._stop_key}"):
            return

        ms = self._elapsed()

        # Tecla especial (Key.enter, Key.f5, modificadores, locks, etc.)
        mapped = _PYNPUT_KEY_MAP.get(key_str)
        if mapped:
            with self._lock:
                self._steps.append(MacroStep(
                    action="key_press",
                    key=mapped,
                    delay_ms=ms,
                ))
            return

        # Caractere produzido pela tecla
        try:
            char = key.char
            if not char:
                return
            # Caracteres de controle (Ctrl+A=\x01, Ctrl+C=\x03, etc.) viram
            # key_press "ctrl+letra" — Ctrl é detectado pelo control char.
            if len(char) == 1 and ord(char) < 0x20 and char not in ("\t", "\n", "\r"):
                letter = chr(ord(char) + ord('a') - 1)
                if letter.isalpha():
                    with self._lock:
                        self._steps.append(MacroStep(
                            action="key_press",
                            key=f"ctrl+{letter}",
                            delay_ms=ms,
                        ))
                return
            # ASCII imprimível (letras, dígitos, símbolos básicos) → key_press
            # com VK code real — funciona em jogos (Roblox/DirectInput) E em editores.
            # pyautogui.press('A') já lida com shift internamente.
            if len(char) == 1 and 0x20 < ord(char) < 0x7f:
                with self._lock:
                    self._steps.append(MacroStep(
                        action="key_press",
                        key=char,
                        delay_ms=ms,
                    ))
                return
            # Non-ASCII (ç, ã, é, €, …) → precisa de KEYEVENTF_UNICODE via type.
            with self._lock:
                self._steps.append(MacroStep(
                    action="type",
                    text=char,
                    delay_ms=ms,
                ))
        except AttributeError:
            # Tecla sem .char e sem mapping conhecido — última tentativa via vk
            vk = getattr(key, "vk", None)
            if vk is None:
                return
            # Numpad com NumLock OFF (vk 96-105 = num0-num9, mas só viram char com NumLock)
            if 0x60 <= vk <= 0x69:
                with self._lock:
                    self._steps.append(MacroStep(
                        action="key_press",
                        key=f"num{vk - 0x60}",
                        delay_ms=ms,
                    ))
