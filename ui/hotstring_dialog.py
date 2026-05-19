"""
ui/hotstring_dialog.py — Diálogo modal para criar/editar uma hotstring.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ui.widgets import make_button


class HotstringDialog(tk.Toplevel):
    """Diálogo modal para criar/editar uma hotstring (trigger + expand)."""

    def __init__(self, parent: tk.Tk, theme: dict,
                 hs: dict | None = None) -> None:
        super().__init__(parent)
        self._T = theme
        self.result: dict | None = None
        self.title("Editar Hotstring" if hs else "Nova Hotstring")
        self.configure(bg=theme["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._v_trigger = tk.StringVar(value=hs.get("trigger", "") if hs else ":")
        self._v_enabled = tk.BooleanVar(value=hs.get("enabled", True) if hs else True)
        self._v_force_type = tk.BooleanVar(
            value=bool(hs.get("force_type", False)) if hs else False)
        initial_expand = hs.get("expand", "") if hs else ""

        T = theme
        body = tk.Frame(self, bg=T["bg"]); body.pack(fill="both", padx=16, pady=14)

        tk.Label(body, text="Trigger (texto que dispara):",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 10)
                 ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        tk.Entry(body, textvariable=self._v_trigger, width=30, bg=T["card"],
                 fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                 relief="flat", bd=4).grid(row=1, column=0, sticky="w")
        tk.Label(body, text='Sugestão: use ":" como delimitador. Ex: ":mail:", ":pix:"',
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).grid(row=2, column=0, sticky="w", pady=(2, 8))

        tk.Label(body, text="Expansão (o texto que vai ser digitado):",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 10)
                 ).grid(row=3, column=0, sticky="w", pady=(0, 4))
        # Frame com Text + Scrollbar lateral — necessário pra textos longos
        text_frame = tk.Frame(body, bg=T["bg"])
        text_frame.grid(row=4, column=0, sticky="we")
        self._expand_text = tk.Text(text_frame, height=6, width=46,
                                     bg=T["card"], fg=T["text"],
                                     insertbackground=T["text"],
                                     font=("Consolas", 10), relief="flat",
                                     padx=6, pady=4, wrap="word")
        self._expand_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(text_frame, orient="vertical",
                            command=self._expand_text.yview)
        sb.pack(side="right", fill="y")
        self._expand_text.config(yscrollcommand=sb.set)
        if initial_expand:
            self._expand_text.insert("1.0", initial_expand)

        tk.Checkbutton(body, text="Ativada", variable=self._v_enabled,
                        bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                        activebackground=T["bg"],
                        font=("Segoe UI", 10)
                        ).grid(row=5, column=0, sticky="w", pady=(8, 0))

        tk.Checkbutton(body, text="Forçar digitação tecla-por-tecla (para Roblox/jogos)",
                        variable=self._v_force_type,
                        bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                        activebackground=T["bg"],
                        font=("Segoe UI", 10)
                        ).grid(row=6, column=0, sticky="w", pady=(2, 0))
        tk.Label(body, text="Use isso se a expansão não aparece em algum app que "
                              "bloqueia Ctrl+V (Roblox, etc).",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                 wraplength=380, justify="left"
                 ).grid(row=7, column=0, sticky="w", pady=(0, 4))

        btns = tk.Frame(body, bg=T["bg"]); btns.grid(row=8, column=0, sticky="we", pady=(12, 0))
        make_button(btns, "✔ OK", self._ok, T["accent"], fg="#ffffff",
                    padx=14, pady=6).pack(side="left", padx=(0, 8))
        make_button(btns, "✕ Cancelar", self.destroy, T["card"], fg=T["text"],
                    padx=12, pady=6).pack(side="left")

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _ok(self) -> None:
        trig = self._v_trigger.get().strip()
        expand = self._expand_text.get("1.0", "end-1c")
        if not trig:
            messagebox.showwarning("Trigger vazio", "Defina um trigger.", parent=self)
            return
        self.result = {
            "trigger": trig,
            "expand": expand,
            "enabled": bool(self._v_enabled.get()),
            "force_type": bool(self._v_force_type.get()),
        }
        self.destroy()
