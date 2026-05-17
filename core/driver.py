"""
core/driver.py — Camada de acesso ao Windows.

TODOS os usos de ctypes.windll estão isolados neste arquivo.
Para portar para outro OS, substitua apenas as implementações desta classe.
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from typing import Tuple

import pyautogui


def _autodetect_tesseract() -> None:
    """Procura tesseract.exe em locais comuns e configura pytesseract.

    Útil se Tesseract foi instalado mas o PATH ainda não foi refrescado
    (shell aberto antes da instalação), ou se está num local custom.
    """
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.append(os.path.join(local_app, "AutoClickPro", "tesseract", "tesseract.exe"))

    for path in candidates:
        if os.path.exists(path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = path
            except ImportError:
                pass
            return


_autodetect_tesseract()

# ── Flags de mouse para user32.SendInput (INPUT_MOUSE) ────────────────────────
_INPUT_MOUSE           = 0        # windll: tipo de input mouse
_MOUSEEVENTF_MOVE      = 0x0001   # windll: mover cursor
_MOUSEEVENTF_LEFTDOWN  = 0x0002   # windll: botão esquerdo press
_MOUSEEVENTF_LEFTUP    = 0x0004   # windll: botão esquerdo release
_MOUSEEVENTF_RIGHTDOWN = 0x0008   # windll: botão direito press
_MOUSEEVENTF_RIGHTUP   = 0x0010   # windll: botão direito release
_MOUSEEVENTF_MIDDLEDOWN= 0x0020   # windll: botão do meio press
_MOUSEEVENTF_MIDDLEUP  = 0x0040   # windll: botão do meio release
_MOUSEEVENTF_WHEEL     = 0x0800   # windll: scroll vertical
_MOUSEEVENTF_ABSOLUTE  = 0x8000   # windll: coords em espaço 0-65535
_WHEEL_DELTA           = 120      # unidade padrão de scroll do Windows

# Mapeia botão → (flag_down, flag_up) para SendInput
_BTN_SINPUT: dict[str, tuple[int, int]] = {
    "left":   (_MOUSEEVENTF_LEFTDOWN,   _MOUSEEVENTF_LEFTUP),
    "right":  (_MOUSEEVENTF_RIGHTDOWN,  _MOUSEEVENTF_RIGHTUP),
    "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
}

# ── Estruturas ctypes para user32.SendInput ────────────────────────────────────

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   wintypes.DWORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         wintypes.WORD),
        ("wScan",       wintypes.WORD),
        ("dwFlags",     wintypes.DWORD),
        ("time",        wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi",      _MOUSEINPUT),
        ("ki",      _KEYBDINPUT),
        ("padding", ctypes.c_byte * 28),
    ]

class _INPUT(ctypes.Structure):
    _anonymous_ = ("_u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_u",   _INPUT_UNION),
    ]

_INPUT_KEYBOARD       = 1       # windll: tipo de input (teclado)
_KEYEVENTF_UNICODE    = 0x0004  # windll: flag — enviar caractere pelo valor Unicode
_KEYEVENTF_KEYUP      = 0x0002  # windll: flag — evento de soltura de tecla
_KEYEVENTF_SCANCODE   = 0x0008  # windll: flag — enviar scan code de hardware
_KEYEVENTF_EXTENDEDKEY= 0x0001  # windll: flag — tecla estendida (setas, ins, del…)

# VKs que precisam de KEYEVENTF_EXTENDEDKEY para gerar o scan code correto
_EXTENDED_VKS = {
    0x21, 0x22, 0x23, 0x24,        # PgUp, PgDn, End, Home
    0x25, 0x26, 0x27, 0x28,        # Left, Up, Right, Down
    0x2D, 0x2E,                    # Insert, Delete
    0x5B, 0x5C,                    # Win esq/dir
    0x6F,                          # Numpad /
}

# Mapa de nome de tecla → Virtual Key code (usado para gerar scan code via MapVirtualKeyW)
_VK_MAP: dict[str, int] = {
    'enter': 0x0D, 'return': 0x0D,
    'tab': 0x09,
    'space': 0x20,
    'backspace': 0x08,
    'delete': 0x2E, 'del': 0x2E,
    'escape': 0x1B, 'esc': 0x1B,
    'shift': 0x10,
    'ctrl': 0x11, 'control': 0x11,
    'alt': 0x12,
    'win': 0x5B,
    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
    'home': 0x24, 'end': 0x23,
    'pageup': 0x21, 'pgup': 0x21,
    'pagedown': 0x22, 'pgdn': 0x22,
    'insert': 0x2D,
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72,  'f4': 0x73,
    'f5': 0x74, 'f6': 0x75, 'f7': 0x76,  'f8': 0x77,
    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    'capslock': 0x14, 'numlock': 0x90, 'scrolllock': 0x91,
    'printscreen': 0x2C, 'pause': 0x13,
}
for _c in 'abcdefghijklmnopqrstuvwxyz':
    _VK_MAP[_c] = ord(_c.upper())
for _d in '0123456789':
    _VK_MAP[_d] = ord(_d)

# ⚠ CRÍTICO em x64: sem argtypes, ctypes trunca o ponteiro LPINPUT a 32 bits
# causando falha silenciosa intermitente do SendInput (cliques que não disparam).
_user32 = ctypes.windll.user32
_user32.SendInput.argtypes  = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
_user32.SendInput.restype   = wintypes.UINT
_user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_user32.SetCursorPos.restype  = ctypes.c_int
_user32.mouse_event.argtypes  = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.DWORD, ctypes.c_void_p]
_user32.mouse_event.restype   = None

# Clipboard: argtypes definidos uma vez aqui em vez de a cada chamada de
# set_clipboard_text (evita race condition e overhead repetido).
_kernel32 = ctypes.windll.kernel32
_kernel32.GlobalAlloc.argtypes  = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype   = ctypes.c_void_p
_kernel32.GlobalLock.argtypes   = [ctypes.c_void_p]
_kernel32.GlobalLock.restype    = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype  = ctypes.c_int
_kernel32.GlobalFree.argtypes   = [ctypes.c_void_p]
_kernel32.GlobalFree.restype    = ctypes.c_void_p
_user32.OpenClipboard.argtypes  = [ctypes.c_void_p]
_user32.OpenClipboard.restype   = ctypes.c_int
_user32.EmptyClipboard.restype  = ctypes.c_int
_user32.CloseClipboard.restype  = ctypes.c_int
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_user32.SetClipboardData.restype  = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_user32.GetClipboardData.restype  = ctypes.c_void_p

# ── Estrutura de ponto (usada por WindowFromPoint / ScreenToClient) ────────────
class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# ── Constantes de mensagens de janela e modificadores de botão ────────────────
_WM_LBUTTONDOWN, _WM_LBUTTONUP = 0x0201, 0x0202
_WM_RBUTTONDOWN, _WM_RBUTTONUP = 0x0204, 0x0205
_MK_LBUTTON, _MK_RBUTTON       = 0x0001, 0x0002


class WindowsDriver:
    """Encapsula todas as interações com o WinAPI (windll) e pyautogui.

    Concentra windll.user32, windll.dwmapi — facilita portabilidade futura.
    """

    def _send_mouse(self, flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
        """Envia um único evento de mouse via user32.SendInput (INPUT_MOUSE).

        windll: user32.SendInput — API unificada de input, substitui mouse_event
        """
        inp = (_INPUT * 1)()
        inp[0].type          = _INPUT_MOUSE
        inp[0].mi.dx         = dx
        inp[0].mi.dy         = dy
        inp[0].mi.mouseData  = data
        inp[0].mi.dwFlags    = flags
        ctypes.windll.user32.SendInput(1, inp, ctypes.sizeof(_INPUT))

    def _normalize_coords(self, x: int, y: int) -> tuple[int, int]:
        """Converte coordenadas de tela para espaço normalizado 0-65535.

        windll: user32.GetSystemMetrics — dimensões da tela primária
        Necessário para MOUSEEVENTF_ABSOLUTE via SendInput.
        """
        user32 = ctypes.windll.user32
        sm_cx = max(1, user32.GetSystemMetrics(0))
        sm_cy = max(1, user32.GetSystemMetrics(1))
        return (int(x) * 65535 // sm_cx, int(y) * 65535 // sm_cy)

    def perform_click(
        self,
        x: int | None = None,
        y: int | None = None,
        button: str = "left",
        double: bool = False,
        burst: int = 1,
    ) -> None:
        """Move o cursor (se x/y fornecidos) e dispara clique via SendInput.

        windll: user32.SendInput com INPUT_MOUSE — substitui mouse_event legado.
        Usa MOUSEEVENTF_ABSOLUTE para posicionamento exato independente de DPI.
        """
        if x is not None and y is not None:
            nx, ny = self._normalize_coords(x, y)
            self._send_mouse(_MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_MOVE, dx=nx, dy=ny)
        down, up = _BTN_SINPUT.get(button, _BTN_SINPUT["left"])
        n = burst * (2 if double else 1)
        for _ in range(n):
            self._send_mouse(down)
            self._send_mouse(up)

    def perform_scroll(
        self,
        x: int | None = None,
        y: int | None = None,
        dy: int = 3,
    ) -> None:
        """Rola o scroll vertical na posição dada via SendInput.

        windll: user32.SendInput com MOUSEEVENTF_WHEEL — substitui mouse_event legado.
        dy positivo = scroll para cima, negativo = scroll para baixo.
        """
        if x is not None and y is not None:
            nx, ny = self._normalize_coords(x, y)
            self._send_mouse(_MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_MOVE, dx=nx, dy=ny)
        self._send_mouse(_MOUSEEVENTF_WHEEL, data=int(dy * _WHEEL_DELTA))

    def perform_drag(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        duration_ms: int = 300,
        button: str = "left",
    ) -> None:
        """Click-hold-drag de (x1,y1) até (x2,y2). Usa SendInput — funciona no Roblox.

        Interpola movimento em N passos durante duration_ms para parecer movimento real.
        Sem PostMessage — Raw Input aceita SendInput nativamente.
        """
        # 1. Move até origem
        nx, ny = self._normalize_coords(x1, y1)
        self._send_mouse(_MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_MOVE, dx=nx, dy=ny)
        # 2. Pressiona botão
        down, up = _BTN_SINPUT.get(button, _BTN_SINPUT["left"])
        self._send_mouse(down)
        # 3. Interpola moves até destino — try/finally garante que o botão SEMPRE
        # solta mesmo se for interrompido por exceção; senão o mouse fica "preso"
        try:
            steps = max(10, duration_ms // 10)
            step_ms = duration_ms / steps / 1000
            for i in range(1, steps + 1):
                t = i / steps
                cx = int(x1 + (x2 - x1) * t)
                cy = int(y1 + (y2 - y1) * t)
                nx, ny = self._normalize_coords(cx, cy)
                self._send_mouse(_MOUSEEVENTF_ABSOLUTE | _MOUSEEVENTF_MOVE, dx=nx, dy=ny)
                time.sleep(step_ms)
        finally:
            # 4. Solta botão (sempre — mesmo em interrupção)
            self._send_mouse(up)

    def perform_type(self, kind: str, value: str) -> None:
        """Digita um caractere ou pressiona uma tecla especial.

        Para chars: usa SendInput com KEYEVENTF_UNICODE — funciona com qualquer
        layout de teclado (ABNT2, QWERTY, AZERTY) e qualquer caractere Unicode
        (ã, ç, à, ê, €, etc).
        Para teclas especiais (enter, tab, f1…): usa SendInput com scan code de
        hardware — aceito pelo Roblox e outros jogos que usam Raw Input.
        Para combos (ctrl+c, alt+f4, shift+tab): idem, via _send_combo_scancode.
        """
        if kind == "char":
            self._send_unicode(value)
            return
        # Combo (ex: "ctrl+c") → SendInput scan codes
        if "+" in value:
            parts = [p.strip().lower() for p in value.split("+") if p.strip()]
            if len(parts) >= 2:
                self._send_combo_scancode(parts)
                return
        vk = _VK_MAP.get(value.lower())
        if vk and not self._send_scancode(vk):
            pyautogui.press(value)  # fallback se scan code = 0 (tecla não mapeada no layout)
        elif not vk:
            pyautogui.press(value)  # fallback para teclas fora do _VK_MAP

    def _send_scancode(self, vk: int) -> bool:
        """Envia key press/release via SendInput com KEYEVENTF_SCANCODE.

        Simula hardware real — aceito por jogos com Raw Input (Roblox, etc).
        MapVirtualKeyW converte o VK para o scan code correto do layout atual.
        Retorna False se a tecla não tem scan code no layout (chamador faz fallback).
        """
        scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
        if scan == 0:
            return False  # tecla não mapeada — chamador usa pyautogui como fallback
        ext  = _KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_VKS else 0
        inputs = (_INPUT * 2)()
        inputs[0].type       = _INPUT_KEYBOARD
        inputs[0].ki.wVk     = 0
        inputs[0].ki.wScan   = scan
        inputs[0].ki.dwFlags = _KEYEVENTF_SCANCODE | ext
        inputs[1].type       = _INPUT_KEYBOARD
        inputs[1].ki.wVk     = 0
        inputs[1].ki.wScan   = scan
        inputs[1].ki.dwFlags = _KEYEVENTF_SCANCODE | _KEYEVENTF_KEYUP | ext
        ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))
        return True

    def _send_combo_scancode(self, keys: list[str]) -> None:
        """Envia combo (ex: ctrl+c) via SendInput scan codes — aceito pelo Roblox.

        Envia key-down de todas as teclas em ordem, depois key-up em ordem reversa,
        num único SendInput para garantir que o OS não intercale outros eventos.
        Se qualquer tecla não mapeia para scan code, cai pra pyautogui.hotkey.
        """
        vks = [_VK_MAP.get(k) for k in keys]
        if any(v is None for v in vks):
            pyautogui.hotkey(*keys)
            return
        # Resolve scan codes uma vez; se alguma der 0, fallback pra pyautogui
        scans = [ctypes.windll.user32.MapVirtualKeyW(vk, 0) for vk in vks]
        if any(s == 0 for s in scans):
            pyautogui.hotkey(*keys)
            return
        n = len(vks)
        inputs = (_INPUT * (n * 2))()
        for i, vk in enumerate(vks):
            ext  = _KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_VKS else 0
            inputs[i].type       = _INPUT_KEYBOARD
            inputs[i].ki.wVk     = 0
            inputs[i].ki.wScan   = scans[i]
            inputs[i].ki.dwFlags = _KEYEVENTF_SCANCODE | ext
        for i, vk in enumerate(reversed(vks)):
            ext  = _KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_VKS else 0
            inputs[n + i].type       = _INPUT_KEYBOARD
            inputs[n + i].ki.wVk     = 0
            inputs[n + i].ki.wScan   = scans[n - 1 - i]
            inputs[n + i].ki.dwFlags = _KEYEVENTF_SCANCODE | _KEYEVENTF_KEYUP | ext
        ctypes.windll.user32.SendInput(n * 2, inputs, ctypes.sizeof(_INPUT))

    def _send_unicode(self, char: str) -> None:
        """Envia um caractere Unicode via user32.SendInput.

        windll: user32.SendInput com flags KEYEVENTF_UNICODE + KEYEVENTF_KEYUP
        Independente do layout de teclado — envia o codepoint diretamente.
        """
        code = ord(char)
        inputs = (_INPUT * 2)()
        # Key down
        inputs[0].type       = _INPUT_KEYBOARD
        inputs[0].ki.wScan   = code
        inputs[0].ki.dwFlags = _KEYEVENTF_UNICODE
        # Key up
        inputs[1].type       = _INPUT_KEYBOARD
        inputs[1].ki.wScan   = code
        inputs[1].ki.dwFlags = _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP
        # windll: user32.SendInput — envia evento de teclado Unicode
        ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))

    def perform_click_virtual(
        self,
        x: int,
        y: int,
        button: str = "left",
        double: bool = False,
        burst: int = 1,
    ) -> None:
        """Envia clique via PostMessage sem mover o cursor físico do mouse.

        windll: user32.WindowFromPoint  — HWND da janela na coordenada dada
        windll: user32.ScreenToClient   — converte coord de tela para cliente
        windll: user32.PostMessageW     — envia WM_LBUTTONDOWN/UP à fila da janela

        Funciona para browsers, apps desktop, etc.
        Não funciona em jogos DirectX/OpenGL que ignoram a message queue.
        """
        user32 = ctypes.windll.user32

        user32.WindowFromPoint.argtypes = [_POINT]
        user32.WindowFromPoint.restype  = wintypes.HWND

        pt = _POINT(int(x), int(y))
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return

        user32.ScreenToClient(hwnd, ctypes.byref(pt))
        lp = (pt.y << 16) | (pt.x & 0xFFFF)

        if button == "right":
            dn, up, mk = _WM_RBUTTONDOWN, _WM_RBUTTONUP, _MK_RBUTTON
        else:
            dn, up, mk = _WM_LBUTTONDOWN, _WM_LBUTTONUP, _MK_LBUTTON

        n = burst * (2 if double else 1)
        for _ in range(n):
            user32.PostMessageW(hwnd, dn, mk, lp)
            user32.PostMessageW(hwnd, up, 0,  lp)

    def get_hwnd_at(self, x: int, y: int) -> tuple[int, str]:
        """Retorna (hwnd, título) da janela na coordenada de tela dada.

        windll: user32.WindowFromPoint  — HWND da janela na posição
        windll: user32.GetWindowTextW   — título da janela
        """
        user32 = ctypes.windll.user32
        user32.WindowFromPoint.argtypes = [_POINT]
        user32.WindowFromPoint.restype  = wintypes.HWND

        hwnd = user32.WindowFromPoint(_POINT(int(x), int(y)))
        if not hwnd:
            return 0, ""

        # Subir até a janela-raiz (ignora sub-controles dentro da janela)
        root = user32.GetAncestor(hwnd, 2)  # GA_ROOT = 2
        if root:
            hwnd = root

        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return hwnd, buf.value

    def _find_deepest_child_hwnd(self, root_hwnd: int, x_screen: int, y_screen: int) -> int:
        """Desce a hierarquia de HWNDs filhos pra achar o que realmente recebe input.

        Útil pra Discord/Electron/Chrome onde o HWND principal é só o frame e
        o controle que processa o clique é um filho profundo.

        windll: user32.RealChildWindowFromPoint (espera ponto em coords de CLIENTE do pai)
                user32.ScreenToClient (converte screen → client)
        """
        u32 = ctypes.windll.user32
        u32.RealChildWindowFromPoint.argtypes = [wintypes.HWND, _POINT]
        u32.RealChildWindowFromPoint.restype  = wintypes.HWND

        current = root_hwnd
        for _ in range(32):  # cap recursão por segurança
            pt = _POINT(int(x_screen), int(y_screen))
            u32.ScreenToClient(current, ctypes.byref(pt))
            child = u32.RealChildWindowFromPoint(current, pt)
            if not child or child == current:
                break
            current = child
        return current

    def perform_click_to_hwnd(
        self,
        hwnd: int,
        x_screen: int,
        y_screen: int,
        button: str = "left",
        double: bool = False,
        burst: int = 1,
    ) -> None:
        """Envia clique a um HWND específico via PostMessage sem mover o cursor.

        Estratégia melhorada:
          1. Desce até o HWND filho real que recebe input (Discord/Electron usam aninhamento)
          2. Posta WM_MOUSEMOVE primeiro (alguns apps exigem "hover" antes de clique)
          3. Posta WM_LBUTTONDOWN/UP no HWND correto com coords no cliente DELE

        Funciona em apps Win32 padrão e Electron. Não funciona em jogos DirectX
        que ignoram a message queue (Roblox, etc) — use modo "foco temporário".

        windll: user32.RealChildWindowFromPoint, ScreenToClient, PostMessageW
        """
        u32 = ctypes.windll.user32
        # Achar o filho real que recebe input na posição da tela
        target = self._find_deepest_child_hwnd(hwnd, x_screen, y_screen) or hwnd

        # Converter screen → client coords desse target específico
        pt = _POINT(int(x_screen), int(y_screen))
        u32.ScreenToClient(target, ctypes.byref(pt))
        lp = (pt.y << 16) | (pt.x & 0xFFFF)

        if button == "right":
            dn, up, mk = _WM_RBUTTONDOWN, _WM_RBUTTONUP, _MK_RBUTTON
        else:
            dn, up, mk = _WM_LBUTTONDOWN, _WM_LBUTTONUP, _MK_LBUTTON

        _WM_MOUSEMOVE = 0x0200
        n = burst * (2 if double else 1)
        for _ in range(n):
            u32.PostMessageW(target, _WM_MOUSEMOVE, 0,  lp)
            u32.PostMessageW(target, dn,            mk, lp)
            u32.PostMessageW(target, up,            0,  lp)

    def perform_move(self, x: int, y: int) -> None:
        """Move o cursor para a posição dada sem clicar.

        windll: user32.SetCursorPos — move cursor para coordenadas absolutas
        """
        ctypes.windll.user32.SetCursorPos(int(x), int(y))  # windll: user32.SetCursorPos

    def get_position(self) -> Tuple[int, int]:
        """Retorna (x, y) da posição atual do cursor via pyautogui."""
        return pyautogui.position()

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        """Retorna (left, top, width, height) da janela ou None se hwnd inválido.

        windll: user32.GetWindowRect — rect em coordenadas de tela
        """
        rect = wintypes.RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top,
                    rect.right - rect.left, rect.bottom - rect.top)
        return None

    def get_pixel_color(self, x: int, y: int) -> tuple[int, int, int]:
        """Retorna (R, G, B) do pixel na coordenada de tela dada via GDI.

        windll: user32.GetDC + gdi32.GetPixel + user32.ReleaseDC
        """
        # try/finally garante ReleaseDC mesmo se GetPixel lançar — sem isso,
        # vazamento acumula até estourar o limite de 10k handles GDI por processo.
        dc = ctypes.windll.user32.GetDC(0)
        try:
            color = ctypes.windll.gdi32.GetPixel(dc, int(x), int(y))
        finally:
            ctypes.windll.user32.ReleaseDC(0, dc)
        return (color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF)

    def set_clipboard_text(self, text: str) -> bool:
        """Coloca texto Unicode no clipboard do Windows.

        windll: user32.OpenClipboard/EmptyClipboard/SetClipboardData/CloseClipboard
                + kernel32.GlobalAlloc/Lock/Unlock
        Retorna True em sucesso.
        """
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE  = 0x0002

        # Algumas vezes outro app ainda está com o clipboard aberto — tentar 5x
        opened = False
        for _ in range(5):
            if _user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)
        if not opened:
            return False

        try:
            _user32.EmptyClipboard()
            # UTF-16 LE + terminador NUL duplo
            buf = text.encode("utf-16-le") + b"\x00\x00"
            h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(buf))
            if not h:
                return False
            ptr = _kernel32.GlobalLock(h)
            if not ptr:
                _kernel32.GlobalFree(h)
                return False
            ctypes.memmove(ptr, buf, len(buf))
            _kernel32.GlobalUnlock(h)
            # SetClipboardData transfere ownership do hmem para o sistema
            if not _user32.SetClipboardData(CF_UNICODETEXT, h):
                _kernel32.GlobalFree(h)
                return False
            return True
        finally:
            _user32.CloseClipboard()

    def paste_text(self, text: str, preserve_clipboard: bool = True) -> bool:
        """Cola texto via clipboard + Ctrl+V. Instantâneo vs digitar char-by-char.

        Muito mais rápido em apps com auto-format (WhatsApp/Discord) que
        re-processam a cada caractere digitado.

        Se preserve_clipboard=True, salva e restaura o conteúdo anterior.
        Retorna False se o set_clipboard_text falhou (chamador pode fallback
        pra digitação tradicional).
        """
        if not text:
            return True
        saved = ""
        if preserve_clipboard:
            try:
                saved = self.get_clipboard_text()
            except Exception:
                pass
        if not self.set_clipboard_text(text):
            return False
        time.sleep(0.03)  # clipboard "assentar" antes do Ctrl+V
        # Ctrl+V via scan code — funciona em jogos com Raw Input
        self.perform_type("key", "ctrl+v")
        time.sleep(0.05)  # app processar o paste antes de restaurar
        if preserve_clipboard:
            try:
                self.set_clipboard_text(saved)
            except Exception:
                pass
        return True

    def get_clipboard_text(self) -> str:
        """Lê texto Unicode do clipboard do Windows. Retorna '' se vazio/falha.

        windll: user32.OpenClipboard / GetClipboardData(CF_UNICODETEXT) /
                CloseClipboard + kernel32.GlobalLock / GlobalUnlock
        """
        CF_UNICODETEXT = 13
        opened = False
        for _ in range(5):
            if _user32.OpenClipboard(None):
                opened = True
                break
            time.sleep(0.02)
        if not opened:
            return ""
        try:
            h = _user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            ptr = _kernel32.GlobalLock(h)
            if not ptr:
                return ""
            try:
                return ctypes.wstring_at(ptr)
            finally:
                _kernel32.GlobalUnlock(h)
        finally:
            _user32.CloseClipboard()

    def has_opencv(self) -> bool:
        """True se opencv-python (cv2) estiver instalado.

        Sem opencv, `pyautogui.locateOnScreen(..., confidence=X)` falha — a
        feature de image_click / if_image / stop condition por imagem precisa dele.
        """
        try:
            import cv2  # noqa: F401
            return True
        except ImportError:
            return False

    def find_image_on_screen(
        self,
        image_data_b64: str | None,
        threshold: float = 0.9,
        timeout_ms: int = 0,
    ) -> tuple[int, int, int, int] | None:
        """Procura imagem template na tela. Retorna (left, top, w, h) ou None.

        timeout_ms=0 = uma única tentativa; >0 = retry até encontrar ou timeout.
        Usa pyautogui.locateOnScreen (requer Pillow + opencv-python).
        """
        if not image_data_b64:
            return None
        try:
            import base64
            import io
            from PIL import Image
        except ImportError:
            return None
        try:
            tpl_img = Image.open(io.BytesIO(base64.b64decode(image_data_b64)))
        except Exception:
            return None

        deadline = time.time() + max(0, timeout_ms) / 1000
        last_err: Exception | None = None
        while True:
            try:
                found = pyautogui.locateOnScreen(tpl_img, confidence=max(0.5, min(1.0, threshold)))
            except Exception as exc:
                found = None
                last_err = exc
            if found:
                return (int(found.left), int(found.top),
                        int(found.width), int(found.height))
            if timeout_ms <= 0 or time.time() >= deadline:
                # Se NUNCA achou E houve exceção persistente E opencv falta,
                # registra o erro como atributo para a UI poder mostrar diagnóstico
                if last_err is not None and not self.has_opencv():
                    self._last_image_error = (
                        "opencv-python não instalado — image_click não funciona. "
                        "Rode: pip install opencv-python"
                    )
                return None
            time.sleep(0.1)

    def capture_region(self, x: int, y: int, w: int, h: int):
        """Captura screenshot de uma região da tela via PIL.ImageGrab.

        Retorna PIL.Image ou None se PIL/ImageGrab não disponível.
        """
        try:
            from PIL import ImageGrab
            return ImageGrab.grab(bbox=(int(x), int(y), int(x + w), int(y + h)))
        except Exception:
            return None

    def run_ocr(self, image, lang: str = "eng", whitelist: str = "") -> str:
        """Extrai texto de uma imagem PIL via Tesseract (pytesseract).

        Retorna '' se pytesseract/Tesseract indisponível ou erro de leitura.
        """
        if image is None:
            return ""
        try:
            import pytesseract
            config = ""
            if whitelist:
                # Escapa aspas pra não quebrar a config string
                safe = whitelist.replace('"', '')
                config = f'-c tessedit_char_whitelist="{safe}"'
            return pytesseract.image_to_string(image, lang=lang or "eng", config=config).strip()
        except Exception:
            return ""

    def has_tesseract(self) -> bool:
        """True se pytesseract conseguir invocar o binário do Tesseract."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def set_dark_mode(self, hwnd: int, enable: bool = True) -> None:
        """Aplica/remove barra de título escura à janela via DWM.

        windll: dwmapi.DwmSetWindowAttribute
        Atributo 20 (DWMWA_USE_IMMERSIVE_DARK_MODE): 1 = dark, 0 = light.
        """
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(   # windll: dwmapi.DwmSetWindowAttribute
                hwnd, 20, ctypes.byref(ctypes.c_int(1 if enable else 0)), 4
            )
        except Exception:
            pass

    def make_clickthrough(self, hwnd: int) -> None:
        """Torna uma janela transparente a cliques do mouse (overlay).

        windll: user32.GetWindowLongW  — lê estilo estendido da janela
        windll: user32.SetWindowLongW  — aplica WS_EX_LAYERED | WS_EX_TRANSPARENT
        GWL_EXSTYLE = -20, WS_EX_LAYERED = 0x80000, WS_EX_TRANSPARENT = 0x20
        """
        try:
            user32 = ctypes.windll.user32                 # windll
            style = user32.GetWindowLongW(hwnd, -20)      # windll: user32.GetWindowLongW (GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)  # windll: user32.SetWindowLongW
        except Exception:
            pass
