"""
ui/tabs/macro.py — Aba 🤖 Macro: editor de steps, execução, gravador,
variáveis, stop conditions, profiles (collect/apply script).

Requisitos do host (AutoClickPro):
  Attrs:   _driver, _macro_runner, _hotstrings, _ntfy, _tray, _recorder,
           _click_running, _type_running, _macro_running, _recorder_running,
           _macro_steps, _stop_conditions, _debug_event, _stopped_by_cond,
           _seq_positions, _target_hwnd, _lbl_hk, _hs_was_running_pre_rec,
           _var_panel_state, tab_macro, var_* (todas), _pill_mcr, _pill_rec,
           seq_tree, type_text
  Métodos: _make_scrollable, _section, _btn, _set_status, _set_pill,
           _start_pulse, _stop_pulse, _stop_clicking, _stop_typing,
           _rebind_hotkeys
"""
from __future__ import annotations

import copy
import tkinter as tk
from tkinter import ttk

from core.macro_schema import (
    MacroScript,
    StopCondition,
    UIProfile,
    macrostep_from_dict,
    macrostep_to_dict,
    stop_cond_from_dict,
    stop_cond_to_dict,
)
from core.recorder import HAS_PYNPUT
from ui.step_dialog import (
    ACTION_DESCRIPTIONS,
    ACTION_LABELS,
    StepDialog,
    StopConditionDialog,
    step_to_params_str,
)
from ui.theme import T
from ui.widgets import Tooltip


