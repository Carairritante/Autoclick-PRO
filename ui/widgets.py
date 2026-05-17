"""
ui/widgets.py — Helpers de widgets tkinter compartilhados entre app.py e step_dialog.py.
"""
from __future__ import annotations

import time
import tkinter as tk


def _shift(hex_color: str, amount: int = 18) -> str:
    """Clareia tons escuros e escurece tons claros — universal pra dark+light."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        avg = (r + g + b) / 3
        if avg < 128:                 # cor escura → clareia
            r = min(255, r + amount)
            g = min(255, g + amount)
            b = min(255, b + amount)
        else:                          # cor clara → escurece
            r = max(0, r - amount)
            g = max(0, g - amount)
            b = max(0, b - amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def make_button(
    parent,
    text: str,
    command,
    bg: str,
    fg: str = "white",
    font_size: int = 9,
    bold: bool = True,
    padx: int = 10,
    pady: int = 5,
    width: int | None = None,
    hover_bg: str | None = None,
) -> tk.Button:
    """tk.Button estilo flat, hover sutil, cursor hand2."""
    font = ("Segoe UI", font_size, "bold" if bold else "normal")
    kw: dict = dict(bg=bg, fg=fg, font=font, relief="flat",
                    padx=padx, pady=pady, cursor="hand2",
                    activeforeground=fg, bd=0,
                    highlightthickness=0, takefocus=0)
    if width is not None:
        kw["width"] = width
    btn = tk.Button(parent, text=text, command=command, **kw)
    hover_in = hover_bg or _shift(bg)
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_in))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    btn.config(activebackground=hover_in)
    return btn


class Tooltip:
    """Tooltip que aparece após hover de `delay_ms` sobre um widget.

    Para widgets simples (botão, label), passe `text` como string fixa.
    Para Treeview/Listbox onde o texto depende da linha, passe `get_text`
    como callable(event) que retorna a string ou None (sem tooltip).
    """

    def __init__(self, widget, text: str | None = None,
                  get_text=None, delay_ms: int = 600,
                  wraplength: int = 380) -> None:
        self._widget = widget
        self._text   = text
        self._get_text = get_text
        self._delay  = delay_ms
        self._wrap   = wraplength
        self._tw: tk.Toplevel | None = None
        self._after_id = None
        self._last_text: str | None = None
        self._last_motion_t: float = 0.0   # throttle de <Motion>
        widget.bind("<Motion>", self._on_motion)
        widget.bind("<Leave>",  self._on_leave)

    def _resolve_text(self, event) -> str | None:
        if self._get_text is not None:
            try:
                return self._get_text(event)
            except Exception:
                return None
        return self._text

    def _on_motion(self, event) -> None:
        # Throttle: <Motion> dispara por pixel — sem isso, identify_row/index
        # rodam centenas de vezes/segundo durante hover rápido. 40ms é
        # imperceptível para o usuário.
        now = time.monotonic()
        if now - self._last_motion_t < 0.04:
            return
        self._last_motion_t = now
        text = self._resolve_text(event)
        if text != self._last_text:
            # Texto mudou (mudou de linha, ou saiu de linha válida) — reseta
            self._hide()
            self._last_text = text
            if text:
                self._after_id = self._widget.after(
                    self._delay, lambda e=event, t=text: self._show(e, t)
                )

    def _on_leave(self, event) -> None:
        self._hide()
        self._last_text = None

    def _show(self, event, text: str) -> None:
        if self._tw is not None:
            return
        x = self._widget.winfo_rootx() + event.x + 14
        y = self._widget.winfo_rooty() + event.y + 18
        self._tw = tk.Toplevel(self._widget)
        self._tw.wm_overrideredirect(True)   # sem barra de título
        self._tw.wm_geometry(f"+{x}+{y}")
        # Cores fixas: amarelo pálido + preto — convenção Windows, legível
        # em dark e light themes (não acompanha o tema do app).
        lbl = tk.Label(self._tw, text=text, justify="left",
                       background="#fffacd", foreground="#000000",
                       relief="solid", borderwidth=1,
                       font=("Segoe UI", 9), padx=6, pady=4,
                       wraplength=self._wrap)
        lbl.pack()

    def _hide(self) -> None:
        if self._after_id is not None:
            try: self._widget.after_cancel(self._after_id)
            except Exception: pass
            self._after_id = None
        if self._tw is not None:
            try: self._tw.destroy()
            except Exception: pass
            self._tw = None
