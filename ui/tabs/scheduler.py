"""
ui/tabs/scheduler.py — Aba ⏰ Agendador.

Lista regras (treeview), botões add/edit/remove/toggle, integra com
SchedulerWorker do core. Dispara macros via slot ou arquivo nos horários
configurados.

Requisitos do host (AutoClickPro):
  Attrs:   _scheduler, tab_scheduler
  Métodos: _make_scrollable, _section, _btn, _set_status,
           _load_slot, _start_macro, _apply_script, _apply_ui_profile
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from core.paths import SCHEDULER_PATH
from core.scheduler import ScheduleRule
from ui.theme import T
from ui.scheduler_dialog import ScheduleRuleDialog


WEEKDAY_ABBR = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _freq_label(rule: ScheduleRule) -> str:
    if rule.freq == "daily":
        return f"Todo dia às {rule.time}"
    if rule.freq == "weekly":
        days = ",".join(WEEKDAY_ABBR[i] for i in rule.weekdays if 0 <= i < 7)
        return f"{days or '(sem dias)'} às {rule.time}"
    if rule.freq == "once":
        return f"Uma vez — {rule.date} {rule.time}"
    return rule.freq


def _target_label(rule: ScheduleRule) -> str:
    if rule.macro_kind == "slot":
        return f"Slot {rule.macro_target}"
    return os.path.basename(rule.macro_target or "?")


class SchedulerMixin:
    # ─────────────────────────────────────────────────────────────
    # ABA: AGENDADOR
    # ─────────────────────────────────────────────────────────────
    def _build_scheduler_tab(self) -> None:
        p = self._make_scrollable(self.tab_scheduler)

        self._section(p, "Agendador — Rode Macros em Horário Marcado", "⏰ "
                       ).pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Crie regras que disparam um macro automaticamente em horários definidos.\n"
                          "Ex: 'todo dia às 9h' ou 'segundas e quartas às 14:30'.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(fill="x", padx=14, pady=(0, 6))

        btn_row = tk.Frame(p, bg=T["bg"])
        btn_row.pack(fill="x", padx=14, pady=(6, 4))
        self._btn(btn_row, "➕ Adicionar", self._sched_add,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=(0, 4))
        self._btn(btn_row, "✏ Editar", self._sched_edit,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
        self._btn(btn_row, "✕ Remover", self._sched_remove,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
        self._btn(btn_row, "▶ Disparar agora", self._sched_fire_now,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)

        tree_frame = tk.Frame(p, bg=T["bg"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        self.sched_tree = ttk.Treeview(
            tree_frame, columns=("name", "freq", "target", "enabled"),
            show="headings", style="Seq.Treeview", height=10,
        )
        self.sched_tree.heading("name",    text="Nome")
        self.sched_tree.heading("freq",    text="Quando")
        self.sched_tree.heading("target",  text="Macro")
        self.sched_tree.heading("enabled", text="Ativado")
        self.sched_tree.column("name",    width=180, anchor="w")
        self.sched_tree.column("freq",    width=240, anchor="w")
        self.sched_tree.column("target",  width=140, anchor="w")
        self.sched_tree.column("enabled", width=70,  anchor="center")
        self.sched_tree.pack(fill="both", expand=True, side="left")
        self.sched_tree.bind("<Double-1>", lambda e: self._sched_toggle_enabled())

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                            command=self.sched_tree.yview)
        sb.pack(side="right", fill="y")
        self.sched_tree.config(yscrollcommand=sb.set)

        self._sched_empty_lbl = tk.Label(
            tree_frame,
            text="⏰  Nenhum agendamento ainda.\nClique  ➕ Adicionar  para criar uma regra.",
            bg=T["bg"], fg=T["subtext"],
            font=("Segoe UI", 10), justify="center",
        )
        self._sched_empty_lbl.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(p, text="Dica: dê duplo-clique pra ativar/desativar uma regra.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(fill="x", padx=14, pady=(0, 8))

        self._refresh_sched_tree()

    def _refresh_sched_tree(self) -> None:
        if not hasattr(self, "sched_tree"):
            return
        for item in self.sched_tree.get_children():
            self.sched_tree.delete(item)
        rules = self._scheduler.get_all()
        for rule in rules:
            on = "🟢" if rule.enabled else "—"
            self.sched_tree.insert(
                "", "end",
                iid=rule.id,
                values=(rule.name or "(sem nome)",
                        _freq_label(rule), _target_label(rule), on),
            )
        if hasattr(self, "_sched_empty_lbl"):
            if rules:
                self._sched_empty_lbl.place_forget()
            else:
                self._sched_empty_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _save_scheduler(self) -> None:
        try:
            self._scheduler.save(SCHEDULER_PATH)
        except OSError as exc:
            messagebox.showerror("Erro ao salvar agendamentos",
                                  f"Não foi possível salvar:\n{exc}", parent=self)

    def _sched_add(self) -> None:
        dlg = ScheduleRuleDialog(self, T)
        self.wait_window(dlg)
        if dlg.result:
            self._scheduler.add(dlg.result)
            self._save_scheduler()
            self._refresh_sched_tree()
            self._set_status(f"⏰  Agendamento '{dlg.result.name}' criado.")

    def _sched_edit(self) -> None:
        sel = self.sched_tree.selection()
        if not sel:
            return
        rule_id = sel[0]
        rules = self._scheduler.get_all()
        existing = next((r for r in rules if r.id == rule_id), None)
        if not existing:
            return
        dlg = ScheduleRuleDialog(self, T, existing)
        self.wait_window(dlg)
        if dlg.result:
            self._scheduler.update(rule_id, dlg.result)
            self._save_scheduler()
            self._refresh_sched_tree()

    def _sched_remove(self) -> None:
        sel = self.sched_tree.selection()
        if not sel:
            return
        rule_id = sel[0]
        if not messagebox.askyesno("Remover agendamento?",
                                    "Tem certeza que quer remover esta regra?",
                                    parent=self):
            return
        self._scheduler.remove(rule_id)
        self._save_scheduler()
        self._refresh_sched_tree()

    def _sched_toggle_enabled(self) -> None:
        sel = self.sched_tree.selection()
        if not sel:
            return
        rule_id = sel[0]
        self._scheduler.toggle(rule_id)
        self._save_scheduler()
        self._refresh_sched_tree()

    def _sched_fire_now(self) -> None:
        """Dispara o macro da regra selecionada imediatamente (teste)."""
        sel = self.sched_tree.selection()
        if not sel:
            return
        rule_id = sel[0]
        rule = next((r for r in self._scheduler.get_all() if r.id == rule_id), None)
        if rule:
            self._fire_schedule(rule)

    def _fire_schedule(self, rule: ScheduleRule) -> None:
        """Carrega o macro do rule.macro_kind/target e inicia execução.

        Chamado pelo worker via app.after — já está na main thread.
        """
        try:
            if rule.macro_kind == "slot":
                try:
                    slot = int(rule.macro_target)
                except (TypeError, ValueError):
                    self._set_status(f"⏰  Agendamento '{rule.name}': slot inválido.")
                    return
                self._load_slot(slot)
            else:
                # file
                path = rule.macro_target
                if not path or not os.path.exists(path):
                    self._set_status(f"⏰  Agendamento '{rule.name}': arquivo não encontrado.")
                    return
                import json as _json
                from core.macro_schema import script_from_dict, ui_from_dict
                with open(path, encoding="utf-8") as f:
                    data = _json.load(f)
                self._apply_script(script_from_dict(data))
                self._apply_ui_profile(ui_from_dict(data))
        except Exception as exc:
            self._set_status(f"⏰  Erro carregando '{rule.name}': {exc}")
            return

        # Se já tem macro rodando, pula (evita conflito)
        if getattr(self, "_macro_running", False):
            self._set_status(f"⏰  '{rule.name}' pulado — outro macro está rodando.")
            return
        self._start_macro()
        self._set_status(f"⏰  Agendamento '{rule.name}' disparado.")
        # Atualiza tree caso once tenha desativado a regra
        self._refresh_sched_tree()
