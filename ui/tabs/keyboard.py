"""
ui/tabs/keyboard.py — Aba ⌨ AutoKeyboard + lógica de digitação.

Requisitos do host (AutoClickPro):
  Attrs:   _macro_runner, _click_running, _type_running, tab_key,
           var_type_*, _pill_key
  Métodos: _make_scrollable, _section, _set_status, _set_pill,
           _start_pulse, _stop_pulse, _stop_clicking
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog

from ui.theme import T
from ui.widgets import Tooltip


class KeyboardMixin:
    # ─────────────────────────────────────────────────────────────
    # ABA: AUTOKEYBOARD
    # ─────────────────────────────────────────────────────────────
    def _build_keyboard_tab(self) -> None:
        p = self._make_scrollable(self.tab_key)

        self._section(p, "Texto / Teclas para Digitar", "✏ ").pack(fill="x", padx=8, pady=(10, 3))
        self.type_text = tk.Text(p, height=5, bg=T["card"], fg=T["text"],
                                  insertbackground=T["text"],
                                  font=("Consolas", 11), relief="flat",
                                  padx=8, pady=6, wrap="word")
        self.type_text.pack(fill="x", padx=8, pady=(0, 2))
        self.type_text.insert("1.0", "Olá Mundo!\nDigite aqui o texto que deseja repetir.")

        tbar = tk.Frame(p, bg=T["bg"]); tbar.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(tbar, text="Inserir token →", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 8), anchor="w"
                 ).pack(side="left", padx=(0, 6))
        tk.Button(tbar, text="📂 Carregar .txt",
                  command=self._load_text_from_file,
                  bg=T["card"], fg=T["text"],
                  font=("Segoe UI", 8), relief="flat", pady=2, padx=6,
                  cursor="hand2", activebackground=T["card_h"],
                  activeforeground=T["text"],
                  bd=0, highlightthickness=0).pack(side="right")

        # Token chips clicáveis (estilo Discord mention)
        chips_row = tk.Frame(p, bg=T["bg"]); chips_row.pack(fill="x", padx=10, pady=(0, 6))
        for tok in ["{ENTER}", "{TAB}", "{UP}", "{DOWN}", "{LEFT}", "{RIGHT}",
                    "{BACKSPACE}", "{F1}", "{F12}", "{ESCAPE}"]:
            tk.Button(chips_row, text=tok, command=lambda t=tok: self._insert_token(t),
                      bg=T["sel"], fg=T["accent2"],
                      font=("Consolas", 8, "bold"),
                      relief="flat", bd=0, padx=8, pady=2,
                      cursor="hand2",
                      activebackground=T["accent"], activeforeground="#ffffff",
                      highlightthickness=0
                      ).pack(side="left", padx=2, pady=1)

        # Modo Colar: Ctrl+V em vez de digitar caractere por caractere
        self._section(p, "Modo de Envio", "🚀 ").pack(fill="x", padx=8, pady=3)
        prow = tk.Frame(p, bg=T["bg"]); prow.pack(fill="x", padx=14, pady=(2, 2))
        tk.Checkbutton(prow,
                       text="Colar via Ctrl+V (recomendado p/ Discord, Notepad e apps lentos)",
                       variable=self.var_type_paste,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Label(p,
                 text="Tokens especiais ({ENTER}, {TAB}, etc.) continuam como tecla individual.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8), anchor="w"
                 ).pack(fill="x", padx=16, pady=(0, 4))
        prow2 = tk.Frame(p, bg=T["bg"]); prow2.pack(fill="x", padx=14, pady=(0, 6))
        tk.Checkbutton(prow2,
                       text="Pressionar Enter após cada repetição",
                       variable=self.var_type_enter,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")

        self._section(p, "Intervalo entre Caracteres (ms)", "⏱ ").pack(fill="x", padx=8, pady=3)
        tf = tk.Frame(p, bg=T["bg"]); tf.pack(fill="x", padx=14, pady=(2, 6))
        tk.Label(tf, text="Mín:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(tf, textvariable=self.var_type_interval, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 12), justify="center",
                 relief="flat", bd=4).pack(side="left", padx=(4, 0))
        tk.Label(tf, text="  Máx:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))
        tk.Entry(tf, textvariable=self.var_type_interval_max, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 12), justify="center",
                 relief="flat", bd=4).pack(side="left", padx=(4, 0))
        tk.Label(tf, text="ms  (vazio = sem variação)", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 8)).pack(side="left", padx=6)

        self._section(p, "Repetições", "🔁 ").pack(fill="x", padx=8, pady=3)
        rf = tk.Frame(p, bg=T["bg"]); rf.pack(fill="x", padx=14, pady=(2, 6))
        tk.Radiobutton(rf, text="∞ Infinito", variable=self.var_type_rep_mode, value="infinite",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        tk.Radiobutton(rf, text="Qtd:", variable=self.var_type_rep_mode, value="count",
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left", padx=(12, 2))
        tk.Entry(rf, textvariable=self.var_type_rep_count, width=7,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 11), justify="center",
                 relief="flat", bd=4).pack(side="left")

        self._section(p, "Atraso Inicial (s)", "⏳ ").pack(fill="x", padx=8, pady=3)
        df = tk.Frame(p, bg=T["bg"]); df.pack(fill="x", padx=14, pady=(2, 6))
        tk.Label(df, text="Esperar antes de começar (s):", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(df, textvariable=self.var_type_delay, width=6,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 12), justify="center",
                 relief="flat", bd=4).pack(side="left", padx=8)
        tk.Label(df, text="(use para trocar de janela)", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 8)).pack(side="left")

        self.key_btn_var = tk.StringVar(value="▶  START AUTOKEYBOARD   F7")
        self.key_btn = tk.Button(p, textvariable=self.key_btn_var,
                                  command=self.toggle_typing,
                                  bg=T["accent"], fg="#ffffff",
                                  font=("Segoe UI", 11, "bold"),
                                  relief="flat", pady=13, cursor="hand2",
                                  activeforeground="#ffffff",
                                  activebackground=T["accent_h"],
                                  bd=0, highlightthickness=0)
        self.key_btn.pack(fill="x", padx=8, pady=(10, 10))
        self.key_btn.bind("<Enter>", lambda e: self._btn_anim_hover(
            self.key_btn, T["red_h"] if self._type_running else T["accent_h"]))
        self.key_btn.bind("<Leave>", lambda e: self._btn_anim_hover(
            self.key_btn, T["red"] if self._type_running else T["accent"]))
        Tooltip(self.key_btn,
                get_text=lambda e: f"Atalho: {self.var_hk_key.get().upper()}  •  "
                                   "Configurável em ⚙ Configurações",
                delay_ms=700)

    # ─────────────────────────────────────────────────────────────
    # AUTO KEYBOARD — LÓGICA
    # ─────────────────────────────────────────────────────────────
    def _insert_token(self, token: str) -> None:
        """Insere um token na posição do cursor do type_text (ou no fim)."""
        try:
            self.type_text.insert("insert", token)
            self.type_text.focus_set()
        except Exception:
            pass

    def _load_text_from_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Carregar texto",
            filetypes=[("Texto", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if not path:
            return
        try:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(path, "r", encoding="cp1252") as f:
                    content = f.read()
        except Exception as exc:
            self._set_status(f"Erro ao ler arquivo: {exc}")
            return
        self.type_text.delete("1.0", "end")
        self.type_text.insert("1.0", content.rstrip("\n"))
        self._set_status(f"✓  Texto carregado: {os.path.basename(path)}")

    def toggle_typing(self) -> None:
        if self._type_running:
            self._stop_typing()
        else:
            self._start_typing()

    def _start_typing(self) -> None:
        if self._click_running:
            self._stop_clicking()

        try:
            interval_ms = max(0, int(self.var_type_interval.get() or 50))
        except ValueError:
            interval_ms = 50
        try:
            max_str = self.var_type_interval_max.get().strip()
            interval_max_ms = max(interval_ms, int(max_str)) if max_str else interval_ms
        except ValueError:
            interval_max_ms = interval_ms
        try:
            rep_count = int(self.var_type_rep_count.get() or 1)
        except ValueError:
            rep_count = 1
        try:
            delay_s = float(self.var_type_delay.get() or 0)
        except ValueError:
            delay_s = 3.0

        type_loop = self._macro_runner.get_type_loop()
        type_loop.configure(
            text=self.type_text.get("1.0", "end-1c"),
            interval_ms=interval_ms,
            interval_max_ms=interval_max_ms,
            rep_mode=self.var_type_rep_mode.get(),
            rep_count=rep_count,
            delay_s=delay_s,
            paste_mode=self.var_type_paste.get(),
            press_enter=self.var_type_enter.get(),
            on_status=lambda msg: self.after(0, lambda m=msg: self._set_status(m)),
            on_stop=lambda: self.after(0, self._stop_typing),
        )

        self._type_running = True
        self.key_btn.config(bg=T["red"], fg="#ffffff")
        self.key_btn_var.set("⏹  STOP AUTOKEYBOARD   F7")
        self._set_pill(self._pill_key, True, T["green"])
        self._start_pulse(self.key_btn)
        self._run_indicator_start()
        type_loop.start()

    def _stop_typing(self) -> None:
        self._macro_runner.get_type_loop().stop()
        self._type_running = False
        self._stop_pulse(self.key_btn)
        self.key_btn.config(bg=T["accent"], fg="#ffffff")
        self.key_btn_var.set("▶  START AUTOKEYBOARD   F7")
        self._set_pill(self._pill_key, False)
        if not self._click_running and not self._macro_running:
            self._run_indicator_stop()
        self._set_status("⏹  autokeyboard parado.")
