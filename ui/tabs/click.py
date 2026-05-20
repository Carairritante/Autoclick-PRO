"""
ui/tabs/click.py — Aba 🖱 AutoClick + lógica de clique, overlay, sequência,
janela alvo.

Requisitos do host (AutoClickPro):
  Attrs:   _driver, _macro_runner, _click_running, _type_running,
           _seq_positions, _overlay, _target_hwnd, _target_win_name,
           _session_clicks, _session_start, _recent_clicks, _stats_after_id,
           tab_click, var_mouse_btn, var_click_type, var_burst,
           var_interval_h/m/s/ms, var_pos_mode, var_pos_x, var_pos_y,
           var_humanize, var_humanize_pct, var_jitter, var_jitter_px,
           var_overlay, var_simultaneous, var_target_window, var_rep_mode,
           var_rep_count, var_sound, _pill_clk, lbl_cps, lbl_total, lbl_stats
  Métodos: _make_scrollable, _section, _btn, _set_status, _set_pill,
           _start_pulse, _stop_pulse, _play_tick, _fmt_time, _stop_typing
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk

from ui.theme import T
from ui.widgets import Tooltip


class ClickMixin:
    # ─────────────────────────────────────────────────────────────
    # ABA: AUTOCLICKER
    # ─────────────────────────────────────────────────────────────
    def _build_click_tab(self) -> None:
        p = self._make_scrollable(self.tab_click)

        # Speed presets
        self._section(p, "Presets de Velocidade", "⚡ ").pack(fill="x", padx=8, pady=(8, 2))
        prow = tk.Frame(p, bg=T["bg"])
        prow.pack(fill="x", padx=10, pady=(4, 6))
        for label, ms in [("🐢 Lento", 500),
                          ("▶ Normal", 100),
                          ("⚡ Rápido", 50),
                          ("🚀 Turbo", 1)]:
            btn = self._btn(prow, label, lambda m=ms: self._apply_preset(m),
                            bg=T["card"], fg=T["text"], font_size=9, bold=True,
                            padx=6, pady=6)
            btn.pack(side="left", padx=3, expand=True, fill="x")

        # Mouse button
        self._section(p, "Botão do Mouse", "🖱 ").pack(fill="x", padx=8, pady=(2, 2))
        row = tk.Frame(p, bg=T["bg"]); row.pack(fill="x", padx=14, pady=(2, 4))
        for txt, val in [("Esquerdo", "left"), ("Direito", "right"), ("Meio", "middle")]:
            tk.Radiobutton(row, text=txt, variable=self.var_mouse_btn, value=val,
                           bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                           activebackground=T["bg"],
                           font=("Segoe UI", 10)).pack(side="left", padx=8)

        # Click type + burst
        self._section(p, "Tipo de Clique  •  Rajada", "👆 ").pack(fill="x", padx=8, pady=2)
        row2 = tk.Frame(p, bg=T["bg"]); row2.pack(fill="x", padx=14, pady=(2, 4))
        for txt, val in [("Simples", "single"), ("Duplo", "double")]:
            tk.Radiobutton(row2, text=txt, variable=self.var_click_type, value=val,
                           bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                           activebackground=T["bg"],
                           font=("Segoe UI", 10)).pack(side="left", padx=8)
        tk.Label(row2, text="  Rajada:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left", padx=(8, 2))
        tk.Entry(row2, textvariable=self.var_burst, width=3,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")
        tk.Label(row2, text=" /ciclo", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=2)

        # Interval
        self._section(p, "Intervalo entre Cliques", "⏱ ").pack(fill="x", padx=8, pady=2)
        frm = tk.Frame(p, bg=T["bg"]); frm.pack(fill="x", padx=14, pady=(2, 4))
        for lbl, var in [("Horas", self.var_interval_h),
                          ("Minutos", self.var_interval_m),
                          ("Segundos", self.var_interval_s),
                          ("Ms", self.var_interval_ms)]:
            tf = tk.Frame(frm, bg=T["bg"]); tf.pack(side="left", padx=4)
            tk.Label(tf, text=lbl, bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 8)).pack()
            tk.Entry(tf, textvariable=var, width=5, bg=T["card"], fg=T["text"],
                     insertbackground=T["text"], font=("Consolas", 12),
                     justify="center", relief="flat", bd=4).pack()

        # Humanization
        self._section(p, "Humanização (Variação de Intervalo)", "🎲 ").pack(fill="x", padx=8, pady=2)
        hrow = tk.Frame(p, bg=T["bg"]); hrow.pack(fill="x", padx=14, pady=(2, 4))
        tk.Checkbutton(hrow, text="Ativar variação aleatória  ±",
                       variable=self.var_humanize,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(hrow, textvariable=self.var_humanize_pct, width=4,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")
        tk.Label(hrow, text=" %", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")

        # Position
        self._section(p, "Posição na Tela", "📍 ").pack(fill="x", padx=8, pady=2)
        pf = tk.Frame(p, bg=T["bg"]); pf.pack(fill="x", padx=14, pady=(2, 2))

        tk.Radiobutton(pf, text="Posição atual do cursor",
                       variable=self.var_pos_mode, value="cursor",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=7, sticky="w", pady=1)

        tk.Radiobutton(pf, text="Posição fixa:",
                       variable=self.var_pos_mode, value="fixed",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=1)
        tk.Label(pf, text="X:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).grid(row=1, column=1, padx=(8, 2))
        tk.Entry(pf, textvariable=self.var_pos_x, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).grid(row=1, column=2, padx=2)
        tk.Label(pf, text="Y:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).grid(row=1, column=3, padx=(8, 2))
        tk.Entry(pf, textvariable=self.var_pos_y, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).grid(row=1, column=4, padx=2)
        self._btn(pf, "📍 Capturar", self._capture_pos,
                  bg=T["text"], fg=T["bg"], bold=True, padx=6).grid(row=1, column=5, padx=(8, 0))

        tk.Radiobutton(pf, text="Posições em quadro:",
                       variable=self.var_pos_mode, value="sequence",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).grid(row=2, column=0, columnspan=7, sticky="w", pady=1)

        tree_frame = tk.Frame(p, bg=T["bg"]); tree_frame.pack(fill="x", padx=28, pady=(0, 2))
        self.seq_tree = ttk.Treeview(tree_frame,
                                      columns=("x", "y", "delay"),
                                      show="headings", height=4,
                                      selectmode="browse", style="Seq.Treeview")
        for col, head, w in [("x", "X", 85), ("y", "Y", 85), ("delay", "Delay (ms)", 110)]:
            self.seq_tree.heading(col, text=head)
            self.seq_tree.column(col, width=w, anchor="center")
        seq_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.seq_tree.yview)
        self.seq_tree.configure(yscrollcommand=seq_vsb.set)
        self.seq_tree.pack(side="left", fill="x", expand=True)
        seq_vsb.pack(side="right", fill="y")
        # Duplo clique edita o delay_ms da posição selecionada
        self.seq_tree.bind("<Double-1>", lambda e: self._edit_seq_delay())

        seq_btns = tk.Frame(p, bg=T["bg"]); seq_btns.pack(fill="x", padx=28, pady=(2, 4))
        self._btn(seq_btns, "+ Adicionar (3s)", self._capture_seq_pos,
                  bg=T["text"], fg=T["bg"], bold=True, padx=8).pack(side="left", padx=(0, 4))
        self._btn(seq_btns, "− Remover", self._seq_remove,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=(0, 4))
        self._btn(seq_btns, "✕ Limpar", self._seq_clear,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left")

        sim_row = tk.Frame(p, bg=T["bg"]); sim_row.pack(fill="x", padx=28, pady=(0, 6))
        tk.Checkbutton(sim_row,
                       text="Clicar em todos os pontos ao mesmo tempo (sem mover o mouse)",
                       variable=self.var_simultaneous,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")

        # Jitter
        jrow = tk.Frame(p, bg=T["bg"]); jrow.pack(fill="x", padx=14, pady=(0, 4))
        tk.Checkbutton(jrow, text="Jitter de posição  ±",
                       variable=self.var_jitter,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(jrow, textvariable=self.var_jitter_px, width=4,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")
        tk.Label(jrow, text=" px  (só modo fixo)", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=2)

        # Overlay
        ov_row = tk.Frame(p, bg=T["bg"]); ov_row.pack(fill="x", padx=14, pady=(2, 4))
        tk.Checkbutton(ov_row, text="Mostrar ponto azul indicador na tela",
                       variable=self.var_overlay,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")

        # Janela alvo (background click)
        self._section(p, "Janela Alvo  (clicar em segundo plano)", "🎯 ").pack(fill="x", padx=8, pady=(6, 2))
        tw_row = tk.Frame(p, bg=T["bg"]); tw_row.pack(fill="x", padx=14, pady=(2, 2))
        tk.Checkbutton(tw_row, text="Ativar clique em janela específica",
                       variable=self.var_target_window,
                       command=self._on_target_window_toggle,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")

        tw_pick = tk.Frame(p, bg=T["bg"]); tw_pick.pack(fill="x", padx=14, pady=(0, 6))
        self._lbl_target_win = tk.Label(tw_pick, text="Nenhuma janela selecionada",
                                        bg=T["card"], fg=T["subtext"],
                                        font=("Segoe UI", 9), padx=8, pady=3,
                                        anchor="w", width=34)
        self._lbl_target_win.pack(side="left", padx=(0, 6))
        self._btn_pick_win = self._btn(tw_pick, "Selecionar janela", self._capture_target_window,
                                       bg=T["card"], fg=T["text"], bold=False, padx=8)
        self._btn_pick_win.pack(side="left")
        self._btn_clear_win = self._btn(tw_pick, "✕", self._clear_target_window,
                                        bg=T["card"], fg=T["text"], padx=6)
        self._btn_clear_win.pack(side="left", padx=(4, 0))

        # Repetitions
        self._section(p, "Repetições", "🔁 ").pack(fill="x", padx=8, pady=2)
        rf = tk.Frame(p, bg=T["bg"]); rf.pack(fill="x", padx=14, pady=(2, 4))
        tk.Radiobutton(rf, text="∞ Infinito", variable=self.var_rep_mode, value="infinite",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Radiobutton(rf, text="Qtd:", variable=self.var_rep_mode, value="count",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left", padx=(12, 2))
        tk.Entry(rf, textvariable=self.var_rep_count, width=7,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")

        # Start/Stop button — estilo invertido (branco/preto)
        self.click_btn_var = tk.StringVar(value="▶  START AUTOCLICK   F6")
        self.click_btn = tk.Button(p, textvariable=self.click_btn_var,
                                   command=self.toggle_clicking,
                                   bg=T["accent"], fg="#ffffff",
                                   font=("Segoe UI", 11, "bold"),
                                   relief="flat", pady=13, cursor="hand2",
                                   activeforeground="#ffffff",
                                   activebackground=T["accent_h"],
                                   bd=0, highlightthickness=0)
        self.click_btn.pack(fill="x", padx=8, pady=(10, 10))
        self.click_btn.bind("<Enter>", lambda e: self._btn_anim_hover(
            self.click_btn, T["red_h"] if self._click_running else T["accent_h"]))
        self.click_btn.bind("<Leave>", lambda e: self._btn_anim_hover(
            self.click_btn, T["red"] if self._click_running else T["accent"]))
        Tooltip(self.click_btn,
                get_text=lambda e: f"Atalho: {self.var_hk_clk.get().upper()}  •  "
                                   "Configurável em ⚙ Configurações",
                delay_ms=700)

    # ─────────────────────────────────────────────────────────────
    # CLICK — INTERVAL / PRESETS
    # ─────────────────────────────────────────────────────────────
    def _get_interval_ms(self) -> int:
        try:
            h  = int(self.var_interval_h.get()  or 0)
            m  = int(self.var_interval_m.get()  or 0)
            s  = int(self.var_interval_s.get()  or 0)
            ms = int(self.var_interval_ms.get() or 100)
            return max(1, h * 3_600_000 + m * 60_000 + s * 1_000 + ms)
        except ValueError:
            return 100

    def _apply_preset(self, ms: int) -> None:
        self.var_interval_h.set("0")
        self.var_interval_m.set("0")
        self.var_interval_s.set("0")
        self.var_interval_ms.set(str(ms))

    # ─────────────────────────────────────────────────────────────
    # CAPTURE POSITION
    # ─────────────────────────────────────────────────────────────
    def _capture_pos(self) -> None:
        self._set_status("⏳  Aguardando 3s... coloque o cursor na posição desejada!")
        self.var_pos_mode.set("fixed")
        def _do() -> None:
            time.sleep(3)
            x, y = self._driver.get_position()
            self.var_pos_x.set(str(x))
            self.var_pos_y.set(str(y))
            self.after(0, lambda: self._set_status(f"✅  Posição capturada: ({x}, {y})"))
        threading.Thread(target=_do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────
    # STATS LOOP
    # ─────────────────────────────────────────────────────────────
    def _start_stats(self) -> None:
        self._session_clicks = 0
        self._session_start  = time.monotonic()
        self._recent_clicks.clear()
        if self._stats_after_id:
            self.after_cancel(self._stats_after_id)
        self._stats_loop()

    def _stats_loop(self) -> None:
        if not self._click_running:
            self.lbl_cps.pack_forget()
            self.lbl_total.pack_forget()
            self.lbl_stats.config(text="")
            return
        now = time.monotonic()
        while self._recent_clicks and now - self._recent_clicks[0] > 1.0:
            self._recent_clicks.popleft()
        cps     = len(self._recent_clicks)
        elapsed = now - self._session_start if self._session_start else 0
        avg_cps = self._session_clicks / elapsed if elapsed > 0 else 0.0

        self.lbl_cps.config(text=f"{cps} CPS")
        self.lbl_total.config(text=f"{self._session_clicks}")
        self.lbl_cps.pack(side="right", padx=2)
        self.lbl_total.pack(side="right", padx=2)
        self.lbl_stats.config(
            text=f"⏱ {self._fmt_time(elapsed)}   ∑ {self._session_clicks}   ⌀ {avg_cps:.1f} CPS"
        )
        self._stats_after_id = self.after(250, self._stats_loop)

    # ─────────────────────────────────────────────────────────────
    # CLICK EVENT (chamado pelo ClickLoop de outra thread)
    # ─────────────────────────────────────────────────────────────
    def _on_click_event(self) -> None:
        self._session_clicks += 1
        self._recent_clicks.append(time.monotonic())

    # ─────────────────────────────────────────────────────────────
    # AUTO CLICKER
    # ─────────────────────────────────────────────────────────────
    def toggle_clicking(self) -> None:
        if self._click_running:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self) -> None:
        if self._type_running:
            self._stop_typing()

        try:
            burst = max(1, int(self.var_burst.get() or 1))
        except ValueError:
            burst = 1
        try:
            pos_x = int(self.var_pos_x.get() or 0)
            pos_y = int(self.var_pos_y.get() or 0)
        except ValueError:
            pos_x = pos_y = 0
        try:
            humanize_pct = float(self.var_humanize_pct.get() or 10)
        except ValueError:
            humanize_pct = 10.0
        try:
            jitter_px = int(self.var_jitter_px.get() or 5)
        except ValueError:
            jitter_px = 5
        try:
            rep_count = int(self.var_rep_count.get() or 1)
        except ValueError:
            rep_count = 1

        click_loop = self._macro_runner.get_click_loop()
        click_loop.configure(
            interval_ms=self._get_interval_ms(),
            button=self.var_mouse_btn.get(),
            double=(self.var_click_type.get() == "double"),
            burst=burst,
            pos_mode=self.var_pos_mode.get(),
            pos_x=pos_x,
            pos_y=pos_y,
            seq_positions=list(self._seq_positions),
            simultaneous=self.var_simultaneous.get(),
            target_hwnd=self._target_hwnd if self.var_target_window.get() else 0,
            humanize=self.var_humanize.get(),
            humanize_pct=humanize_pct,
            jitter=self.var_jitter.get(),
            jitter_px=jitter_px,
            rep_mode=self.var_rep_mode.get(),
            rep_count=rep_count,
            sound_enabled=self.var_sound.get(),
            on_click=lambda: self.after(0, self._on_click_event),
            # self.after é thread-safe — agenda overlay no thread da UI
            on_overlay_update=lambda x, y: self.after(0, lambda a=x, b=y: self._move_overlay(a, b)),
            on_stop=lambda: self.after(0, self._stop_clicking),
            on_play_sound=self._play_tick,
        )

        self._click_running = True
        self._start_stats()
        self.click_btn.config(bg=T["red"], fg="#ffffff")
        self.click_btn_var.set("⏹  STOP AUTOCLICK   F6")
        self._set_pill(self._pill_clk, True, T["green"])
        self._start_pulse(self.click_btn)
        self._run_indicator_start()
        self._set_status("▶  autoclicker rodando...")
        if self.var_overlay.get():
            self._overlay = self._create_overlay()
        click_loop.start()

    def _stop_clicking(self) -> None:
        self._macro_runner.get_click_loop().stop()
        self._click_running = False
        self._stop_pulse(self.click_btn)
        self.click_btn.config(bg=T["accent"], fg="#ffffff")
        self.click_btn_var.set("▶  START AUTOCLICK   F6")
        self._set_pill(self._pill_clk, False)
        if not self._type_running and not self._macro_running:
            self._run_indicator_stop()
        self._set_status(f"⏹  autoclicker parado.  ∑ {self._session_clicks} cliques.")
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

    # ─────────────────────────────────────────────────────────────
    # OVERLAY VISUAL  (make_clickthrough delegado ao driver)
    # ─────────────────────────────────────────────────────────────
    # Cor de chroma key: magenta puro impossível de aparecer em qualquer app
    _OVERLAY_CHROMA = "#fe01fe"

    def _create_overlay(self) -> tk.Toplevel | None:
        try:
            ov = tk.Toplevel(self)
            ov.overrideredirect(True)
            ov.attributes("-topmost", True)
            # transparentcolor torna essa cor "invisível" — apenas o oval aparece
            ov.wm_attributes("-transparentcolor", self._OVERLAY_CHROMA)
            ov.geometry("20x20+0+0")
            c = tk.Canvas(ov, width=20, height=20,
                          bg=self._OVERLAY_CHROMA, highlightthickness=0)
            c.pack()
            c.create_oval(2, 2, 18, 18, fill="#00aaff", outline="white", width=1)
            # update() (não update_idletasks) garante HWND válido antes de make_clickthrough
            ov.update()
            # windll delegado ao driver (core/driver.py: make_clickthrough)
            self._driver.make_clickthrough(ov.winfo_id())
            return ov
        except Exception:
            return None

    def _move_overlay(self, x: int, y: int) -> None:
        if self._overlay:
            try:
                self._overlay.geometry(f"20x20+{x - 10}+{y - 10}")
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # SEQUÊNCIA DE POSIÇÕES
    # ─────────────────────────────────────────────────────────────
    def _capture_seq_pos(self) -> None:
        self._set_status("⏳  Mova o cursor para a posição em 3s...")
        def _do() -> None:
            time.sleep(3)
            x, y = self._driver.get_position()
            entry = {"x": x, "y": y, "delay_ms": 0}
            self._seq_positions.append(entry)
            idx = len(self._seq_positions)
            self.after(0, lambda: self.seq_tree.insert("", "end", values=(x, y, 0)))
            self.after(0, lambda: self._set_status(f"✅  Posição {idx} capturada: ({x}, {y})"))
        threading.Thread(target=_do, daemon=True).start()

    def _seq_remove(self) -> None:
        sel = self.seq_tree.selection()
        if not sel:
            return
        idx = self.seq_tree.index(sel[0])
        self.seq_tree.delete(sel[0])
        if 0 <= idx < len(self._seq_positions):
            self._seq_positions.pop(idx)

    def _seq_clear(self) -> None:
        self._seq_positions.clear()
        for item in self.seq_tree.get_children():
            self.seq_tree.delete(item)

    # ─────────────────────────────────────────────────────────────
    # JANELA ALVO (clique em segundo plano)
    # ─────────────────────────────────────────────────────────────
    def _on_target_window_toggle(self) -> None:
        if not self.var_target_window.get():
            self._clear_target_window()

    def _capture_target_window(self) -> None:
        """Abre diálogo com lista de janelas abertas — escolha qual o autoclicker mira."""
        from ui.window_picker import list_visible_windows, pick_window
        if not list_visible_windows():
            self._set_status("⚠  Nenhuma janela encontrada.")
            return
        result = pick_window(
            self, T,
            title_text="Selecionar Janela Alvo",
            prompt="Escolha a janela onde o autoclicker vai clicar:",
        )
        if result is None:
            return  # usuário cancelou
        hwnd, title = result
        self._target_hwnd = hwnd
        self._target_win_name = title
        display = (title[:32] + "…") if len(title) > 32 else title
        self._lbl_target_win.config(text=display, fg=T["text"])
        self.var_target_window.set(True)
        self._set_status(f"🎯  Janela alvo: {title}")

    def _clear_target_window(self) -> None:
        self._target_hwnd = 0
        self._target_win_name = ""
        self._lbl_target_win.config(text="Nenhuma janela selecionada", fg=T["subtext"])
        self.var_target_window.set(False)

    # ─────────────────────────────────────────────────────────────
    # EDITAR DELAY DA SEQUÊNCIA
    # ─────────────────────────────────────────────────────────────
    def _edit_seq_delay(self) -> None:
        """Abre diálogo para editar delay_ms da posição selecionada na sequência."""
        sel = self.seq_tree.selection()
        if not sel:
            return
        idx = self.seq_tree.index(sel[0])
        if idx < 0 or idx >= len(self._seq_positions):
            return
        current = self._seq_positions[idx].get("delay_ms", 0)

        dlg = tk.Toplevel(self)
        dlg.title("Editar Delay")
        dlg.configure(bg=T["bg"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Delay antes deste clique (ms):",
                 bg=T["bg"], fg=T["text"], font=("Segoe UI", 10)).pack(padx=16, pady=(14, 4))
        var = tk.StringVar(value=str(current))
        entry = tk.Entry(dlg, textvariable=var, width=10,
                         bg=T["card"], fg=T["text"], insertbackground=T["text"],
                         font=("Consolas", 12), justify="center", relief="flat", bd=4)
        entry.pack(padx=16, pady=4)
        entry.select_range(0, "end")
        entry.focus_set()

        def _apply() -> None:
            try:
                ms = max(0, int(var.get() or 0))
            except ValueError:
                ms = 0
            self._seq_positions[idx]["delay_ms"] = ms
            self.seq_tree.set(sel[0], "delay", ms)
            dlg.destroy()

        entry.bind("<Return>", lambda e: _apply())
        self._btn(dlg, "✔ OK", _apply, bg=T["text"], fg=T["bg"], bold=True).pack(padx=16, pady=(8, 14))

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - dlg.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")