class MacroMixin:
    _UNDO_MAX = 50

    # ─────────────────────────────────────────────────────────────
    # UNDO
    # ─────────────────────────────────────────────────────────────
    def _macro_push_undo(self) -> None:
        """Salva snapshot de _macro_steps na pilha de undo."""
        stack = getattr(self, "_undo_stack", None)
        if stack is None:
            return
        stack.append(copy.deepcopy(self._macro_steps))
        if len(stack) > self._UNDO_MAX:
            stack.pop(0)

    def _macro_undo(self, event=None) -> str:
        """Ctrl+Z: restaura último snapshot."""
        stack = getattr(self, "_undo_stack", None)
        if not stack:
            self._set_status("↩  Nada para desfazer.", toast=True)
            return "break"
        self._macro_steps = stack.pop()
        self._macro_refresh_tree()
        n = len(self._macro_steps)
        self._set_status(
            f"↩  Undo — {n} step{'s' if n != 1 else ''} restaurado{'s' if n != 1 else ''}.",
            toast=True,
        )
        return "break"

    # ─────────────────────────────────────────────────────────────
    # ABA: MACRO
    # ─────────────────────────────────────────────────────────────
    def _build_macro_tab(self) -> None:
        p = self._make_scrollable(self.tab_macro)

        self._section(p, "Steps do Macro", "📋 ").pack(fill="x", padx=8, pady=(8, 2))
        tree_frame = tk.Frame(p, bg=T["bg"])
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 2))

        self.macro_tree = ttk.Treeview(
            tree_frame,
            columns=("n", "action", "params", "delay"),
            show="headings",
            height=10,
            selectmode="browse",
            style="Seq.Treeview",
        )
        for col, head, w, anchor in [
            ("n",      "#",           32,  "center"),
            ("action", "Ação",       148,  "w"),
            ("params", "Parâmetros", 258,  "w"),
            ("delay",  "Delay (ms)",  90,  "center"),
        ]:
            self.macro_tree.heading(col, text=head)
            self.macro_tree.column(col, width=w, anchor=anchor, minwidth=w)

        macro_vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                                   command=self.macro_tree.yview)
        self.macro_tree.configure(yscrollcommand=macro_vsb.set)
        self.macro_tree.pack(side="left", fill="both", expand=True)
        macro_vsb.pack(side="right", fill="y")
        self.macro_tree.bind("<Double-1>", lambda e: self._macro_edit_step())
        self.bind("<Control-z>", self._macro_undo)

        self._macro_empty_lbl = tk.Label(
            tree_frame,
            text="📋  Sem steps.\nClique  + Adicionar  para começar.",
            bg=T["bg"], fg=T["subtext"],
            font=("Segoe UI", 10), justify="center",
        )
        self._macro_empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        # Tooltip ao passar o mouse: explica o que o step faz + parâmetros atuais
        Tooltip(self.macro_tree, get_text=self._macro_step_tooltip_text,
                delay_ms=550, wraplength=380)

        step_btns = tk.Frame(p, bg=T["bg"])
        step_btns.pack(fill="x", padx=8, pady=(2, 4))
        self._btn(step_btns, "+ Adicionar", self._macro_add_step,
                  bg=T["text"], fg=T["bg"], bold=True, padx=8).pack(side="left", padx=(0, 3))
        self._btn(step_btns, "✏ Editar", self._macro_edit_step,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=3)
        self._btn(step_btns, "− Remover", self._macro_remove_step,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=3)
        self._btn(step_btns, "⧉ Dup", self._macro_duplicate_step,
                  bg=T["card"], fg=T["text"], padx=6).pack(side="left", padx=3)
        self._btn(step_btns, "↑", self._macro_move_up,
                  bg=T["card"], fg=T["text"], padx=6).pack(side="left", padx=3)
        self._btn(step_btns, "↓", self._macro_move_down,
                  bg=T["card"], fg=T["text"], padx=6).pack(side="left", padx=3)
        self._btn(step_btns, "✕ Limpar", self._macro_clear,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="right")
        self.rec_btn = self._btn(step_btns, "● Gravar", self._macro_toggle_recording,
                                  bg=T["card"], fg=T["text"], bold=False, padx=8)
        self.rec_btn.pack(side="right", padx=6)
        if not HAS_PYNPUT:
            self.rec_btn.config(state="disabled")

        rec_opts = tk.Frame(p, bg=T["bg"])
        rec_opts.pack(fill="x", padx=8, pady=(0, 2))
        tk.Checkbutton(rec_opts, text="Capturar teclado durante gravação",
                       variable=self.var_capture_keyboard,
                       bg=T["bg"], fg=T["subtext"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 9)).pack(side="left", padx=4)
        if not HAS_PYNPUT:
            tk.Label(rec_opts, text="(instale pynput para gravar)",
                     bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8)).pack(side="left")

        self._section(p, "Execução", "▶ ").pack(fill="x", padx=8, pady=(4, 2))
        rf = tk.Frame(p, bg=T["bg"])
        rf.pack(fill="x", padx=14, pady=(2, 4))
        tk.Radiobutton(rf, text="∞ Infinito", variable=self.var_macro_rep_mode, value="infinite",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Radiobutton(rf, text="Qtd:", variable=self.var_macro_rep_mode, value="count",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left", padx=(10, 2))
        tk.Entry(rf, textvariable=self.var_macro_rep_count, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")
        tk.Label(rf, text="  Delay entre loops (ms, mín 1):", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        tk.Spinbox(rf, textvariable=self.var_macro_loop_delay, from_=1, to=600000,
                   width=6, bg=T["card"], fg=T["text"], insertbackground=T["text"],
                   font=("Consolas", 11), justify="center",
                   relief="flat", bd=4).pack(side="left")
        tk.Label(rf, text="  Vel:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 2))
        for lbl, val in [("½×","0.5"), ("1×","1"), ("2×","2"), ("4×","4")]:
            tk.Radiobutton(rf, text=lbl, variable=self.var_macro_speed, value=val,
                           bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                           activebackground=T["bg"],
                           font=("Segoe UI", 9)).pack(side="left", padx=1)

        dbg_row = tk.Frame(p, bg=T["bg"]); dbg_row.pack(fill="x", padx=14, pady=(0, 4))
        tk.Checkbutton(dbg_row, text="🔍 Step-by-step (pausa após cada ação)",
                       variable=self.var_macro_debug,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 9)).pack(side="left")
        self.debug_next_btn = self._btn(dbg_row, "⏭ Próximo Step", self._debug_next_step,
                                        bg=T["card"], fg=T["subtext"], padx=6)
        self.debug_next_btn.pack(side="left", padx=(10, 0))
        self.debug_next_btn.config(state="disabled")

        notify_row = tk.Frame(p, bg=T["bg"]); notify_row.pack(fill="x", padx=14, pady=(0, 4))
        tk.Checkbutton(notify_row, text="🔔 Notificar ao terminar (bandeja)",
                       variable=self.var_macro_notify_done,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 9)).pack(side="left")

        # Painel de variáveis (atualizado em tempo real durante execução)
        var_section = tk.Frame(p, bg=T["bg"])
        var_section.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(var_section, text="🔢 Variáveis", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(var_section, text="(atualizado durante execução)",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(side="left", padx=6)
        clear_var_btn = self._btn(var_section, "✕ Limpar", self._clear_var_panel,
                                  bg=T["card"], fg=T["text"], padx=5, pady=1)
        clear_var_btn.pack(side="right")
        self.var_panel = tk.Listbox(p, height=3, bg=T["card"], fg=T["text"],
                                     font=("Consolas", 9), relief="flat",
                                     selectbackground=T["card_h"],
                                     selectforeground=T["text"],
                                     highlightthickness=0, bd=0)
        self.var_panel.pack(fill="x", padx=8, pady=(0, 4))
        self._var_panel_state: dict[str, str] = {}

        # Painel de Stop Conditions
        sc_section = tk.Frame(p, bg=T["bg"])
        sc_section.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(sc_section, text="🛑 Condições de Parada", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(sc_section, text="(checadas antes de cada step)",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(side="left", padx=6)

        sc_btns = tk.Frame(p, bg=T["bg"])
        sc_btns.pack(fill="x", padx=8, pady=(0, 2))
        self._btn(sc_btns, "+ Adicionar", self._sc_add,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=(0, 3))
        self._btn(sc_btns, "✏ Editar", self._sc_edit,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=3)
        self._btn(sc_btns, "− Remover", self._sc_remove,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=3)
        self._btn(sc_btns, "✕ Limpar", self._sc_clear,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="right")

        self.sc_panel = tk.Listbox(p, height=3, bg=T["card"], fg=T["text"],
                                    font=("Consolas", 9), relief="flat",
                                    selectbackground=T["card_h"],
                                    selectforeground=T["text"],
                                    highlightthickness=0, bd=0)
        self.sc_panel.pack(fill="x", padx=8, pady=(0, 4))
        self.sc_panel.bind("<Double-1>", lambda e: self._sc_toggle_enabled())
        self._refresh_sc_panel()

        exec_row = tk.Frame(p, bg=T["bg"])
        exec_row.pack(fill="x", padx=8, pady=(6, 10))
        self.macro_btn_var = tk.StringVar(value="▶  EXECUTAR MACRO   F9")
        self.macro_btn = tk.Button(exec_row, textvariable=self.macro_btn_var,
                                   command=self.toggle_macro,
                                   bg=T["accent"], fg="#ffffff",
                                   font=("Segoe UI", 11, "bold"),
                                   relief="flat", pady=13, cursor="hand2",
                                   activeforeground="#ffffff",
                                   activebackground=T["accent_h"],
                                   bd=0, highlightthickness=0)
        self.macro_btn.pack(side="left", fill="x", expand=True)
        self.macro_btn.bind("<Enter>", lambda e: self._btn_anim_hover(
            self.macro_btn, T["red_h"] if self._macro_running else T["accent_h"]))
        self.macro_btn.bind("<Leave>", lambda e: self._btn_anim_hover(
            self.macro_btn, T["red"] if self._macro_running else T["accent"]))
        Tooltip(self.macro_btn,
                get_text=lambda e: f"Atalho: {self.var_hk_macro.get().upper()}  •  "
                                   "Configurável em ⚙ Configurações",
                delay_ms=700)
        self.pause_btn = self._btn(exec_row, "⏸  Pausar", self._toggle_pause,
                                    bg=T["card"], fg=T["text"],
                                    font_size=10, bold=True, padx=14, pady=11)
        self.pause_btn.pack(side="left", padx=(6, 0))
        Tooltip(self.pause_btn,
                get_text=lambda e: f"Atalho: {self.var_hk_pause.get().upper()}  •  "
                                   "Pausa/retoma o macro em execução",
                delay_ms=700)

    # ─────────────────────────────────────────────────────────────
    # PROFILES — coleta / aplica
    # ─────────────────────────────────────────────────────────────
    def _collect_script(self) -> MacroScript:
        """Coleta estado atual da UI em um MacroScript (automação)."""
        return MacroScript(
            mouse_button=self.var_mouse_btn.get(),
            click_type=self.var_click_type.get(),
            burst=self.var_burst.get(),
            interval_h=self.var_interval_h.get(),
            interval_m=self.var_interval_m.get(),
            interval_s=self.var_interval_s.get(),
            interval_ms=self.var_interval_ms.get(),
            pos_mode=self.var_pos_mode.get(),
            pos_x=self.var_pos_x.get(),
            pos_y=self.var_pos_y.get(),
            seq_positions=list(self._seq_positions),
            rep_mode=self.var_rep_mode.get(),
            rep_count=self.var_rep_count.get(),
            humanize=self.var_humanize.get(),
            humanize_pct=self.var_humanize_pct.get(),
            jitter=self.var_jitter.get(),
            jitter_px=self.var_jitter_px.get(),
            overlay=self.var_overlay.get(),
            type_text=self.type_text.get("1.0", "end-1c"),
            type_interval=self.var_type_interval.get(),
            type_rep_mode=self.var_type_rep_mode.get(),
            type_rep_count=self.var_type_rep_count.get(),
            type_delay=self.var_type_delay.get(),
            type_paste=self.var_type_paste.get(),
            type_enter=self.var_type_enter.get(),
            type_interval_max=self.var_type_interval_max.get(),
            macro_speed=self.var_macro_speed.get(),
            macro_steps=[macrostep_to_dict(s) for s in self._macro_steps],
            stop_conditions=[stop_cond_to_dict(sc) for sc in self._stop_conditions],
            macro_notify_done=self.var_macro_notify_done.get(),
        )

    def _collect_ui_profile(self) -> UIProfile:
        """Coleta preferências de UI (hotkeys, som)."""
        return UIProfile(
            hk_clk=self.var_hk_clk.get(),
            hk_key=self.var_hk_key.get(),
            hk_macro=self.var_hk_macro.get(),
            hk_rec=self.var_hk_rec.get(),
            hk_stop=self.var_hk_stop.get(),
            hk_pause=self.var_hk_pause.get(),
            sound=self.var_sound.get(),
        )

    def _apply_script(self, script: MacroScript) -> None:
        """Aplica um MacroScript na UI."""
        def s(var: tk.Variable, val) -> None:
            var.set(val)

        s(self.var_mouse_btn,      script.mouse_button)
        s(self.var_click_type,     script.click_type)
        s(self.var_burst,          script.burst)
        s(self.var_interval_h,     script.interval_h)
        s(self.var_interval_m,     script.interval_m)
        s(self.var_interval_s,     script.interval_s)
        s(self.var_interval_ms,    script.interval_ms)
        s(self.var_pos_mode,       script.pos_mode)
        s(self.var_pos_x,          script.pos_x)
        s(self.var_pos_y,          script.pos_y)
        s(self.var_rep_mode,       script.rep_mode)
        s(self.var_rep_count,      script.rep_count)
        self.var_humanize.set(bool(script.humanize))
        s(self.var_humanize_pct,   script.humanize_pct)
        self.var_jitter.set(bool(script.jitter))
        s(self.var_jitter_px,      script.jitter_px)
        self.var_overlay.set(bool(script.overlay))
        self.type_text.delete("1.0", "end")
        self.type_text.insert("1.0", script.type_text)
        s(self.var_type_interval,  script.type_interval)
        s(self.var_type_rep_mode,  script.type_rep_mode)
        s(self.var_type_rep_count, script.type_rep_count)
        s(self.var_type_delay,     script.type_delay)
        self.var_type_paste.set(bool(getattr(script, "type_paste", True)))
        self.var_type_enter.set(bool(getattr(script, "type_enter", False)))
        self.var_type_interval_max.set(getattr(script, "type_interval_max", ""))
        self.var_macro_speed.set(getattr(script, "macro_speed", "1"))
        self.var_macro_notify_done.set(bool(getattr(script, "macro_notify_done", False)))

        # Restaurar seq_positions no treeview
        self._seq_positions.clear()
        for item in self.seq_tree.get_children():
            self.seq_tree.delete(item)
        for pos in script.seq_positions:
            if isinstance(pos, dict):
                self._seq_positions.append(pos)
                self.seq_tree.insert("", "end",
                    values=(pos.get("x", 0), pos.get("y", 0), pos.get("delay_ms", 0)))

        # Restaurar macro steps
        self._macro_steps.clear()
        for step_dict in script.macro_steps:
            if isinstance(step_dict, dict):
                try:
                    self._macro_steps.append(macrostep_from_dict(step_dict))
                except Exception:
                    pass
        self._macro_refresh_tree()

        # Restaurar stop conditions
        self._stop_conditions.clear()
        for sc_dict in getattr(script, "stop_conditions", []) or []:
            if isinstance(sc_dict, dict):
                try:
                    self._stop_conditions.append(stop_cond_from_dict(sc_dict))
                except Exception:
                    pass
        try:
            self._refresh_sc_panel()
        except Exception:
            pass

    def _apply_ui_profile(self, ui: UIProfile) -> None:
        """Aplica um UIProfile na UI."""
        self.var_hk_clk.set(ui.hk_clk)
        self.var_hk_key.set(ui.hk_key)
        self.var_hk_macro.set(ui.hk_macro)
        self.var_hk_rec.set(ui.hk_rec)
        self.var_hk_stop.set(ui.hk_stop)
        self.var_hk_pause.set(getattr(ui, "hk_pause", "pause"))
        self.var_sound.set(bool(ui.sound))
        self._rebind_hotkeys()
        for key, var in [("clk", self.var_hk_clk), ("key", self.var_hk_key),
                         ("macro", self.var_hk_macro), ("rec", self.var_hk_rec),
                         ("stop", self.var_hk_stop), ("pause", self.var_hk_pause)]:
            if key in self._lbl_hk:
                self._lbl_hk[key].config(text=var.get().upper())

    # ─────────────────────────────────────────────────────────────
    # MACRO — toggle / start / stop
    # ─────────────────────────────────────────────────────────────
    def toggle_macro(self) -> None:
        # Conserta estado inconsistente: _macro_running=True mas runner já
        # morreu. Sem isso, F9 alternaria entre "stop" e "stop" sem nunca
        # iniciar (porque stop não faz nada num runner que já parou).
        runner = self._macro_runner.get_sequential_runner()
        if self._macro_running and not runner.is_running:
            self._macro_running = False
        if self._macro_running:
            self._stop_macro()
        else:
            self._start_macro()

    def _start_macro(self) -> None:
        if not self._macro_steps:
            self._set_status("⚠  Nenhum step no macro.")
            return
        if self._click_running:
            self._stop_clicking()
        if self._type_running:
            self._stop_typing()

        repeat_count: int | None = None
        if self.var_macro_rep_mode.get() == "count":
            try:
                repeat_count = max(1, int(self.var_macro_rep_count.get() or 1))
            except ValueError:
                repeat_count = 1
        try:
            # Min 1ms: delay 0 satura input queue e trava Roblox e outros jogos
            loop_delay = max(1, int(self.var_macro_loop_delay.get() or 1))
        except ValueError:
            loop_delay = 1

        try:
            speed = float(self.var_macro_speed.get())
        except (ValueError, AttributeError):
            speed = 1.0

        if self.var_macro_debug.get():
            import threading
            self._debug_event = threading.Event()
        else:
            self._debug_event = None

        # Limpa painel de variáveis ao iniciar nova execução
        self._clear_var_panel()
        # Reset do flag de notify por stop_condition (nova execução = clean state)
        self._stopped_by_cond = False

        runner = self._macro_runner.get_sequential_runner()
        runner.start(
            # deepcopy: se o usuário editar steps ou stop conds durante a execução
            # (raro mas possível), o runner não vê estado parcial — trabalha
            # numa snapshot do momento do start.
            steps=copy.deepcopy(self._macro_steps),
            repeat_count=repeat_count,
            loop_delay_ms=loop_delay,
            on_step=lambda i: self.after(0, lambda idx=i: self._on_macro_step(idx)),
            on_stop=lambda: self.after(0, self._stop_macro),
            target_hwnd=self._target_hwnd if self.var_target_window.get() else 0,
            speed=speed,
            step_event=self._debug_event,
            on_variable_change=lambda n, v: self.after(
                0, lambda name=n, val=v: self._on_variable_change(name, val)
            ),
            stop_conditions=copy.deepcopy(self._stop_conditions),
            on_stop_condition=lambda label: self.after(
                0, lambda l=label: self._on_macro_stop_condition(l)
            ),
        )
        self._macro_running = True
        self.macro_btn.config(bg=T["red"], fg="#ffffff")
        self.macro_btn_var.set("⏹  STOP MACRO   F9")
        self._start_pulse(self.macro_btn)
        self._set_pill(self._pill_mcr, True, T["green"])
        self._run_indicator_start()
        self._set_status("▶  macro executando...")
        # Notifica monitores de evento (ntfy)
        try: self._ntfy.fire_event("macro_started")
        except Exception: pass

    def _on_macro_stop_condition(self, label: str) -> None:
        # Marca pra evitar notify duplicado: _stop_macro será chamado em
        # seguida (via on_stop callback) e pularia o notify se já houve aqui.
        self._stopped_by_cond = True
        self._set_status(f"🛑  Macro parado: {label}")
        self._notify_macro_done(f"Parado: {label}")
        # Notifica monitores ntfy de evento (com label da condition)
        try: self._ntfy.fire_event("macro_stopped_by_cond", label=label)
        except Exception: pass

    def _notify_macro_done(self, msg: str = "Macro finalizado.") -> None:
        """Mostra notificação na bandeja se o usuário marcou o checkbox."""
        if not self.var_macro_notify_done.get():
            return
        if not self._tray:
            return
        try:
            self._tray.notify(msg, "AutoClick Pro")
        except Exception:
            pass

    def _toggle_pause(self) -> None:
        """Pausa/retoma o macro. No-op se nenhum macro está rodando."""
        if not self._macro_running:
            return
        runner = self._macro_runner.get_sequential_runner()
        if runner.is_paused:
            runner.resume()
            self.pause_btn.config(text="⏸  Pausar")
            self._set_status("▶  macro retomado.")
        else:
            runner.pause()
            self.pause_btn.config(text="▶  Retomar")
            self._set_status("⏸  macro pausado.")

    def _stop_macro(self) -> None:
        self._macro_runner.get_sequential_runner().stop()
        self._macro_running = False
        self._debug_event = None
        try:
            self.debug_next_btn.config(state="disabled")
        except Exception:
            pass
        try:
            self.pause_btn.config(text="⏸  Pausar")
        except Exception:
            pass
        self._stop_pulse(self.macro_btn)
        self.macro_btn.config(bg=T["accent"], fg="#ffffff")
        self.macro_btn_var.set("▶  EXECUTAR MACRO   F9")
        self._set_pill(self._pill_mcr, False)
        if not self._click_running and not self._type_running:
            self._run_indicator_stop()
        # Se _on_macro_stop_condition já notificou (com label específico),
        # pula a notify genérica aqui pra não duplicar.
        if getattr(self, "_stopped_by_cond", False):
            self._set_status("⏹  macro parado.")
            self._stopped_by_cond = False
        else:
            self._set_status("⏹  macro parado.")
            self._notify_macro_done()
            # Notifica monitores ntfy de evento (apenas se NÃO foi por condition,
            # pra evitar duas notifs no celular por uma só execução)
            try: self._ntfy.fire_event("macro_stopped")
            except Exception: pass

    def _on_macro_step(self, idx: int) -> None:
        """Destaca o step atual no Treeview e (em debug mode) habilita o botão Próximo."""
        items = self.macro_tree.get_children()
        if 0 <= idx < len(items):
            self.macro_tree.selection_set(items[idx])
            self.macro_tree.see(items[idx])
        if self._debug_event is not None and self._macro_running:
            total = len(self._macro_steps)
            self._set_status(f"⏸  Step {idx + 1}/{total} — clique ⏭ para continuar")
            try:
                self.debug_next_btn.config(state="normal")
            except Exception:
                pass

    def _macro_step_tooltip_text(self, event) -> str | None:
        """Retorna texto do tooltip para a linha sob o cursor (ou None)."""
        try:
            item = self.macro_tree.identify_row(event.y)
        except Exception:
            return None
        if not item:
            return None
        try:
            idx = self.macro_tree.index(item)
        except Exception:
            return None
        if not (0 <= idx < len(self._macro_steps)):
            return None
        step = self._macro_steps[idx]
        desc = ACTION_DESCRIPTIONS.get(step.action, "")
        params = step_to_params_str(step)
        if desc and params:
            return f"{desc}\n\nParâmetros: {params}"
        return desc or params or None

    # ─────────────────────────────────────────────────────────────
    # MACRO — edição de steps
    # ─────────────────────────────────────────────────────────────
    def _macro_add_step(self) -> None:
        dlg = StepDialog(self, T, driver=self._driver)
        self.wait_window(dlg)
        if dlg.result:
            self._macro_push_undo()
            self._macro_steps.append(dlg.result)
            self._macro_refresh_tree()

    def _macro_edit_step(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if idx < 0 or idx >= len(self._macro_steps):
            return
        dlg = StepDialog(self, T, driver=self._driver, step=self._macro_steps[idx])
        self.wait_window(dlg)
        if dlg.result:
            self._macro_push_undo()
            self._macro_steps[idx] = dlg.result
            self._macro_refresh_tree()
            items = self.macro_tree.get_children()
            if 0 <= idx < len(items):
                self.macro_tree.selection_set(items[idx])

    def _macro_remove_step(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if 0 <= idx < len(self._macro_steps):
            self._macro_push_undo()
            self._macro_steps.pop(idx)
            self._macro_refresh_tree()

    def _macro_move_up(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if idx > 0:
            self._macro_push_undo()
            self._macro_steps[idx], self._macro_steps[idx - 1] = \
                self._macro_steps[idx - 1], self._macro_steps[idx]
            self._macro_refresh_tree()
            items = self.macro_tree.get_children()
            self.macro_tree.selection_set(items[idx - 1])

    def _macro_move_down(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if idx < len(self._macro_steps) - 1:
            self._macro_push_undo()
            self._macro_steps[idx], self._macro_steps[idx + 1] = \
                self._macro_steps[idx + 1], self._macro_steps[idx]
            self._macro_refresh_tree()
            items = self.macro_tree.get_children()
            self.macro_tree.selection_set(items[idx + 1])

    def _macro_duplicate_step(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if 0 <= idx < len(self._macro_steps):
            self._macro_push_undo()
            self._macro_steps.insert(idx + 1, copy.deepcopy(self._macro_steps[idx]))
            self._macro_refresh_tree()
            items = self.macro_tree.get_children()
            if idx + 1 < len(items):
                self.macro_tree.selection_set(items[idx + 1])

    def _debug_next_step(self) -> None:
        if self._debug_event is not None:
            try:
                self.debug_next_btn.config(state="disabled")
            except Exception:
                pass
            self._debug_event.set()

    def _on_variable_change(self, name: str, value: object) -> None:
        """Callback do SequentialRunner — chamado quando uma variável muda."""
        s = f"{name} = {value!r}"
        prev = self._var_panel_state.get(name)
        self._var_panel_state[name] = s
        try:
            if prev is None:
                self.var_panel.insert("end", s)
            else:
                # Atualizar linha existente
                items = list(self.var_panel.get(0, "end"))
                for i, item in enumerate(items):
                    if item.split(" = ", 1)[0] == name:
                        self.var_panel.delete(i)
                        self.var_panel.insert(i, s)
                        break
        except Exception:
            pass

    def _clear_var_panel(self) -> None:
        self._var_panel_state.clear()
        try:
            self.var_panel.delete(0, "end")
        except Exception:
            pass

    # ── Stop Conditions ──────────────────────────────────────────
    def _sc_format(self, sc: StopCondition) -> str:
        prefix = "[✓]" if sc.enabled else "[ ]"
        label = sc.label or "(sem nome)"
        if sc.type == "image":
            has = "✓ tpl" if sc.image_data else "✗ tpl"
            extra = f"image ({has}, conf={int(sc.image_threshold*100)}%)"
        elif sc.type == "pixel":
            rgb = f"RGB{tuple(sc.color_rgb)}" if sc.color_rgb else "RGB(?)"
            extra = f"pixel ({sc.x},{sc.y}) {rgb} tol={sc.color_tolerance}"
        elif sc.type == "var":
            extra = f"var {{{sc.var_name}}} {sc.var_op} {sc.var_value!r}"
        else:
            extra = sc.type
        return f"{prefix} {label}  —  {extra}"

    def _refresh_sc_panel(self) -> None:
        try:
            self.sc_panel.delete(0, "end")
            for sc in self._stop_conditions:
                self.sc_panel.insert("end", self._sc_format(sc))
        except Exception:
            pass

    def _sc_add(self) -> None:
        dlg = StopConditionDialog(self, T, driver=self._driver)
        self.wait_window(dlg)
        if dlg.result:
            self._stop_conditions.append(dlg.result)
            self._refresh_sc_panel()

    def _sc_edit(self) -> None:
        sel = self.sc_panel.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._stop_conditions):
            dlg = StopConditionDialog(self, T, driver=self._driver,
                                       sc=self._stop_conditions[idx])
            self.wait_window(dlg)
            if dlg.result:
                self._stop_conditions[idx] = dlg.result
                self._refresh_sc_panel()
                self.sc_panel.selection_set(idx)

    def _sc_remove(self) -> None:
        sel = self.sc_panel.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._stop_conditions):
            self._stop_conditions.pop(idx)
            self._refresh_sc_panel()

    def _sc_clear(self) -> None:
        self._stop_conditions.clear()
        self._refresh_sc_panel()

    def _sc_toggle_enabled(self) -> None:
        sel = self.sc_panel.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._stop_conditions):
            self._stop_conditions[idx].enabled = not self._stop_conditions[idx].enabled
            self._refresh_sc_panel()
            self.sc_panel.selection_set(idx)

    def _macro_clear(self) -> None:
        if self._macro_steps:
            self._macro_push_undo()
        self._macro_steps.clear()
        self._macro_refresh_tree()

    def _macro_refresh_tree(self) -> None:
        for item in self.macro_tree.get_children():
            self.macro_tree.delete(item)
        if hasattr(self, "_macro_empty_lbl"):
            if self._macro_steps:
                self._macro_empty_lbl.place_forget()
            else:
                self._macro_empty_lbl.place(relx=0.5, rely=0.5, anchor="center")
        depth = 0
        for i, step in enumerate(self._macro_steps):
            # endif sai do bloco ANTES de exibir (volta a ficar alinhado com o if)
            if step.action == "endif" and depth > 0:
                depth -= 1
            indent = "│  " * depth
            # else fica meio dentro do bloco mas alinhado com o if, então usa
            # indent reduzido em 1 nível (mas sem mudar depth permanente)
            label = ACTION_LABELS.get(step.action, step.action)
            if step.action == "else" and depth > 0:
                action_label = ("│  " * (depth - 1)) + label
            else:
                action_label = indent + label
            params = step_to_params_str(step)
            if step.rel_x is not None and step.rel_y is not None:
                params = f"{params}  [{step.rel_x*100:.0f}%, {step.rel_y*100:.0f}%]"
            self.macro_tree.insert("", "end", values=(
                i + 1,
                action_label,
                params,
                step.delay_ms,
            ))
            # if entra em bloco DEPOIS de exibir (próximos ficam indentados)
            if step.action == "if":
                depth += 1

    # ─────────────────────────────────────────────────────────────
    # MACRO — gravador
    # ─────────────────────────────────────────────────────────────
    def _macro_toggle_recording(self) -> None:
        if self._recorder_running:
            self._macro_stop_recording()
        else:
            self._macro_start_recording()

    def _macro_start_recording(self) -> None:
        if not HAS_PYNPUT:
            self._set_status("⚠  pynput não instalado. Execute install_deps.bat.")
            return
        if self._macro_running:
            self._stop_macro()

        # Countdown 3s antes de iniciar
        self._set_status("⏳  Gravando em 3...")
        self.rec_btn.config(state="disabled")

        def _countdown(n: int) -> None:
            if n > 0:
                self._set_status(f"⏳  Gravando em {n}...")
                self.after(1000, lambda: _countdown(n - 1))
            else:
                self._do_start_recording()

        self.after(0, lambda: _countdown(3))

    def _do_start_recording(self) -> None:
        # Pausa hotstrings durante recording: sem isso, qualquer trigger
        # digitado seria expandido E o Ctrl+V resultante seria gravado, virando
        # um macro estranho. Restaura no _macro_stop_recording.
        self._hs_was_running_pre_rec = self._hotstrings.is_running
        if self._hs_was_running_pre_rec:
            self._hotstrings.stop()

        stop_hotkey = self.var_hk_stop.get()
        ok = self._recorder.start(
            capture_keyboard=self.var_capture_keyboard.get(),
            stop_key=stop_hotkey,
        )
        if not ok:
            self._set_status("⚠  Falha ao iniciar gravação.")
            self.rec_btn.config(state="normal")
            # Restaura hotstrings se não conseguiu gravar
            if self._hs_was_running_pre_rec:
                self._hotstrings.start()
            return
        self._recorder_running = True
        self.rec_btn.config(text="⏹ Parar Gravação", bg=T["red"], fg="#ffffff", state="normal")
        self._set_pill(self._pill_rec, True, T["red"])
        self._set_status(f"⏺  gravando... (pressione {self.var_hk_rec.get().upper()} ou clique para parar)")

    def _macro_stop_recording(self) -> None:
        steps = self._recorder.stop()
        self._recorder_running = False
        # Retoma hotstrings se foram pausadas pelo recording
        if getattr(self, "_hs_was_running_pre_rec", False):
            self._hotstrings.start()
            self._hs_was_running_pre_rec = False
        self.rec_btn.config(text="● Gravar", bg=T["card"], fg=T["text"])
        self._set_pill(self._pill_rec, False)
        if steps:
            # Converter coordenadas para relativas quando janela-alvo está definida
            if self._target_hwnd:
                rect = self._driver.get_window_rect(self._target_hwnd)
                if rect:
                    left, top, w, h = rect
                    for step in steps:
                        if step.x is not None and step.y is not None and w > 0 and h > 0:
                            step.rel_x = round((step.x - left) / w, 4)
                            step.rel_y = round((step.y - top)  / h, 4)
            self._macro_steps.extend(steps)
            self._macro_refresh_tree()
            self._set_status(f"✅  Gravação concluída: {len(steps)} step(s) adicionados.")
        else:
            self._set_status("⚠  Nenhum evento gravado.")
