"""
ui/scheduler_dialog.py — Modal pra criar/editar uma ScheduleRule.

Campos:
  - Nome (texto livre, opcional)
  - Frequência: daily | weekly | once
  - Horário (HH:MM) — daily/weekly
  - Dias da semana (checkbuttons) — weekly only
  - Data (YYYY-MM-DD) — once only
  - Destino: slot 1/2/3 ou arquivo .json
  - Ativado (checkbox)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from datetime import datetime

from core.scheduler import ScheduleRule
from ui.widgets import make_button


WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


class ScheduleRuleDialog(tk.Toplevel):
    """Modal pra criar/editar uma regra de agendamento."""

    def __init__(self, parent: tk.Tk, T: dict, rule: ScheduleRule | None = None) -> None:
        super().__init__(parent)
        self._T = T
        self.result: ScheduleRule | None = None

        self.title("Editar Agendamento" if rule else "Novo Agendamento")
        self.configure(bg=T["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Estado
        self._v_name   = tk.StringVar(value=rule.name if rule else "")
        self._v_freq   = tk.StringVar(value=rule.freq if rule else "daily")
        self._v_time   = tk.StringVar(value=rule.time if rule else "09:00")
        self._v_date   = tk.StringVar(
            value=rule.date if rule and rule.date else datetime.now().strftime("%Y-%m-%d"))
        self._v_kind   = tk.StringVar(value=rule.macro_kind if rule else "slot")
        self._v_target = tk.StringVar(value=rule.macro_target if rule else "1")
        self._v_enabled = tk.BooleanVar(value=rule.enabled if rule else True)
        # weekdays — 7 BooleanVars (default: seg-sex se nova regra)
        default_days = rule.weekdays if rule else [0, 1, 2, 3, 4]
        self._v_weekdays = [
            tk.BooleanVar(value=(i in default_days)) for i in range(7)
        ]

        self._build()
        self._refresh_freq_fields()
        self._refresh_target_fields()

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _build(self) -> None:
        T = self._T
        p = self

        # ── Nome ─────────────────────────────────────────────────
        nm = tk.Frame(p, bg=T["bg"])
        nm.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(nm, text="Nome:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(nm, textvariable=self._v_name, width=32, bg=T["card"],
                 fg=T["text"], insertbackground=T["text"], font=("Segoe UI", 11),
                 relief="flat", bd=4).pack(side="left", padx=8)

        # ── Frequência ───────────────────────────────────────────
        fr = tk.Frame(p, bg=T["bg"])
        fr.pack(fill="x", padx=16, pady=4)
        tk.Label(fr, text="Frequência:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 10)).pack(side="left")
        cb = ttk.Combobox(fr, textvariable=self._v_freq,
                           values=["daily", "weekly", "once"],
                           state="readonly", width=10, font=("Segoe UI", 10))
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_freq_fields())

        # ── Campos dinâmicos da frequência ──────────────────────
        self._freq_frame = tk.Frame(p, bg=T["bg"])
        self._freq_frame.pack(fill="x", padx=16, pady=4)

        # ── Destino (tipo + alvo) ────────────────────────────────
        tk.Label(p, text="Macro a executar:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        kf = tk.Frame(p, bg=T["bg"])
        kf.pack(fill="x", padx=16, pady=4)
        tk.Label(kf, text="Tipo:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        kcb = ttk.Combobox(kf, textvariable=self._v_kind,
                            values=["slot", "file"], state="readonly",
                            width=8, font=("Segoe UI", 10))
        kcb.pack(side="left", padx=8)
        kcb.bind("<<ComboboxSelected>>", lambda e: self._refresh_target_fields())

        self._target_frame = tk.Frame(p, bg=T["bg"])
        self._target_frame.pack(fill="x", padx=16, pady=4)

        # ── Ativado ──────────────────────────────────────────────
        en = tk.Frame(p, bg=T["bg"])
        en.pack(fill="x", padx=16, pady=(8, 4))
        tk.Checkbutton(en, text="Ativado", variable=self._v_enabled,
                       bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                       activebackground=T["bg"], font=("Segoe UI", 10)
                       ).pack(side="left")

        # ── Botões ───────────────────────────────────────────────
        btns = tk.Frame(p, bg=T["bg"])
        btns.pack(fill="x", padx=16, pady=(8, 14))
        make_button(btns, "✔ OK", self._ok, T["accent"], fg=T["bg"],
                    padx=10, pady=5).pack(side="left", padx=(0, 8))
        make_button(btns, "✕ Cancelar", self.destroy, T["card"], fg=T["text"],
                    padx=10, pady=5).pack(side="left")

    def _refresh_freq_fields(self) -> None:
        T = self._T
        f = self._freq_frame
        for w in f.winfo_children():
            w.destroy()
        freq = self._v_freq.get()

        # HH:MM sempre — daily/weekly/once todos precisam
        if freq in ("daily", "weekly", "once"):
            tk.Label(f, text="Horário (HH:MM):", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=3)
            tk.Entry(f, textvariable=self._v_time, width=8, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4
                     ).grid(row=0, column=1, sticky="w", padx=8)
            tk.Label(f, text="ex: 09:00, 14:30, 23:59",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=0, column=2, sticky="w", padx=4)

        if freq == "weekly":
            tk.Label(f, text="Dias da semana:", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=1, column=0, sticky="nw", pady=8)
            wd_frame = tk.Frame(f, bg=T["bg"])
            wd_frame.grid(row=1, column=1, columnspan=2, sticky="w", padx=8)
            for i, name in enumerate(WEEKDAY_NAMES):
                tk.Checkbutton(wd_frame, text=name, variable=self._v_weekdays[i],
                               bg=T["bg"], fg=T["text"],
                               selectcolor=T.get("sel", "#7a1a1a"),
                               activebackground=T["bg"], font=("Segoe UI", 9)
                               ).pack(side="left", padx=2)

        if freq == "once":
            tk.Label(f, text="Data (YYYY-MM-DD):", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=3)
            tk.Entry(f, textvariable=self._v_date, width=12, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4
                     ).grid(row=2, column=1, sticky="w", padx=8)
            tk.Label(f, text="ex: 2026-12-25",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=2, column=2, sticky="w", padx=4)

    def _refresh_target_fields(self) -> None:
        T = self._T
        f = self._target_frame
        for w in f.winfo_children():
            w.destroy()
        kind = self._v_kind.get()

        if kind == "slot":
            tk.Label(f, text="Slot:", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
            if self._v_target.get() not in ("1", "2", "3"):
                self._v_target.set("1")
            ttk.Combobox(f, textvariable=self._v_target, values=["1", "2", "3"],
                         state="readonly", width=6, font=("Consolas", 11)
                         ).grid(row=0, column=1, sticky="w", padx=8)
        else:
            tk.Label(f, text="Arquivo:", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
            tk.Entry(f, textvariable=self._v_target, width=36, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 10),
                     relief="flat", bd=4
                     ).grid(row=0, column=1, sticky="w", padx=8)
            make_button(f, "📂", self._pick_file, T["card"], fg=T["text"],
                        padx=6, pady=3).grid(row=0, column=2, padx=4)

    def _pick_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Escolher macro a agendar",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            self._v_target.set(path)

    def _ok(self) -> None:
        from tkinter import messagebox

        # Valida HH:MM
        try:
            hh, mm = self._v_time.get().split(":")
            hh, mm = int(hh), int(mm)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            messagebox.showerror("Horário inválido",
                                  "Use o formato HH:MM (ex: 09:00, 14:30).", parent=self)
            return

        freq = self._v_freq.get()
        if freq == "weekly":
            wd = [i for i, v in enumerate(self._v_weekdays) if v.get()]
            if not wd:
                messagebox.showerror("Sem dias selecionados",
                                      "Escolha pelo menos um dia da semana.", parent=self)
                return
        else:
            wd = [i for i, v in enumerate(self._v_weekdays) if v.get()]

        if freq == "once":
            try:
                datetime.strptime(self._v_date.get(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Data inválida",
                                      "Use o formato YYYY-MM-DD (ex: 2026-12-25).", parent=self)
                return

        target = self._v_target.get().strip()
        if not target:
            messagebox.showerror("Sem destino", "Defina slot ou arquivo.", parent=self)
            return

        self.result = ScheduleRule(
            name=self._v_name.get().strip(),
            enabled=bool(self._v_enabled.get()),
            freq=freq,
            time=f"{hh:02d}:{mm:02d}",
            weekdays=wd,
            date=self._v_date.get().strip() if freq == "once" else "",
            macro_kind=self._v_kind.get(),
            macro_target=target,
        )
        self.destroy()
