"""
ui/window_picker.py — Modal para selecionar uma janela aberta do Windows.

Reusado por:
  - ui/tabs/click.py (janela alvo do AutoClick)
  - ui/monitor_dialog.py (janela alvo de monitor)
"""
from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import ttk

from ui.widgets import make_button


def list_visible_windows(exclude_titles: tuple[str, ...] = ("AutoClick Pro",)
                          ) -> list[tuple[int, str]]:
    """Enumera todas as janelas visíveis com título. Retorna [(hwnd, title), ...]."""
    windows: list[tuple[int, str]] = []
    user32 = ctypes.windll.user32

    def _cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title and title not in exclude_titles:
            windows.append((hwnd, title))
        return True

    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(cb_type(_cb), 0)
    windows.sort(key=lambda w: w[1].lower())
    return windows


def pick_window(parent: tk.Tk, theme: dict,
                title_text: str = "Selecionar Janela Alvo",
                prompt: str = "Escolha uma janela:"
                ) -> tuple[int, str] | None:
    """Abre modal listando janelas visíveis. Retorna (hwnd, title) ou None.

    Bloqueia até o usuário confirmar (Selecionar/Double-click/Enter) ou
    cancelar (Cancelar/Escape/fechar).
    """
    T = theme
    windows = list_visible_windows()
    if not windows:
        return None

    result: list[tuple[int, str] | None] = [None]

    dlg = tk.Toplevel(parent)
    dlg.title(title_text)
    dlg.configure(bg=T["bg"])
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.attributes("-topmost", True)

    tk.Label(dlg, text=prompt,
             bg=T["bg"], fg=T["text"], font=("Segoe UI", 10)
             ).pack(padx=16, pady=(12, 6), anchor="w")

    frame = tk.Frame(dlg, bg=T["bg"])
    frame.pack(padx=16, fill="both", expand=True)

    sb = ttk.Scrollbar(frame)
    sb.pack(side="right", fill="y")
    lb = tk.Listbox(frame, yscrollcommand=sb.set, bg=T["card"], fg=T["text"],
                    selectbackground=T["accent"], font=("Segoe UI", 10),
                    width=52, height=14, relief="flat", bd=0,
                    activestyle="none")
    lb.pack(side="left", fill="both", expand=True)
    sb.config(command=lb.yview)

    for _, title in windows:
        lb.insert("end", title)

    lb.selection_set(0)
    lb.activate(0)

    def _confirm():
        sel = lb.curselection()
        if not sel:
            return
        result[0] = windows[sel[0]]
        dlg.destroy()

    btn_row = tk.Frame(dlg, bg=T["bg"])
    btn_row.pack(pady=10)
    make_button(btn_row, "Selecionar", _confirm,
                bg=T["text"], fg=T["bg"], bold=True, padx=16).pack(side="left", padx=6)
    make_button(btn_row, "Cancelar", dlg.destroy,
                bg=T["card"], fg=T["text"], padx=12).pack(side="left")

    lb.bind("<Double-1>", lambda e: _confirm())
    dlg.bind("<Return>", lambda e: _confirm())
    dlg.bind("<Escape>", lambda e: dlg.destroy())

    parent.wait_window(dlg)
    return result[0]
