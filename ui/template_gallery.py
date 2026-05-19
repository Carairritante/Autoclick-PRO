"""
ui/template_gallery.py — Modal de galeria de templates.

Dois modos:
  - welcome=True: primeira execução; mostra texto "Bem-vindo!" no topo
    e botão "Pular por agora". Cria flag de onboarding ao fechar.
  - welcome=False: abertura manual via botão "📚 Exemplos" no footer.
    Sem welcome text, sem flag.
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

from core.paths import ONBOARDING_PATH, PROFILES_DIR
from ui.templates import (
    Template,
    apply_template,
    templates_by_category,
)
from ui.widgets import make_button


CARD_WIDTH = 260   # largura mínima de cada card
CARDS_PER_ROW = 2  # grid 2 colunas
ONBOARDING_VERSION = 1


class TemplateGallery(tk.Toplevel):
    """Modal com tabs por categoria + grid de cards de templates."""

    def __init__(self, parent: tk.Tk, theme: dict, app,
                 welcome: bool = False) -> None:
        super().__init__(parent)
        self._T = theme
        self._app = app
        self._welcome = welcome
        self.title("Bem-vindo ao AutoClick Pro!" if welcome
                   else "Templates e Exemplos")
        self.configure(bg=theme["bg"])
        self.transient(parent)
        self.grab_set()
        self.minsize(620, 540)
        self.geometry("680x600")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()

        # Centraliza na janela pai
        self.update_idletasks()
        try:
            px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
            py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        T = self._T

        # Header (welcome mode mostra mensagem)
        if self._welcome:
            head = tk.Frame(self, bg=T["bg"])
            head.pack(fill="x", padx=20, pady=(16, 4))
            tk.Label(head, text="👋 Bem-vindo ao AutoClick Pro!",
                     bg=T["bg"], fg=T["accent"],
                     font=("Segoe UI", 16, "bold")
                     ).pack(anchor="w")
            tk.Label(head,
                     text="Que tal experimentar um exemplo pronto? Escolha uma categoria abaixo.",
                     bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)
                     ).pack(anchor="w", pady=(2, 0))
            tk.Frame(self, bg=T["line"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        # Notebook com uma aba por categoria
        nb_frame = tk.Frame(self, bg=T["bg"])
        nb_frame.pack(fill="both", expand=True, padx=14, pady=10)

        nb = ttk.Notebook(nb_frame)
        nb.pack(fill="both", expand=True)
        self._nb = nb

        cats = templates_by_category()
        for cat_name, items in cats.items():
            if not items:
                continue
            tab = tk.Frame(nb, bg=T["bg"])
            nb.add(tab, text=f" {cat_name} ")
            self._build_category_tab(tab, items)

        # Footer
        ftr = tk.Frame(self, bg=T["bg"])
        ftr.pack(fill="x", padx=20, pady=(6, 14))
        tk.Frame(self, bg=T["line"], height=1).pack(fill="x", padx=20,
                                                     before=ftr)

        if self._welcome:
            make_button(ftr, "Pular por agora", self._on_close,
                        T["card"], fg=T["text"], padx=14, pady=6
                        ).pack(side="right", padx=(8, 0))
            tk.Label(ftr,
                     text="Você pode reabrir essa janela a qualquer momento pelo botão 📚 no rodapé.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).pack(side="left")
        else:
            make_button(ftr, "Fechar", self._on_close,
                        T["accent"], fg="#ffffff", padx=14, pady=6
                        ).pack(side="right")

    # ─────────────────────────────────────────────────────────────
    # ABA DE CATEGORIA (scroll frame com grid de cards)
    # ─────────────────────────────────────────────────────────────
    def _build_category_tab(self, parent: tk.Frame,
                             templates: list[Template]) -> None:
        T = self._T

        # Canvas + scrollbar pra muitos cards
        canvas = tk.Canvas(parent, bg=T["bg"], highlightthickness=0,
                            borderwidth=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=T["bg"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)

        def _cfg(e):  canvas.configure(scrollregion=canvas.bbox("all"))
        def _cvs(e):  canvas.itemconfig(win_id, width=e.width)
        def _wheel(e): canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        inner.bind("<Configure>", _cfg)
        canvas.bind("<Configure>", _cvs)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Grid de cards
        for i, tpl in enumerate(templates):
            r, c = divmod(i, CARDS_PER_ROW)
            card = self._build_card(inner, tpl)
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
        for c in range(CARDS_PER_ROW):
            inner.grid_columnconfigure(c, weight=1, uniform="cards")

    # ─────────────────────────────────────────────────────────────
    # CARD INDIVIDUAL
    # ─────────────────────────────────────────────────────────────
    def _build_card(self, parent: tk.Frame, tpl: Template) -> tk.Frame:
        T = self._T

        card = tk.Frame(parent, bg=T["card"], padx=14, pady=12,
                        highlightbackground=T["line"], highlightthickness=1)

        # Hover effect: muda bg do card e dos labels filhos
        def _set_bg(bg: str) -> None:
            try:
                card.config(bg=bg)
                for child in card.winfo_children():
                    if isinstance(child, (tk.Label, tk.Frame)):
                        try: child.config(bg=bg)
                        except Exception: pass
            except Exception:
                pass

        card.bind("<Enter>", lambda e: _set_bg(T["card_h"]))
        card.bind("<Leave>", lambda e: _set_bg(T["card"]))

        # Linha 1: icon emoji grande
        tk.Label(card, text=tpl.icon, bg=T["card"], fg=T["text"],
                 font=("Segoe UI Emoji", 22)
                 ).pack(anchor="w", pady=(0, 2))

        # Linha 2: nome
        tk.Label(card, text=tpl.name, bg=T["card"], fg=T["text"],
                 font=("Segoe UI", 11, "bold"), anchor="w"
                 ).pack(fill="x")

        # Linha 3: tipo (chip pequeno)
        type_label = {
            "autoclick": "🖱 AutoClick",
            "autokey":   "⌨ AutoKey",
            "macro":     "🤖 Macro",
            "hotstring": "✨ Hotstring",
        }.get(tpl.type, tpl.type)
        tk.Label(card, text=type_label, bg=T["card"], fg=T["accent2"],
                 font=("Segoe UI", 8, "bold"), anchor="w"
                 ).pack(fill="x", pady=(0, 4))

        # Linha 4: descrição (wrap)
        tk.Label(card, text=tpl.description, bg=T["card"], fg=T["subtext"],
                 font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=CARD_WIDTH - 30
                 ).pack(fill="x", pady=(2, 6))

        # Warning opcional (vermelho discreto)
        if tpl.warning:
            tk.Label(card, text=f"⚠ {tpl.warning}",
                     bg=T["card"], fg=T["red"],
                     font=("Segoe UI", 8), anchor="w", justify="left",
                     wraplength=CARD_WIDTH - 30
                     ).pack(fill="x", pady=(0, 6))

        # Botão usar este
        btn = make_button(card, "Usar este", lambda t=tpl: self._on_use(t),
                          T["accent"], fg="#ffffff",
                          font_size=9, bold=True, padx=10, pady=4)
        btn.pack(anchor="w")

        return card

    # ─────────────────────────────────────────────────────────────
    # AÇÕES
    # ─────────────────────────────────────────────────────────────
    def _on_use(self, tpl: Template) -> None:
        ok = apply_template(self._app, tpl)
        if ok:
            self._mark_onboarding_done()
            self.destroy()

    def _on_close(self) -> None:
        self._mark_onboarding_done()
        self.destroy()

    def _mark_onboarding_done(self) -> None:
        """Cria flag indicando que usuário já viu o wizard. Só em modo welcome."""
        if not self._welcome:
            return
        try:
            os.makedirs(PROFILES_DIR, exist_ok=True)
            data = {"completed": True, "version": ONBOARDING_VERSION}
            tmp = ONBOARDING_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, ONBOARDING_PATH)
        except OSError:
            pass  # silencioso — pior caso é mostrar o welcome de novo
