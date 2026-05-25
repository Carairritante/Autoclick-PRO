"""
ui/widgets.py — Helpers de widgets tkinter compartilhados entre app.py e step_dialog.py.
"""
from __future__ import annotations

import time
import tkinter as tk

# ── Constantes pra Toast ──────────────────────────────────────────────────────
_TOAST_COLORS = {
    "info":    {"bg": "#5865f2", "fg": "white"},   # blurple (info)
    "success": {"bg": "#23a55a", "fg": "white"},   # verde Discord
    "warning": {"bg": "#f0b232", "fg": "#1a1a1a"}, # ambar
    "error":   {"bg": "#f23f43", "fg": "white"},   # vermelho Discord
}
_TOAST_ICONS = {
    "info":    "ℹ",
    "success": "✓",
    "warning": "⚠",
    "error":   "✕",
}
_TOAST_STACK: list["Toast"] = []
_TOAST_MARGIN = 14
_TOAST_GAP = 8


class Toast:
    """Notificacao efemera no canto inferior-direito da janela raiz.

    Multiplas toasts empilham. Auto-destroem apos `duration_ms`.
    Estilo determinado por `level`: info|success|warning|error.

    Uso:
        from ui.widgets import show_toast
        show_toast(root, "Slot 1 salvo", level="success")
    """

    def __init__(self, root: tk.Tk, message: str,
                  level: str = "info", duration_ms: int = 2800) -> None:
        self._root = root
        self._destroyed = False
        colors = _TOAST_COLORS.get(level, _TOAST_COLORS["info"])
        icon = _TOAST_ICONS.get(level, "")

        self._tw = tk.Toplevel(root)
        self._tw.overrideredirect(True)
        self._tw.attributes("-topmost", True)
        try:
            self._tw.attributes("-alpha", 0.0)   # comeca invisivel pra fade-in
        except Exception:
            pass
        self._tw.configure(bg=colors["bg"])

        # Conteudo: icone + texto, padding generoso
        frame = tk.Frame(self._tw, bg=colors["bg"], padx=14, pady=10)
        frame.pack()
        if icon:
            tk.Label(frame, text=icon, bg=colors["bg"], fg=colors["fg"],
                     font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 8))
        tk.Label(frame, text=message, bg=colors["bg"], fg=colors["fg"],
                 font=("Segoe UI", 10), justify="left").pack(side="left")

        _TOAST_STACK.append(self)
        self._reposition_all()
        self._fade_in()
        # Auto-fechar
        self._after_id = root.after(duration_ms, self._fade_out)
        # Clique fecha imediatamente
        self._tw.bind("<Button-1>", lambda e: self._fade_out())
        for child in self._walk_children(self._tw):
            child.bind("<Button-1>", lambda e: self._fade_out())

    def _walk_children(self, w):
        for c in w.winfo_children():
            yield c
            yield from self._walk_children(c)

    def _fade_in(self, alpha: float = 0.0) -> None:
        if self._destroyed:
            return
        alpha = min(1.0, alpha + 0.15)
        try:
            self._tw.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self._root.after(20, lambda: self._fade_in(alpha))

    def _fade_out(self, alpha: float = 1.0) -> None:
        if self._destroyed:
            return
        if alpha <= 0.0:
            self._destroy()
            return
        try:
            self._tw.attributes("-alpha", alpha)
        except Exception:
            self._destroy()
            return
        alpha -= 0.12
        self._root.after(20, lambda: self._fade_out(alpha))

    def _destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        try:
            self._root.after_cancel(self._after_id)
        except Exception:
            pass
        try:
            self._tw.destroy()
        except Exception:
            pass
        if self in _TOAST_STACK:
            _TOAST_STACK.remove(self)
        self._reposition_all()

    def _reposition_all(self) -> None:
        """Reposiciona todas as toasts ativas no canto inferior-direito da root."""
        try:
            self._root.update_idletasks()
            root_x = self._root.winfo_rootx()
            root_y = self._root.winfo_rooty()
            root_w = self._root.winfo_width()
            root_h = self._root.winfo_height()
        except Exception:
            return
        y_offset = _TOAST_MARGIN
        # Empilha de baixo pra cima (mais recente embaixo)
        for toast in reversed(_TOAST_STACK):
            if toast._destroyed:
                continue
            try:
                toast._tw.update_idletasks()
                tw_w = toast._tw.winfo_width()
                tw_h = toast._tw.winfo_height()
                x = root_x + root_w - tw_w - _TOAST_MARGIN
                y = root_y + root_h - tw_h - y_offset
                toast._tw.geometry(f"+{x}+{y}")
                y_offset += tw_h + _TOAST_GAP
            except Exception:
                continue


def show_toast(root: tk.Tk, message: str, level: str = "info",
                duration_ms: int = 2800) -> Toast | None:
    """Atalho pra criar uma Toast. Retorna None em caso de falha (testes headless)."""
    try:
        return Toast(root, message, level=level, duration_ms=duration_ms)
    except Exception:
        return None


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
    padx: int = 12,
    pady: int = 6,
    width: int | None = None,
    hover_bg: str | None = None,
) -> tk.Button:
    """tk.Button estilo flat, hover sutil, cursor hand2.

    Defaults modernos: padx=12, pady=6 (mais espaco visual que o padrao do tk).
    """
    font = ("Segoe UI", font_size, "bold" if bold else "normal")
    kw: dict = dict(bg=bg, fg=fg, font=font, relief="flat",
                    padx=padx, pady=pady, cursor="hand2",
                    activeforeground=fg, bd=0,
                    highlightthickness=0, takefocus=0)
    if width is not None:
        kw["width"] = width
    btn = tk.Button(parent, text=text, command=command, **kw)
    hover_in = hover_bg or _shift(bg, amount=22)   # hover ligeiramente mais visivel
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
