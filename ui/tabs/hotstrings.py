"""
ui/tabs/hotstrings.py — Aba ✨ Hotstrings + lógica de atalhos de texto.

Requisitos do host (AutoClickPro):
  Attrs:   _hotstrings, tab_hs, var_hotstrings_active
  Métodos: _make_scrollable, _section, _btn, _set_status
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.paths import HOTSTRINGS_PATH
from ui.hotstring_dialog import HotstringDialog
from ui.theme import T


class HotstringTabMixin:
    # ─────────────────────────────────────────────────────────────
    # ABA: HOTSTRINGS (atalhos de texto)
    # ─────────────────────────────────────────────────────────────
    def _build_hotstrings_tab(self) -> None:
        p = self._make_scrollable(self.tab_hs)

        self._section(p, "Hotstrings — Atalhos de Texto", "✨ ").pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Digite um trigger em qualquer app pra expandir o texto.\n"
                          'Ex: digite ":mail:" → vira "seu@email.com" automaticamente.',
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(fill="x", padx=14, pady=(0, 6))

        toggle_row = tk.Frame(p, bg=T["bg"])
        toggle_row.pack(fill="x", padx=14, pady=4)
        tk.Checkbutton(toggle_row, text="🟢 Ativar Hotstrings Globalmente",
                        variable=self.var_hotstrings_active,
                        command=self._toggle_hotstrings,
                        bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                        activebackground=T["bg"],
                        font=("Segoe UI", 10, "bold")).pack(side="left")
        self._hs_status = tk.Label(toggle_row, text="(desligado)",
                                    bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9))
        self._hs_status.pack(side="left", padx=8)

        btn_row = tk.Frame(p, bg=T["bg"])
        btn_row.pack(fill="x", padx=14, pady=(6, 4))
        self._btn(btn_row, "➕ Adicionar", self._hs_add,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=(0, 4))
        self._btn(btn_row, "✏ Editar", self._hs_edit,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
        self._btn(btn_row, "✕ Remover", self._hs_remove,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)

        tree_frame = tk.Frame(p, bg=T["bg"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        self.hs_tree = ttk.Treeview(
            tree_frame, columns=("trigger", "expand", "enabled"),
            show="headings", style="Seq.Treeview", height=10,
        )
        self.hs_tree.heading("trigger", text="Trigger")
        self.hs_tree.heading("expand",  text="Expansão")
        self.hs_tree.heading("enabled", text="Ativada")
        self.hs_tree.column("trigger", width=120, anchor="w")
        self.hs_tree.column("expand",  width=320, anchor="w")
        self.hs_tree.column("enabled", width=70,  anchor="center")
        self.hs_tree.pack(fill="both", expand=True, side="left")
        self.hs_tree.bind("<Double-1>", lambda e: self._hs_toggle_enabled())

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.hs_tree.yview)
        sb.pack(side="right", fill="y")
        self.hs_tree.config(yscrollcommand=sb.set)

    def _refresh_hs_tree(self) -> None:
        if not hasattr(self, "hs_tree"):
            return
        for item in self.hs_tree.get_children():
            self.hs_tree.delete(item)
        for hs in self._hotstrings.get_all():
            trig = hs.get("trigger", "")
            expand = hs.get("expand", "")
            preview = (expand[:50] + "…") if len(expand) > 50 else expand
            on = "✓" if hs.get("enabled", True) else "—"
            self.hs_tree.insert("", "end", values=(trig, preview, on))

    def _save_hotstrings(self) -> None:
        try:
            self._hotstrings.save(HOTSTRINGS_PATH)
        except OSError as exc:
            messagebox.showerror("Erro ao salvar hotstrings",
                                  f"Não foi possível salvar:\n{exc}", parent=self)

    def _toggle_hotstrings(self) -> None:
        if self.var_hotstrings_active.get():
            self._hotstrings.start()
            self._hs_status.config(text="🟢 (ativo)", fg=T["green"])
            self._set_status("✨  Hotstrings ativadas globalmente.")
        else:
            self._hotstrings.stop()
            self._hs_status.config(text="(desligado)", fg=T["subtext"])
            self._set_status("✨  Hotstrings desativadas.")

    def _hs_add(self) -> None:
        dlg = HotstringDialog(self, T)
        self.wait_window(dlg)
        if dlg.result:
            items = self._hotstrings.get_all()
            items.append(dlg.result)
            self._hotstrings.set_all(items)
            self._save_hotstrings()
            self._refresh_hs_tree()

    def _hs_edit(self) -> None:
        sel = self.hs_tree.selection()
        if not sel:
            return
        idx = self.hs_tree.index(sel[0])
        items = self._hotstrings.get_all()
        if idx < 0 or idx >= len(items):
            return
        dlg = HotstringDialog(self, T, items[idx])
        self.wait_window(dlg)
        if dlg.result:
            items[idx] = dlg.result
            self._hotstrings.set_all(items)
            self._save_hotstrings()
            self._refresh_hs_tree()

    def _hs_remove(self) -> None:
        sel = self.hs_tree.selection()
        if not sel:
            return
        idx = self.hs_tree.index(sel[0])
        items = self._hotstrings.get_all()
        if 0 <= idx < len(items):
            del items[idx]
            self._hotstrings.set_all(items)
            self._save_hotstrings()
            self._refresh_hs_tree()

    def _hs_toggle_enabled(self) -> None:
        sel = self.hs_tree.selection()
        if not sel:
            return
        idx = self.hs_tree.index(sel[0])
        items = self._hotstrings.get_all()
        if 0 <= idx < len(items):
            items[idx]["enabled"] = not items[idx].get("enabled", True)
            self._hotstrings.set_all(items)
            self._save_hotstrings()
            self._refresh_hs_tree()
