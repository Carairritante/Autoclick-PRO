"""
ui/app.py — Interface gráfica do AutoClick Pro.

Importa de core/ para toda lógica de automação e acesso ao WinAPI.
Este arquivo contém apenas código tkinter e orquestração de UI.
"""
from __future__ import annotations

import collections
import copy
import json
import math
import os
import struct
import threading
import time
import wave
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import keyboard
import pyautogui

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    HAS_TRAY = True and HAS_PIL
except ImportError:
    HAS_TRAY = False

from core.driver import WindowsDriver
from core.engine import MacroRunner
from core.hotstrings import HotstringManager
from core.ntfy_client import Monitor, NtfyClient
from core.paths import NTFY_CONFIG_PATH
from core.recorder import HAS_PYNPUT, MacroRecorder
from core.macro_schema import (
    MacroScript,
    MacroStep,
    StopCondition,
    UIProfile,
    macrostep_from_dict,
    macrostep_to_dict,
    profile_to_dict,
    script_from_dict,
    stop_cond_from_dict,
    stop_cond_to_dict,
    ui_from_dict,
)
from ui.monitor_dialog import MonitorDialog
from ui.step_dialog import (
    ACTION_DESCRIPTIONS,
    ACTION_LABELS,
    StepDialog,
    StopConditionDialog,
    step_to_params_str,
)
from ui.widgets import Tooltip, make_button

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0
pyautogui.MINIMUM_DURATION = 0

# ─── TEMAS ────────────────────────────────────────────────────────────────────
THEME_DARK = {
    "bg":        "#313338",   # canvas principal
    "bg_deep":   "#1e1f22",   # fundos profundos: inputs, header, tabs
    "panel":     "#2b2d31",   # cards / sections
    "card":      "#232428",   # cards alternativos / hover dim
    "card_h":    "#3f4147",   # hover de cards
    "accent":    "#5865f2",   # blurple Discord
    "accent_h":  "#4752c4",
    "accent2":   "#c7ccff",   # texto blurple (tokens)
    "accent2_h": "#a8aff3",
    "text":      "#dbdee1",
    "subtext":   "#949ba4",
    "green":     "#23a55a",   # Discord green
    "green_h":   "#1a8048",
    "red":       "#f23f43",   # Discord red
    "red_h":     "#c9282b",
    "border":    "#3f4147",
    "line":      "#3f4147",
    "line_2":    "#4e5058",
    "sep":       "#3f4147",
    "ind_bg":    "#1e1f22",
    "ind_off":   "#6c6e72",
    "sel":       "#3c4070",   # blurple soft (tk não tem alpha)
}
THEME_LIGHT = {
    "bg":        "#ffffff",
    "bg_deep":   "#ebedef",   # inputs / header secundário
    "panel":     "#f2f3f5",   # cards
    "card":      "#e3e5e8",
    "card_h":    "#d4d7dc",
    "accent":    "#5865f2",   # blurple — mesmo do dark (brand)
    "accent_h":  "#4752c4",
    "accent2":   "#4752c4",
    "accent2_h": "#3c45a5",
    "text":      "#2e3338",
    "subtext":   "#5c5e66",
    "green":     "#248046",
    "green_h":   "#1a6334",
    "red":       "#d83c3e",
    "red_h":     "#b32d2f",
    "border":    "#cbcdd1",
    "line":      "#d8dadd",
    "line_2":    "#bcbcc2",
    "sep":       "#d8dadd",
    "ind_bg":    "#f2f3f5",
    "ind_off":   "#c4c9ce",
    "sel":       "#dbe0ff",   # blurple bem clarinho
}
# T mutável — _apply_theme troca os valores in-place pra todos os widgets pegarem
T = dict(THEME_DARK)

# Fonte mono (JetBrains Mono cai em Consolas se não instalado)
FONT_MONO = "JetBrains Mono"
FONT_UI   = "Segoe UI"

# ─── CHAVE PIX PARA DONATIONS ─────────────────────────────────────────────────
# Edite esta linha com sua chave PIX (CPF, email, celular ou aleatória).
# Aparece no botão "❤ Apoie o projeto" na aba Configurações.
PIX_KEY   = "ngnicol123.cs@gmail.com"
PIX_OWNER = "Nicolas Gabriel"   # Nome de quem recebe (aparece no diálogo)

# Caminho raiz do projeto (um nível acima de ui/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AutoClickPro(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AutoClick Pro")
        self.geometry("660x780")
        self.minsize(560, 600)        # tamanho mínimo pra não quebrar layout
        self.resizable(True, True)
        self._is_fullscreen = False
        self._pre_fs_size = (660, 780)
        self._pre_fs_pos  = (100, 100)
        self._current_theme = "dark"   # será sobrescrito por _restore_window_geometry se houver pref salva
        self.configure(bg=T["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # F11 alterna fullscreen; Escape sai do fullscreen
        self.bind("<F11>",     lambda e: self._toggle_fullscreen())
        self.bind("<Escape>",  lambda e: self._exit_fullscreen())

        # Camada de acesso ao Windows (windll isolada em core/driver.py)
        self._driver = WindowsDriver()
        self._apply_dark_titlebar()

        # Coordenador de loops de automação (core/engine.py)
        self._macro_runner = MacroRunner(self._driver)

        self._tray            = None
        self._tray_notified   = False
        self._click_running   = False
        self._type_running    = False
        self._macro_running   = False
        self._macro_steps: list[MacroStep] = []
        self._stop_conditions: list[StopCondition] = []
        self._debug_event: threading.Event | None = None
        self._recorder        = MacroRecorder()
        self._recorder_running = False
        self._session_clicks  = 0
        self._session_start: float | None = None
        self._recent_clicks   = collections.deque(maxlen=300)
        self._stats_after_id  = None
        self._tick_wav_path: str | None = None
        self._hk_capture_hook = None
        self._seq_positions: list[dict] = []
        self._overlay         = None
        self._target_hwnd: int = 0
        self._target_win_name: str = ""

        # Hotstrings (atalhos de texto) — opt-in, desligado por padrão
        self._hotstrings = HotstringManager(self._driver)
        self.var_hotstrings_active = tk.BooleanVar(value=False)

        # Monitoramento (ntfy) — opt-in, conecta só quando usuário liga
        self._ntfy = NtfyClient(self._driver)
        self.var_ntfy_active = tk.BooleanVar(value=False)
        # Callbacks (definidos antes de start)
        self._ntfy.on_command = lambda cmd, arg: self.after(
            0, lambda c=cmd, a=arg: self._ntfy_handle_command(c, a)
        )
        self._ntfy.on_status_change = lambda s: self.after(
            0, lambda st=s: self._ntfy_on_status_change(st)
        )
        self._ntfy.on_activity = lambda msg, status: self.after(
            0, lambda m=msg, s=status: self._ntfy_on_activity(m, s)
        )
        # Hotstring disparada → notifica monitores de evento
        self._hotstrings.on_expand = lambda trig: self.after(
            0, lambda t=trig: self._ntfy.fire_event("hotstring_fired", label=t)
        )

        self._init_state()
        self._init_style()
        # Carrega ntfy ANTES de _build_ui para que os checkboxes reflitam o estado salvo
        os.makedirs(os.path.join(_ROOT, "profiles"), exist_ok=True)
        self._ntfy.load(NTFY_CONFIG_PATH)
        if not self._ntfy.get_allowed_cmds():
            self._ntfy.set_allowed_cmds({"stop", "pause", "resume", "run",
                                          "status", "screen", "help"})
        self._build_ui()
        self._init_hotkeys()
        self._init_tray()
        self._warn_missing_deps()
        self._generate_tick_wav()
        self._generate_icon_ico()
        self._hotstrings.load(os.path.join(_ROOT, "profiles", "hotstrings.json"))
        self._refresh_hs_tree()
        self._restore_window_geometry()

        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

    # ─────────────────────────────────────────────────────────────
    # DARK TITLE BAR  (windll delegado ao driver)
    # ─────────────────────────────────────────────────────────────
    def _apply_dark_titlebar(self) -> None:
        try:
            self.update()
            self._driver.set_dark_mode(self.winfo_id())
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # STATE
    # ─────────────────────────────────────────────────────────────
    def _init_state(self) -> None:
        self.var_mouse_btn      = tk.StringVar(value="left")
        self.var_click_type     = tk.StringVar(value="single")
        self.var_interval_h     = tk.StringVar(value="0")
        self.var_interval_m     = tk.StringVar(value="0")
        self.var_interval_s     = tk.StringVar(value="0")
        self.var_interval_ms    = tk.StringVar(value="100")
        self.var_pos_mode       = tk.StringVar(value="cursor")
        self.var_pos_x          = tk.StringVar(value="500")
        self.var_pos_y          = tk.StringVar(value="400")
        self.var_rep_mode       = tk.StringVar(value="infinite")
        self.var_rep_count      = tk.StringVar(value="100")
        self.var_humanize       = tk.BooleanVar(value=False)
        self.var_humanize_pct   = tk.StringVar(value="10")
        self.var_jitter         = tk.BooleanVar(value=False)
        self.var_jitter_px      = tk.StringVar(value="5")
        self.var_type_interval  = tk.StringVar(value="50")
        self.var_type_rep_mode  = tk.StringVar(value="infinite")
        self.var_type_rep_count = tk.StringVar(value="10")
        self.var_type_delay     = tk.StringVar(value="3")
        self.var_type_paste         = tk.BooleanVar(value=True)
        self.var_type_enter         = tk.BooleanVar(value=False)
        self.var_type_interval_max  = tk.StringVar(value="")
        self.var_macro_speed        = tk.StringVar(value="1")
        self.var_macro_debug        = tk.BooleanVar(value=False)
        self.var_macro_notify_done  = tk.BooleanVar(value=False)
        self.var_sound              = tk.BooleanVar(value=False)
        self.var_hk_clk         = tk.StringVar(value="f6")
        self.var_hk_key         = tk.StringVar(value="f7")
        self.var_hk_stop        = tk.StringVar(value="f8")
        self.var_hk_pause       = tk.StringVar(value="pause")
        self.var_burst            = tk.StringVar(value="1")
        self.var_overlay          = tk.BooleanVar(value=False)
        self.var_simultaneous     = tk.BooleanVar(value=False)
        self.var_target_window    = tk.BooleanVar(value=False)
        self.var_slot_names       = [tk.StringVar(value="") for _ in range(3)]
        self.var_hk_macro           = tk.StringVar(value="f9")
        self.var_hk_rec             = tk.StringVar(value="f10")
        self.var_macro_rep_mode     = tk.StringVar(value="infinite")
        self.var_macro_rep_count    = tk.StringVar(value="1")
        self.var_macro_loop_delay   = tk.StringVar(value="1")
        self.var_capture_keyboard   = tk.BooleanVar(value=True)

    # ─────────────────────────────────────────────────────────────
    # STYLE
    # ─────────────────────────────────────────────────────────────
    def _init_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        # Notebook monocromático: aba ativa = bg principal + texto branco, inativa = fundo escuro + texto cinza
        style.configure("TNotebook",
            background=T["bg_deep"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab",
            background=T["bg_deep"], foreground=T["subtext"],
            font=("Segoe UI", 9, "bold"), padding=[18, 9],
            borderwidth=0)
        style.map("TNotebook.Tab",
            background=[("selected", T["bg"])],
            foreground=[("selected", T["text"])],
            expand=[("selected", [0, 0, 0, 0])])
        # Treeview monocromático (bg_deep = preto puro no dark / branco no light)
        style.configure("Seq.Treeview",
            background=T["bg_deep"], foreground=T["text"],
            fieldbackground=T["bg_deep"], rowheight=24, borderwidth=0,
            font=("Consolas", 10))
        style.configure("Seq.Treeview.Heading",
            background=T["panel"], foreground=T["subtext"],
            font=("Segoe UI", 8, "bold"), relief="flat", borderwidth=0)
        style.map("Seq.Treeview",
            background=[("selected", T["card_h"])],
            foreground=[("selected", T["text"])])
        style.map("Seq.Treeview.Heading",
            background=[("active", T["panel"])])
        # Scrollbars finas
        style.configure("TScrollbar",
            background=T["card"], troughcolor=T["bg_deep"],
            borderwidth=0, arrowcolor=T["subtext"],
            relief="flat")
        style.map("TScrollbar",
            background=[("active", T["card_h"])])
        # Combobox monocromático (usado em step_dialog)
        style.configure("TCombobox",
            fieldbackground=T["bg_deep"], background=T["card"],
            foreground=T["text"], arrowcolor=T["subtext"],
            borderwidth=1, relief="flat",
            selectbackground=T["card_h"], selectforeground=T["text"])
        style.map("TCombobox",
            fieldbackground=[("readonly", T["bg_deep"])],
            foreground=[("readonly", T["text"])],
            selectbackground=[("readonly", T["card_h"])])

    # ─────────────────────────────────────────────────────────────
    # BUTTON HELPER
    # ─────────────────────────────────────────────────────────────
    def _btn(self, parent, text, command, bg, fg=None,
             font_size=9, bold=False, padx=10, pady=5, width=None):
        # Auto-pick fg baseado no brilho do bg — contraste absoluto, independe de tema
        if fg is None:
            try:
                r = int(bg[1:3], 16); g = int(bg[3:5], 16); b = int(bg[5:7], 16)
                fg = "#0a0a0a" if (r + g + b) / 3 > 128 else "#ededed"
            except Exception:
                fg = T["text"]
        return make_button(parent, text, command, bg, fg=fg,
                           font_size=font_size, bold=bold,
                           padx=padx, pady=pady, width=width)

    # ─────────────────────────────────────────────────────────────
    # BUILD UI
    # ─────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self._build_header()
        self._build_notebook()
        self._build_footer()

    # ── Header (minimalista monocromático) ────────────────────────
    def _build_header(self) -> None:
        hdr = tk.Frame(self, bg=T["bg_deep"])
        hdr.pack(fill="x")
        # linha fina inferior separando do conteúdo
        tk.Frame(hdr, bg=T["line"], height=1).pack(fill="x", side="bottom")

        inner = tk.Frame(hdr, bg=T["bg_deep"])
        inner.pack(fill="x", padx=14, pady=10)

        # Esquerda: logo (quadrado branco) + título
        left = tk.Frame(inner, bg=T["bg_deep"])
        left.pack(side="left")
        # mark blurple (identidade Discord)
        mark = tk.Frame(left, bg=T["accent"], width=14, height=14,
                        highlightbackground=T["accent"], highlightthickness=1)
        mark.pack(side="left", padx=(0, 10), pady=4)
        mark.pack_propagate(False)
        title_box = tk.Frame(left, bg=T["bg_deep"])
        title_box.pack(side="left")
        title_line = tk.Frame(title_box, bg=T["bg_deep"])
        title_line.pack(anchor="w")
        tk.Label(title_line, text="AutoClick",
                 font=("Segoe UI", 16, "bold"),
                 bg=T["bg_deep"], fg=T["text"]).pack(side="left")
        tk.Label(title_line, text=" Pro",
                 font=("Segoe UI", 16),
                 bg=T["bg_deep"], fg=T["accent"]).pack(side="left")
        tk.Label(title_box,
                 text="AUTOCLICKER · AUTOKEYBOARD · MACRO",
                 font=("Segoe UI", 7, "bold"),
                 bg=T["bg_deep"], fg=T["subtext"]).pack(anchor="w", pady=(0, 0))

        # Direita: pills de status + stats + botão X pequeno
        right = tk.Frame(inner, bg=T["bg_deep"])
        right.pack(side="right")

        # Botão X pequeno (vermelho) — fecha tudo e sai do app
        qbtn = tk.Button(right, text="✕", command=self._quit_app,
                         font=("Segoe UI", 8, "bold"),
                         bg=T["bg_deep"], fg=T["red"],
                         activebackground=T["red"], activeforeground="#ffffff",
                         relief="flat", bd=0, cursor="hand2",
                         padx=5, pady=0, highlightthickness=0)
        qbtn.pack(side="right", padx=(8, 0))
        qbtn.bind("<Enter>", lambda e: qbtn.config(bg=T["red"], fg="#ffffff"))
        qbtn.bind("<Leave>", lambda e: qbtn.config(bg=T["bg_deep"], fg=T["red"]))

        # Botão toggle tema (sol / lua)
        theme_glyph = "☀" if self._current_theme == "dark" else "☾"
        self._theme_btn = tk.Button(right, text=theme_glyph,
                                    command=self._toggle_theme,
                                    font=("Segoe UI", 11),
                                    bg=T["bg_deep"], fg=T["subtext"],
                                    activebackground=T["card_h"],
                                    activeforeground=T["text"],
                                    relief="flat", bd=0, cursor="hand2",
                                    padx=5, pady=0, highlightthickness=0)
        self._theme_btn.pack(side="right", padx=(8, 0))
        self._theme_btn.bind("<Enter>", lambda e: self._theme_btn.config(fg=T["text"]))
        self._theme_btn.bind("<Leave>", lambda e: self._theme_btn.config(fg=T["subtext"]))

        self.lbl_total = tk.Label(right, text="", font=("Consolas", 10, "bold"),
                                  bg=T["card"], fg=T["text"],
                                  padx=8, pady=3,
                                  highlightbackground=T["line_2"],
                                  highlightthickness=1)
        self.lbl_cps = tk.Label(right, text="", font=("Consolas", 10, "bold"),
                                bg=T["card"], fg=T["text"],
                                padx=8, pady=3,
                                highlightbackground=T["line_2"],
                                highlightthickness=1)

        # Status pills CLK / KEY / MCR / REC
        self._pill_clk = self._mk_pill(right, "CLK")
        self._pill_key = self._mk_pill(right, "KEY")
        self._pill_mcr = self._mk_pill(right, "MCR")
        self._pill_rec = self._mk_pill(right, "REC")

        self._pill_clk.pack(side="left", padx=2)
        self._pill_key.pack(side="left", padx=2)
        self._pill_mcr.pack(side="left", padx=2)
        self._pill_rec.pack(side="left", padx=2)

        # Compatibilidade com código antigo (_dot_clk / _dot_key viraram aliases das pills)
        self._dot_clk = self._pill_clk
        self._dot_key = self._pill_key

    def _mk_pill(self, parent, text: str) -> tk.Label:
        """Cria pill de status (apagada por padrão). Use set_pill() pra ligar/desligar."""
        lbl = tk.Label(parent, text="● " + text,
                       font=("Segoe UI", 7, "bold"),
                       bg=T["card"], fg=T["subtext"],
                       padx=7, pady=2,
                       highlightbackground=T["line_2"],
                       highlightthickness=1)
        return lbl

    def _start_pulse(self, btn: tk.Button) -> None:
        """Inicia a animação de pulse (alterna T['red'] e T['red_h']).

        Marcador `_pulse_running=True` no widget; auto-para quando flag vira False.
        """
        btn._pulse_running = True
        self._pulse_step(btn)

    def _pulse_step(self, btn: tk.Button) -> None:
        if not getattr(btn, "_pulse_running", False):
            return
        try:
            cur = btn.cget("bg")
            btn.config(bg=T["red_h"] if cur == T["red"] else T["red"])
        except tk.TclError:
            return  # widget destruído
        self.after(750, lambda: self._pulse_step(btn))

    def _stop_pulse(self, btn: tk.Button) -> None:
        btn._pulse_running = False

    def _set_pill(self, pill: tk.Label, on: bool, color: str | None = None) -> None:
        """Liga/desliga uma pill de status."""
        if on:
            c = color or T["green"]
            pill.config(fg=c, highlightbackground=c)
        else:
            pill.config(fg=T["subtext"], highlightbackground=T["line_2"])

    # ── Notebook ──────────────────────────────────────────────────
    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(6, 4))
        self._nb = nb  # exposto pra _toggle_theme preservar aba ativa

        self.tab_click   = tk.Frame(nb, bg=T["bg"])
        self.tab_key     = tk.Frame(nb, bg=T["bg"])
        self.tab_macro   = tk.Frame(nb, bg=T["bg"])
        self.tab_hs      = tk.Frame(nb, bg=T["bg"])
        self.tab_monitor = tk.Frame(nb, bg=T["bg"])
        self.tab_cfg     = tk.Frame(nb, bg=T["bg"])

        nb.add(self.tab_click,   text="🖱  AutoClick")
        nb.add(self.tab_key,     text="⌨  AutoKeyboard")
        nb.add(self.tab_macro,   text="🤖  Macro")
        nb.add(self.tab_hs,      text="✨  Hotstrings")
        nb.add(self.tab_monitor, text="📡  Monitoramento")
        nb.add(self.tab_cfg,     text="⚙  Configurações")

        self._build_click_tab()
        self._build_keyboard_tab()
        self._build_macro_tab()
        self._build_hotstrings_tab()
        self._build_monitor_tab()
        self._build_settings_tab()

    # ── Footer (status bar terminal-like) ─────────────────────────
    def _build_footer(self) -> None:
        tk.Frame(self, bg=T["line_2"], height=1).pack(fill="x", side="bottom")
        # Clock + stats
        ftr = tk.Frame(self, bg=T["bg_deep"])
        ftr.pack(fill="x", side="bottom")

        self._status_dot = tk.Label(ftr, text="○", bg=T["bg_deep"], fg=T["subtext"],
                                     font=("Consolas", 10))
        self._status_dot.pack(side="left", padx=(12, 4), ipady=4)

        tk.Label(ftr, text="$", bg=T["bg_deep"], fg=T["text"],
                 font=("Consolas", 10, "bold")).pack(side="left", padx=(0, 6), ipady=4)

        self.lbl_status = tk.Label(ftr,
                                    text="pronto. aguardando comando.",
                                    bg=T["bg_deep"], fg=T["subtext"],
                                    font=("Consolas", 9), anchor="w")
        self.lbl_status.pack(side="left", ipady=4, fill="x", expand=True)

        # Relógio (canto direito)
        self.lbl_clock = tk.Label(ftr, text="", bg=T["bg_deep"], fg=T["subtext"],
                                  font=("Consolas", 9), anchor="e", padx=10)
        self.lbl_clock.pack(side="right", ipady=4)

        # Stats com aspecto monoespaçado
        self.lbl_stats = tk.Label(ftr, text="",
                                   bg=T["bg_deep"], fg=T["text"],
                                   font=("Consolas", 9), anchor="e", padx=8)
        self.lbl_stats.pack(side="right", ipady=4)

        self._tick_clock()

    def _tick_clock(self) -> None:
        try:
            from datetime import datetime
            self.lbl_clock.config(text=datetime.now().strftime("%H:%M:%S"))
        except Exception:
            pass
        self.after(1000, self._tick_clock)

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
        self.click_btn.bind("<Enter>", lambda e: self.click_btn.config(
            bg=T["red_h"] if self._click_running else T["accent_h"]))
        self.click_btn.bind("<Leave>", lambda e: self.click_btn.config(
            bg=T["red"] if self._click_running else T["accent"]))

    # ─────────────────────────────────────────────────────────────
    # ABA: AUTO KEYBOARD
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
        self.key_btn.bind("<Enter>", lambda e: self.key_btn.config(
            bg=T["red_h"] if self._type_running else T["accent_h"]))
        self.key_btn.bind("<Leave>", lambda e: self.key_btn.config(
            bg=T["red"] if self._type_running else T["accent"]))

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
        self.macro_btn.bind("<Enter>", lambda e: self.macro_btn.config(
            bg=T["red_h"] if self._macro_running else T["accent_h"]))
        self.macro_btn.bind("<Leave>", lambda e: self.macro_btn.config(
            bg=T["red"] if self._macro_running else T["accent"]))
        self.pause_btn = self._btn(exec_row, "⏸  Pausar", self._toggle_pause,
                                    bg=T["card"], fg=T["text"],
                                    font_size=10, bold=True, padx=14, pady=11)
        self.pause_btn.pack(side="left", padx=(6, 0))

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
        path = os.path.join(_ROOT, "profiles", "hotstrings.json")
        try:
            self._hotstrings.save(path)
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

    # ─────────────────────────────────────────────────────────────
    # ABA: MONITORAMENTO (ntfy.sh — alertas + comandos via celular)
    # ─────────────────────────────────────────────────────────────
    def _build_monitor_tab(self) -> None:
        p = self._make_scrollable(self.tab_monitor)

        # ── Header / descrição ───────────────────────────────────
        self._section(p, "Monitoramento — Controle pelo Celular", "📡 "
                       ).pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Receba alertas e controle o AutoClick pelo celular "
                          "(grátis, sem cadastro).\n"
                          "Setup: instale o app 'ntfy' (Play/App Store) e escaneie o QR.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9),
                 justify="left").pack(fill="x", padx=14, pady=(0, 6))

        # ── Status / conexão ─────────────────────────────────────
        conn_frame = tk.Frame(p, bg=T["bg"])
        conn_frame.pack(fill="x", padx=14, pady=4)
        self._ntfy_status_lbl = tk.Label(conn_frame, text="🔴 desconectado",
                                          bg=T["bg"], fg=T["subtext"],
                                          font=("Segoe UI", 10, "bold"))
        self._ntfy_status_lbl.pack(side="left")
        tk.Label(conn_frame, text="    Topic ID:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")
        self._ntfy_topic_lbl = tk.Label(
            conn_frame,
            text=self._ntfy.topic_id[:16] + "…" if self._ntfy.has_topic() else "(não pareado)",
            bg=T["bg"], fg=T["text"], font=("Consolas", 9))
        self._ntfy_topic_lbl.pack(side="left", padx=4)

        btn_row1 = tk.Frame(p, bg=T["bg"])
        btn_row1.pack(fill="x", padx=14, pady=(4, 2))
        self._btn(btn_row1, "🔄 Gerar Novo Pareamento", self._ntfy_regenerate_topic,
                   bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=(0, 4))
        self._btn(btn_row1, "📱 Mostrar QR Code", self._ntfy_show_qr,
                   bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=4)
        self._btn(btn_row1, "📤 Testar Notificação", self._ntfy_test_notification,
                   bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=4)

        btn_row2 = tk.Frame(p, bg=T["bg"])
        btn_row2.pack(fill="x", padx=14, pady=(2, 8))
        tk.Checkbutton(btn_row2, text="🟢 Ativar Conexão",
                        variable=self.var_ntfy_active,
                        command=self._toggle_ntfy_connection,
                        bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                        activebackground=T["bg"],
                        font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(btn_row2, text="(opt-in: liga só quando você quer)",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(side="left", padx=8)

        # ── Debug: histórico de mensagens recebidas do celular ──
        tk.Label(p, text="Últimas 5 atividades (debug):",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(anchor="w", padx=14, pady=(4, 2))
        self._ntfy_activity_log = tk.Text(
            p, height=5, bg=T["card"], fg=T["text"], font=("Consolas", 9),
            relief="flat", bd=4, wrap="none", state="disabled",
            highlightthickness=0)
        self._ntfy_activity_log.pack(fill="x", padx=14, pady=(0, 6))
        # Tags de cor por status
        self._ntfy_activity_log.tag_config("fired",        foreground=T["green"])
        self._ntfy_activity_log.tag_config("echo",         foreground=T["subtext"])
        self._ntfy_activity_log.tag_config("empty",        foreground=T["subtext"])
        self._ntfy_activity_log.tag_config("not_allowed",  foreground=T["accent2"])
        # Buffer das últimas 5 entradas: lista de (texto, tag)
        self._ntfy_activity_entries: collections.deque = collections.deque(maxlen=5)

        # ── Comandos permitidos ─────────────────────────────────
        self._section(p, "Comandos Permitidos do Celular", "🎮 "
                       ).pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Marque o que o celular pode controlar via DM/botão.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9)
                 ).pack(fill="x", padx=14, pady=(0, 4))

        cmd_frame = tk.Frame(p, bg=T["bg"])
        cmd_frame.pack(fill="x", padx=14, pady=4)
        self._ntfy_cmd_vars: dict[str, tk.BooleanVar] = {}
        allowed = self._ntfy.get_allowed_cmds()
        cmd_specs = [
            ("stop",   "/stop",   "Parar macro/loop"),
            ("pause",  "/pause",  "Pausar macro"),
            ("resume", "/resume", "Retomar macro pausado"),
            ("run",    "/run",    "Rodar macro atual (ou /run 1 / nome)"),
            ("status", "/status", "Receber status atual"),
            ("screen", "/screen", "Receber screenshot da tela"),
            ("help",   "/help",   "Listar comandos disponíveis"),
        ]
        for i, (cmd, label, desc) in enumerate(cmd_specs):
            var = tk.BooleanVar(value=cmd in allowed)
            self._ntfy_cmd_vars[cmd] = var
            row, col = divmod(i, 2)
            tk.Checkbutton(cmd_frame, text=f"{label}  ({desc})",
                            variable=var,
                            command=self._ntfy_save_cmds,
                            bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                            activebackground=T["bg"],
                            font=("Segoe UI", 9)
                            ).grid(row=row, column=col, sticky="w", padx=(0, 12), pady=2)

        # ── Monitores ────────────────────────────────────────────
        self._section(p, "Monitores Ativos", "🎯 "
                       ).pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Defina o que aciona o alerta no seu celular.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9)
                 ).pack(fill="x", padx=14, pady=(0, 4))

        mon_btns = tk.Frame(p, bg=T["bg"])
        mon_btns.pack(fill="x", padx=14, pady=(6, 4))
        self._btn(mon_btns, "➕ Adicionar", self._mon_add,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=(0, 4))
        self._btn(mon_btns, "✏ Editar", self._mon_edit,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
        self._btn(mon_btns, "✕ Remover", self._mon_remove,
                   bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)

        mon_tree_frame = tk.Frame(p, bg=T["bg"])
        mon_tree_frame.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        self.mon_tree = ttk.Treeview(
            mon_tree_frame,
            columns=("name", "type", "cooldown", "screenshot", "enabled"),
            show="headings", style="Seq.Treeview", height=8,
        )
        self.mon_tree.heading("name",       text="Nome")
        self.mon_tree.heading("type",       text="Tipo")
        self.mon_tree.heading("cooldown",   text="Cooldown")
        self.mon_tree.heading("screenshot", text="Screen?")
        self.mon_tree.heading("enabled",    text="Ativo")
        self.mon_tree.column("name",       width=160, anchor="w")
        self.mon_tree.column("type",       width=70,  anchor="center")
        self.mon_tree.column("cooldown",   width=70,  anchor="center")
        self.mon_tree.column("screenshot", width=60,  anchor="center")
        self.mon_tree.column("enabled",    width=50,  anchor="center")
        self.mon_tree.pack(fill="both", expand=True, side="left")
        self.mon_tree.bind("<Double-1>", lambda e: self._mon_edit())

        mon_sb = ttk.Scrollbar(mon_tree_frame, orient="vertical",
                                command=self.mon_tree.yview)
        mon_sb.pack(side="right", fill="y")
        self.mon_tree.config(yscrollcommand=mon_sb.set)
        self._refresh_mon_tree()

    # ── Helpers ntfy ──────────────────────────────────────────────
    def _refresh_mon_tree(self) -> None:
        if not hasattr(self, "mon_tree"):
            return
        for item in self.mon_tree.get_children():
            self.mon_tree.delete(item)
        for m in self._ntfy.get_monitors():
            self.mon_tree.insert("", "end", values=(
                m.name or "(sem nome)",
                m.trigger_type,
                f"{m.cooldown_s}s",
                "✓" if m.attach_screenshot else "—",
                "✓" if m.enabled else "—",
            ))

    def _ntfy_save(self) -> None:
        try:
            self._ntfy.save(NTFY_CONFIG_PATH)
        except OSError as exc:
            messagebox.showerror("Erro ao salvar monitoramento",
                                  f"Não foi possível salvar:\n{exc}", parent=self)

    def _ntfy_save_cmds(self) -> None:
        cmds = {c for c, v in self._ntfy_cmd_vars.items() if v.get()}
        self._ntfy.set_allowed_cmds(cmds)
        self._ntfy_save()

    def _ntfy_regenerate_topic(self) -> None:
        if self._ntfy.has_topic():
            if not messagebox.askyesno(
                "Regenerar pareamento",
                "Isso vai invalidar o QR antigo. Você precisará reescanear "
                "no celular. Continuar?", parent=self):
                return
        # Desconecta se ativo, gera novo, reconecta se estava ativo
        was_running = self._ntfy.is_running
        if was_running:
            self._ntfy.stop()
        new_topic = self._ntfy.generate_topic()
        self._ntfy.set_topic(new_topic)
        self._ntfy_save()
        self._ntfy_topic_lbl.config(text=new_topic[:16] + "…")
        if was_running:
            self._ntfy.start()
        self._set_status("🔄 Novo topic gerado — reescanear QR no celular")

    def _ntfy_show_qr(self) -> None:
        if not self._ntfy.has_topic():
            messagebox.showinfo("Sem pareamento",
                                "Clique em 'Gerar Novo Pareamento' primeiro.",
                                parent=self)
            return
        try:
            import qrcode
            from PIL import ImageTk
        except ImportError:
            messagebox.showerror("Dependência faltando",
                                  "Instale: pip install qrcode[pil]", parent=self)
            return

        # QR usa deeplink ntfy:// que abre direto o app (não o site lento)
        qr_url = self._ntfy.subscribe_deeplink()
        # Mas mostramos a URL HTTPS no campo "Ou cole no app", pois é a que
        # o usuário pode realmente colar no campo de subscribe do app.
        https_url = self._ntfy.topic_url()
        img = qrcode.make(qr_url)

        # Modal mostrando QR
        dlg = tk.Toplevel(self)
        dlg.title("QR Code do Pareamento")
        dlg.configure(bg=T["bg"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Escaneie no app ntfy do celular:",
                 bg=T["bg"], fg=T["text"], font=("Segoe UI", 11, "bold")
                 ).pack(padx=16, pady=(14, 4))
        tk.Label(dlg, text="(abre direto o app, sem passar pelo site)",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(padx=16, pady=(0, 6))

        # PIL → tk.PhotoImage
        try:
            # qrcode retorna PilImage; converte pra PIL.Image padrão
            pil_img = img.get_image() if hasattr(img, "get_image") else img
            photo = ImageTk.PhotoImage(pil_img)
        except Exception as e:
            messagebox.showerror("Erro ao gerar QR", str(e), parent=dlg)
            dlg.destroy()
            return

        qr_lbl = tk.Label(dlg, image=photo, bg="white")
        qr_lbl.image = photo  # evita garbage collect
        qr_lbl.pack(padx=16, pady=4)

        tk.Label(dlg, text="Ou adicione manualmente no app (Subscribe → cole abaixo):",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9)
                 ).pack(padx=16, pady=(8, 2))
        url_entry = tk.Entry(dlg, width=48, bg=T["card"], fg=T["text"],
                              font=("Consolas", 9), relief="flat", bd=4,
                              readonlybackground=T["card"])
        url_entry.insert(0, https_url)
        url_entry.config(state="readonly")
        url_entry.pack(padx=16, pady=(0, 4))

        def _copy_url() -> None:
            self.clipboard_clear()
            self.clipboard_append(https_url)
            self.update()  # garante que o clipboard persiste após fechar dlg
            copy_btn.config(text="✅ Copiado!")
            dlg.after(1500, lambda: copy_btn.config(text="📋 Copiar URL"))

        btn_row = tk.Frame(dlg, bg=T["bg"])
        btn_row.pack(pady=(8, 14))
        copy_btn = make_button(btn_row, "📋 Copiar URL", _copy_url,
                                T["card"], fg=T["text"], padx=12, pady=6)
        copy_btn.pack(side="left", padx=4)
        make_button(btn_row, "Fechar", dlg.destroy, T["accent"], fg="#ffffff",
                    padx=14, pady=6).pack(side="left", padx=4)

        dlg.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - dlg.winfo_width())  // 2
        py = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{px}+{py}")

    def _ntfy_test_notification(self) -> None:
        if not self._ntfy.has_topic():
            messagebox.showinfo("Sem pareamento",
                                "Gere um QR primeiro.", parent=self)
            return
        ok = self._ntfy.publish("✅ Teste do AutoClick Pro",
                                 title="Conexão funcionando!", priority=3)
        if ok:
            self._set_status("📤 Notificação de teste enviada")
        else:
            self._set_status("❌ Falha ao enviar (sem internet?)")

    def _toggle_ntfy_connection(self) -> None:
        if self.var_ntfy_active.get():
            if not self._ntfy.has_topic():
                # Auto-gera topic na primeira ativação
                self._ntfy.set_topic(self._ntfy.generate_topic())
                self._ntfy_topic_lbl.config(text=self._ntfy.topic_id[:16] + "…")
                self._ntfy_save()
            self._ntfy.start()
        else:
            self._ntfy.stop()

    def _ntfy_on_status_change(self, status: str) -> None:
        """Callback do ntfy: atualiza label de status (na thread main)."""
        if not hasattr(self, "_ntfy_status_lbl"):
            return
        if status == "connected":
            self._ntfy_status_lbl.config(text="🟢 conectado", fg=T["green"])
        else:
            self._ntfy_status_lbl.config(text="🔴 desconectado", fg=T["subtext"])

    def _ntfy_on_activity(self, raw_msg: str, status: str) -> None:
        """Callback debug: append no log das últimas 5 msgs (mais recentes no topo)."""
        if not hasattr(self, "_ntfy_activity_log"):
            return
        hh = time.strftime("%H:%M:%S")
        snippet = (raw_msg[:30] + "…") if len(raw_msg) > 30 else raw_msg
        snippet = snippet.replace("\n", " ")
        labels = {
            "fired":               ("✅ executou",                    "fired"),
            "filtered:echo":       ("🖥️ eco do PC (ignorado)",       "echo"),
            "filtered:empty":      ("⚪ msg vazia",                   "empty"),
            "filtered:not_allowed":("🚫 não permitido — marque acima", "not_allowed"),
        }
        lbl_text, tag = labels.get(status, (status, ""))
        entry = (f"[{hh}] '{snippet}' → {lbl_text}\n", tag)
        self._ntfy_activity_entries.appendleft(entry)
        # Re-renderiza
        self._ntfy_activity_log.config(state="normal")
        self._ntfy_activity_log.delete("1.0", "end")
        for text, t in self._ntfy_activity_entries:
            self._ntfy_activity_log.insert("end", text, t)
        self._ntfy_activity_log.config(state="disabled")

    def _ntfy_handle_command(self, cmd: str, arg: str = "") -> None:
        """Executa comando recebido do celular (já filtrado por allowlist).

        arg: parte depois do espaço — ex: "/run slot2" → cmd="run", arg="slot2"
        """
        try:
            if cmd == "stop":
                stopped = []
                if self._macro_running: self._stop_macro(); stopped.append("macro")
                if self._click_running: self._stop_clicking(); stopped.append("autoclick")
                if self._type_running:  self._stop_typing(); stopped.append("autokey")
                reply = "⏹ Parado: " + ", ".join(stopped) if stopped else "⏹ Nada estava rodando"
                self._ntfy.publish(reply, priority=2)
            elif cmd in ("pause", "resume"):
                self._toggle_pause()
                if not self._macro_running:
                    self._ntfy.publish("ℹ Nenhum macro rodando pra pausar", priority=2)
                else:
                    paused = self._macro_runner.get_sequential_runner().is_paused
                    self._ntfy.publish(f"⏸ Macro {'pausado' if paused else 'retomado'}",
                                       priority=2)
            elif cmd == "run":
                self._ntfy_run_macro(arg)
            elif cmd == "status":
                parts = []
                if self._macro_running: parts.append("macro rodando")
                if self._click_running: parts.append("autoclick rodando")
                if self._type_running:  parts.append("autokey rodando")
                msg = " + ".join(parts) if parts else "tudo parado"
                self._ntfy.publish(f"📊 Status: {msg}", priority=2)
            elif cmd == "screen":
                self._ntfy.publish("📸 Screen", attach_screenshot=True, priority=2)
            elif cmd == "help":
                self._ntfy_send_help()
            self._set_status(f"📱 Comando recebido: /{cmd}" + (f" {arg}" if arg else ""))
        except Exception as exc:
            self._ntfy.publish(f"⚠ Erro no comando /{cmd}: {exc}", priority=4)
            self._set_status(f"⚠ Erro no comando /{cmd}: {exc}")

    def _ntfy_send_help(self) -> None:
        """Manda lista de comandos disponíveis pro celular."""
        allowed = self._ntfy.get_allowed_cmds()
        lines = ["📋 Comandos disponíveis:"]
        descs = [
            ("run",    "/run [N|nome]  iniciar macro (atual / slot N / por nome)"),
            ("stop",   "/stop          parar tudo"),
            ("pause",  "/pause         pausar macro"),
            ("resume", "/resume        retomar pausa"),
            ("status", "/status        ver estado atual"),
            ("screen", "/screen        receber screenshot"),
            ("help",   "/help          esta lista"),
        ]
        for key, line in descs:
            if key in allowed:
                lines.append(line)
        self._ntfy.publish("\n".join(lines), title="AutoClick — Ajuda", priority=2)

    def _ntfy_run_macro(self, arg: str) -> None:
        """Inicia macro. arg pode ser vazio (atual), "1/2/3" (slot) ou nome do slot."""
        # Estado inconsistente: _macro_running=True mas runner já morreu (ex:
        # macro terminou mas o callback on_stop não rodou). Conserta antes de
        # tentar iniciar pra evitar "já está rodando" eterno.
        runner = self._macro_runner.get_sequential_runner()
        if self._macro_running and not runner.is_running:
            self._macro_running = False

        if not arg:
            if self._macro_running:
                self._ntfy.publish("ℹ Macro já está rodando", priority=2)
                return
            self._start_macro()
            if self._macro_running:
                self._ntfy.publish("▶ Macro iniciado", priority=2)
            else:
                self._ntfy.publish(
                    "⚠ Não consegui iniciar. Verifique se há steps no macro atual.",
                    priority=3)
            return
        # Resolve slot por número ou por nome
        slot_idx = None
        try:
            n = int(arg)
            if 1 <= n <= 3:
                slot_idx = n
        except ValueError:
            for i, var in enumerate(self.var_slot_names, start=1):
                if var.get().strip().lower() == arg.strip().lower():
                    slot_idx = i
                    break
        if slot_idx is None:
            available = [f"{i+1}:{v.get() or '(vazio)'}"
                         for i, v in enumerate(self.var_slot_names)]
            self._ntfy.publish(
                f"❌ Slot '{arg}' não encontrado.\nDisponíveis: " + ", ".join(available),
                priority=3)
            return
        if self._macro_running:
            self._stop_macro()
        self._load_slot(slot_idx)
        self._start_macro()
        name = self.var_slot_names[slot_idx - 1].get() or f"Slot {slot_idx}"
        if self._macro_running:
            self._ntfy.publish(f"▶ Iniciei: {name}", priority=2)
        else:
            self._ntfy.publish(
                f"⚠ Carreguei '{name}' mas não consegui iniciar (slot vazio?)",
                priority=3)

    # ── CRUD de monitores (acionado pelos botões da aba) ─────────
    def _mon_add(self) -> None:
        dlg = MonitorDialog(self, T, driver=self._driver)
        self.wait_window(dlg)
        if dlg.result:
            monitors = self._ntfy.get_monitors()
            monitors.append(dlg.result)
            self._ntfy.set_monitors(monitors)
            self._ntfy_save()
            self._refresh_mon_tree()

    def _mon_edit(self) -> None:
        sel = self.mon_tree.selection()
        if not sel:
            return
        idx = self.mon_tree.index(sel[0])
        monitors = self._ntfy.get_monitors()
        if not (0 <= idx < len(monitors)):
            return
        dlg = MonitorDialog(self, T, driver=self._driver, monitor=monitors[idx])
        self.wait_window(dlg)
        if dlg.result:
            monitors[idx] = dlg.result
            self._ntfy.set_monitors(monitors)
            self._ntfy_save()
            self._refresh_mon_tree()

    def _mon_remove(self) -> None:
        sel = self.mon_tree.selection()
        if not sel:
            return
        idx = self.mon_tree.index(sel[0])
        monitors = self._ntfy.get_monitors()
        if 0 <= idx < len(monitors):
            del monitors[idx]
            self._ntfy.set_monitors(monitors)
            self._ntfy_save()
            self._refresh_mon_tree()

    # ─────────────────────────────────────────────────────────────
    # ABA: CONFIGURAÇÕES
    # ─────────────────────────────────────────────────────────────
    def _build_settings_tab(self) -> None:
        p = self._make_scrollable(self.tab_cfg)

        # Hotkeys
        self._section(p, "Teclas de Atalho (Hotkeys)", "⌨ ").pack(fill="x", padx=8, pady=(10, 3))
        hk_frame = tk.Frame(p, bg=T["bg"])
        hk_frame.pack(fill="x", padx=14, pady=(2, 6))

        self._lbl_hk = {}
        for i, (desc, var, key) in enumerate([
            ("Iniciar AutoClick:", self.var_hk_clk,   "clk"),
            ("Iniciar AutoKey:",   self.var_hk_key,   "key"),
            ("Executar Macro:",    self.var_hk_macro,  "macro"),
            ("Pausar/Retomar Macro:", self.var_hk_pause, "pause"),
            ("Gravar/Parar Macro:", self.var_hk_rec,  "rec"),
            ("Parar Tudo:",        self.var_hk_stop,  "stop"),
        ]):
            tk.Label(hk_frame, text=desc, bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10), width=20, anchor="w").grid(row=i, column=0, pady=3)
            lbl = tk.Label(hk_frame, text=var.get().upper(),
                           bg=T["card"], fg=T["text"],
                           font=("Consolas", 10, "bold"), padx=10, pady=2, width=8,
                           highlightbackground=T["line_2"], highlightthickness=1)
            lbl.grid(row=i, column=1, padx=8)
            self._lbl_hk[key] = lbl
            self._btn(hk_frame, "Alterar",
                      lambda v=var, l=lbl: self._listen_for_hotkey(v, l),
                      bg=T["card"], fg=T["text"], padx=8).grid(row=i, column=2)

        # Sound
        self._section(p, "Som de Feedback", "🔊 ").pack(fill="x", padx=8, pady=(6, 3))
        srow = tk.Frame(p, bg=T["bg"]); srow.pack(fill="x", padx=14, pady=(2, 6))
        tk.Checkbutton(srow, text="Som a cada clique  (intervalo ≥ 50ms)",
                       variable=self.var_sound,
                       bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                       activebackground=T["bg"],
                       font=("Segoe UI", 10)).pack(side="left")
        self._btn(srow, "▶ Testar", self._play_tick,
                  bg=T["card"], fg=T["text"], padx=8).pack(side="left", padx=8)

        # Profiles
        self._section(p, "Perfis (Salvar / Carregar)", "💾 ").pack(fill="x", padx=8, pady=(6, 3))
        for slot in range(1, 4):
            sr = tk.Frame(p, bg=T["bg"]); sr.pack(fill="x", padx=14, pady=3)
            tk.Label(sr, text=f"Slot {slot}:", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10, "bold"), width=6, anchor="w").pack(side="left")
            self._btn(sr, "💾 Salvar", lambda s=slot: self._save_slot(s),
                      bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
            self._btn(sr, "📂 Carregar", lambda s=slot: self._load_slot(s),
                      bg=T["card"], fg=T["text"], padx=10).pack(side="left", padx=4)
            tk.Label(sr, text="Nome:", bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
            tk.Entry(sr, textvariable=self.var_slot_names[slot - 1], width=14,
                     bg=T["card"], fg=T["text"], insertbackground=T["text"],
                     font=("Consolas", 10), relief="flat", bd=3).pack(side="left")

        frow = tk.Frame(p, bg=T["bg"]); frow.pack(fill="x", padx=14, pady=(6, 8))
        self._btn(frow, "💾 Salvar em Arquivo...", self._save_file,
                  bg=T["card"], fg=T["text"], bold=False, padx=10).pack(side="left", padx=(0, 6))
        self._btn(frow, "📂 Carregar de Arquivo...", self._load_file,
                  bg=T["card"], fg=T["text"], bold=False, padx=10).pack(side="left")

        # About
        self._section(p, "Sobre", "ℹ ").pack(fill="x", padx=8, pady=(6, 3))
        tk.Label(p,
                 text="AutoClick Pro  •  100% gratuito e open source\n"
                      "Python + tkinter + pyautogui + keyboard\n"
                      "Mover mouse para canto superior esquerdo = parada de emergência",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=16, pady=4)

        # Apoiar o projeto (PIX)
        self._section(p, "Apoie o projeto", "❤ ").pack(fill="x", padx=8, pady=(12, 3))
        tk.Label(p,
                 text=("Mantenho esse app sozinho nas horas livres.\n"
                       "Se ajudou, qualquer valor via PIX é muito bem-vindo. 💜"),
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=16, pady=(4, 6))
        donate_row = tk.Frame(p, bg=T["bg"])
        donate_row.pack(fill="x", padx=14, pady=(0, 8))
        self._btn(donate_row, "❤  Apoiar via PIX", self._show_donate_dialog,
                  bg=T["accent"], fg="#ffffff", bold=True, padx=14, pady=6
                  ).pack(side="left")

        # Desinstalar
        self._section(p, "Desinstalar", "🗑 ").pack(fill="x", padx=8, pady=(12, 3))
        tk.Label(p,
                 text="Remove o app, todos os atalhos e arquivos de configuração.\n"
                      "Esta ação é irreversível — pede confirmação dupla antes de executar.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=16, pady=(4, 6))
        uninst_row = tk.Frame(p, bg=T["bg"])
        uninst_row.pack(fill="x", padx=14, pady=(0, 12))
        self._btn(uninst_row, "🗑  Desinstalar AutoClick Pro", self._uninstall_app,
                  bg=T["red"], fg="#ffffff", bold=True, padx=14, pady=6).pack(side="left")

    # ─────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────
    def _make_scrollable(self, outer: tk.Frame) -> tk.Frame:
        """Envolve `outer` em um Canvas+Scrollbar verticais e retorna o frame interno.

        Comportamento:
          - Mouse wheel rola enquanto o cursor está sobre o canvas
          - Treeviews internos têm wheel scrolling próprio (Tk default) — não conflita
          - Frame interno acompanha a largura do canvas (cresce horizontalmente)
        """
        canvas = tk.Canvas(outer, bg=T["bg"], highlightthickness=0)
        vsb    = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg=T["bg"])
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
        return inner

    def _section(self, parent, title: str, icon: str = "") -> tk.Frame:
        # Estilo Discord: bullet blurple ● + título uppercase + linha separadora
        f = tk.Frame(parent, bg=T["bg"])
        head = tk.Frame(f, bg=T["bg"])
        head.pack(fill="x")
        # Bullet blurple (caractere ● Unicode)
        tk.Label(head, text="●", bg=T["bg"], fg=T["accent"],
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(2, 7), pady=(2, 0))
        tk.Label(head, text=title.upper(), bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(
                 side="left", fill="x", expand=True, pady=(2, 2))
        # Linha fina inferior
        tk.Frame(f, bg=T["line"], height=1).pack(fill="x", pady=(0, 0))
        return f

    def _set_status(self, msg: str) -> None:
        self.lbl_status.config(text=msg)
        if msg.startswith(("🖱", "⌨", "▶")):
            self._status_dot.config(fg=T["green"])
        elif msg.startswith(("⏹", "🛑")):
            self._status_dot.config(fg=T["red"])
        elif msg.startswith("⏳"):
            self._status_dot.config(fg=T["accent2"])
        elif msg.startswith("✅"):
            self._status_dot.config(fg=T["green"])
        elif msg.startswith("⚠"):
            self._status_dot.config(fg=T["accent2"])
        else:
            self._status_dot.config(fg=T["subtext"])

    def _fmt_time(self, secs: float) -> str:
        s = int(secs)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

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
        """Abre diálogo com lista de todas as janelas abertas para o usuário escolher."""
        import ctypes
        windows: list[tuple[int, str]] = []

        def _enum_cb(hwnd, _):
            user32 = ctypes.windll.user32
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.strip()
            if title and title != "AutoClick Pro":
                windows.append((hwnd, title))
            return True

        cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(cb_type(_enum_cb), 0)
        windows.sort(key=lambda w: w[1].lower())

        if not windows:
            self._set_status("⚠  Nenhuma janela encontrada.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Selecionar Janela Alvo")
        dlg.configure(bg=T["bg"])
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.attributes("-topmost", True)

        tk.Label(dlg, text="Escolha a janela onde o autoclicker vai clicar:",
                 bg=T["bg"], fg=T["text"], font=("Segoe UI", 10)).pack(padx=16, pady=(12, 6), anchor="w")

        frame = tk.Frame(dlg, bg=T["bg"])
        frame.pack(padx=16, fill="both", expand=True)

        sb = tk.Scrollbar(frame)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(frame, yscrollcommand=sb.set, bg=T["card"], fg=T["text"],
                        selectbackground=T["accent"], font=("Segoe UI", 10),
                        width=52, height=14, relief="flat", bd=0,
                        activestyle="none")
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        for _, title in windows:
            lb.insert("end", title)

        # Selecionar a primeira por padrão
        if windows:
            lb.selection_set(0)
            lb.activate(0)

        def _confirm():
            sel = lb.curselection()
            if not sel:
                return
            hwnd, title = windows[sel[0]]
            self._target_hwnd = hwnd
            self._target_win_name = title
            display = (title[:32] + "…") if len(title) > 32 else title
            self._lbl_target_win.config(text=display, fg=T["text"])
            self.var_target_window.set(True)
            self._set_status(f"🎯  Janela alvo: {title}")
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=T["bg"])
        btn_row.pack(pady=10)
        self._btn(btn_row, "Selecionar", _confirm,
                  bg=T["text"], fg=T["bg"], bold=True, padx=16).pack(side="left", padx=6)
        self._btn(btn_row, "Cancelar", dlg.destroy,
                  bg=T["card"], fg=T["text"], padx=12).pack(side="left")

        lb.bind("<Double-1>", lambda e: _confirm())
        dlg.bind("<Return>", lambda e: _confirm())
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _clear_target_window(self) -> None:
        self._target_hwnd = 0
        self._target_win_name = ""
        self._lbl_target_win.config(text="Nenhuma janela selecionada", fg=T["subtext"])
        self.var_target_window.set(False)

    # ─────────────────────────────────────────────────────────────
    # AUTO KEYBOARD
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
        type_loop.start()

    def _stop_typing(self) -> None:
        self._macro_runner.get_type_loop().stop()
        self._type_running = False
        self._stop_pulse(self.key_btn)
        self.key_btn.config(bg=T["accent"], fg="#ffffff")
        self.key_btn_var.set("▶  START AUTOKEYBOARD   F7")
        self._set_pill(self._pill_key, False)
        self._set_status("⏹  autokeyboard parado.")

    # ─────────────────────────────────────────────────────────────
    # STOP ALL
    # ─────────────────────────────────────────────────────────────
    def stop_all(self) -> None:
        if self._recorder_running:
            self._macro_stop_recording()
            return  # parar gravação é a ação prioritária; não para execuções
        if self._click_running:
            self._stop_clicking()
        if self._type_running:
            self._stop_typing()
        if self._macro_running:
            self._stop_macro()
        self._set_status("🛑  Tudo parado (F8).")

    # ─────────────────────────────────────────────────────────────
    # HOTKEYS
    # ─────────────────────────────────────────────────────────────
    def _init_hotkeys(self) -> None:
        self._rebind_hotkeys()

    def _rebind_hotkeys(self) -> None:
        # Remove apenas hotkeys conhecidos — NÃO chama unhook_all (mataria
        # outros hooks como o das hotstrings)
        for h in getattr(self, "_hk_handles", []):
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hk_handles = []
        def _add(key: str, callback) -> None:
            if not key:
                return
            try:
                self._hk_handles.append(keyboard.add_hotkey(key, callback))
            except Exception:
                pass
        _add(self.var_hk_clk.get(),   lambda: self.after(0, self.toggle_clicking))
        _add(self.var_hk_key.get(),   lambda: self.after(0, self.toggle_typing))
        _add(self.var_hk_macro.get(), lambda: self.after(0, self.toggle_macro))
        _add(self.var_hk_pause.get(), lambda: self.after(0, self._toggle_pause))
        _add(self.var_hk_rec.get(),   lambda: self.after(0, self._macro_toggle_recording))
        _add(self.var_hk_stop.get(),  lambda: self.after(0, self.stop_all))

    def _listen_for_hotkey(self, var: tk.StringVar, label: tk.Label) -> None:
        label.config(text="...", bg=T["card"], fg=T["red"],
                     highlightbackground=T["red"])
        if self._hk_capture_hook:
            try:
                keyboard.unhook(self._hk_capture_hook)
            except Exception:
                pass
            self._hk_capture_hook = None

        def _capture(e) -> None:
            if e.event_type != "down":
                return
            var.set(e.name)
            label.config(text=e.name.upper(), bg=T["card"], fg=T["text"],
                         highlightbackground=T["line_2"])
            try:
                keyboard.unhook(self._hk_capture_hook)
            except Exception:
                pass
            self._hk_capture_hook = None
            self._rebind_hotkeys()

        self._hk_capture_hook = keyboard.hook(_capture)

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
    # PROFILES — slots e arquivos
    # ─────────────────────────────────────────────────────────────
    def _atomic_write_json(self, path: str, data: dict) -> None:
        """Escreve JSON de forma atômica: tmp + os.replace.

        Evita corrupção se o processo morrer no meio da escrita — o arquivo
        final só é trocado quando o conteúdo está 100% no disco.
        """
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _save_slot(self, slot: int) -> None:
        os.makedirs(os.path.join(_ROOT, "profiles"), exist_ok=True)
        path = os.path.join(_ROOT, "profiles", f"slot{slot}.json")
        data = profile_to_dict(self._collect_script(), self._collect_ui_profile())
        name = self.var_slot_names[slot - 1].get()
        data["slot_name"] = name
        try:
            self._atomic_write_json(path, data)
        except OSError as e:
            self._set_status(f"❌  Erro ao salvar Slot {slot}: {e}")
            return
        label = f" \"{name}\"" if name else ""
        self._set_status(f"✅  Perfil salvo no Slot {slot}{label}.")

    def _load_slot(self, slot: int) -> None:
        path = os.path.join(_ROOT, "profiles", f"slot{slot}.json")
        if not os.path.exists(path):
            self._set_status(f"⚠  Slot {slot} está vazio.")
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self._apply_script(script_from_dict(d))
            self._apply_ui_profile(ui_from_dict(d))
            self.var_slot_names[slot - 1].set(d.get("slot_name", ""))
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as e:
            self._set_status(f"❌  Slot {slot} corrompido ou inválido ({type(e).__name__}). Não carregado.")
            return
        self._set_status(f"📂  Perfil carregado do Slot {slot}.")

    def _save_file(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Salvar perfil")
        if path:
            data = profile_to_dict(self._collect_script(), self._collect_ui_profile())
            try:
                self._atomic_write_json(path, data)
            except OSError as e:
                self._set_status(f"❌  Erro ao salvar: {e}")
                return
            self._set_status(f"✅  Perfil salvo em {os.path.basename(path)}.")

    def _load_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            title="Carregar perfil")
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                self._apply_script(script_from_dict(d))
                self._apply_ui_profile(ui_from_dict(d))
            except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as e:
                self._set_status(f"❌  Arquivo inválido ({type(e).__name__}). Não carregado.")
                return
            self._set_status(f"📂  Perfil carregado de {os.path.basename(path)}.")

    # ─────────────────────────────────────────────────────────────
    # SOUND
    # ─────────────────────────────────────────────────────────────
    def _generate_tick_wav(self) -> None:
        assets_dir = os.path.join(_ROOT, "assets")
        path       = os.path.join(assets_dir, "tick.wav")
        if os.path.exists(path):
            self._tick_wav_path = path
            return
        try:
            os.makedirs(assets_dir, exist_ok=True)
            sample_rate = 22050
            n_samples   = int(sample_rate * 0.03)
            data = bytearray()
            for i in range(n_samples):
                envelope = 1.0 - (i / n_samples)
                val = int(20000 * envelope * math.sin(2 * math.pi * 880 * i / sample_rate))
                data += struct.pack("<h", val)
            with wave.open(path, "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(bytes(data))
            self._tick_wav_path = path
        except Exception:
            self._tick_wav_path = None

    def _play_tick(self) -> None:
        try:
            import winsound
            if self._tick_wav_path and os.path.exists(self._tick_wav_path):
                winsound.PlaySound(
                    self._tick_wav_path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            else:
                winsound.Beep(880, 20)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # TRAY ICON
    # ─────────────────────────────────────────────────────────────
    def _init_tray(self) -> None:
        if not HAS_TRAY:
            return
        try:
            img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([4, 4, 60, 60], fill=(108, 99, 255, 255))
            draw.ellipse([22, 22, 42, 42], fill=(255, 255, 255, 200))

            menu = pystray.Menu(
                pystray.MenuItem("Mostrar AutoClick Pro", self._tray_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Iniciar Clicker", lambda i, it: self.after(0, self._start_clicking)),
                pystray.MenuItem("Parar Tudo",      lambda i, it: self.after(0, self.stop_all)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair",            self._tray_quit),
            )
            self._tray = pystray.Icon("AutoClickPro", img, "AutoClick Pro", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception:
            self._tray = None

    def _tray_show(self, icon=None, item=None) -> None:
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _tray_quit(self, icon=None, item=None) -> None:
        self.after(0, self._quit_app)

    # ─────────────────────────────────────────────────────────────
    # QUIT / CLOSE
    # ─────────────────────────────────────────────────────────────
    def _on_close(self) -> None:
        if HAS_TRAY and self._tray:
            self.withdraw()
            if not self._tray_notified:
                self._tray_notified = True
                try:
                    self._tray.notify("AutoClick Pro está rodando na bandeja do sistema.")
                except Exception:
                    pass
        else:
            self._quit_app()

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
        """Destaca o step atual no Treeview durante a execução."""
        items = self.macro_tree.get_children()
        if 0 <= idx < len(items):
            self.macro_tree.selection_set(items[idx])
            self.macro_tree.see(items[idx])

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
        if self._debug_event is not None and self._macro_running:
            total = len(self._macro_steps)
            self._set_status(f"⏸  Step {idx + 1}/{total} — clique ⏭ para continuar")
            try:
                self.debug_next_btn.config(state="normal")
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # MACRO — edição de steps
    # ─────────────────────────────────────────────────────────────
    def _macro_add_step(self) -> None:
        dlg = StepDialog(self, T, driver=self._driver)
        self.wait_window(dlg)
        if dlg.result:
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
            self._macro_steps.pop(idx)
            self._macro_refresh_tree()

    def _macro_move_up(self) -> None:
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if idx > 0:
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
            self._macro_steps[idx], self._macro_steps[idx + 1] = \
                self._macro_steps[idx + 1], self._macro_steps[idx]
            self._macro_refresh_tree()
            items = self.macro_tree.get_children()
            self.macro_tree.selection_set(items[idx + 1])

    def _macro_duplicate_step(self) -> None:
        import copy
        sel = self.macro_tree.selection()
        if not sel:
            return
        idx = self.macro_tree.index(sel[0])
        if 0 <= idx < len(self._macro_steps):
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
        self._macro_steps.clear()
        self._macro_refresh_tree()

    def _macro_refresh_tree(self) -> None:
        for item in self.macro_tree.get_children():
            self.macro_tree.delete(item)
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

    # ─────────────────────────────────────────────────────────────
    # ÍCONE DA JANELA
    # ─────────────────────────────────────────────────────────────
    def _generate_icon_ico(self) -> None:
        """Gera assets/icon.ico se não existir e aplica na janela."""
        icon_path = os.path.join(_ROOT, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            try:
                from core.icon_gen import generate_icon_ico
                generate_icon_ico(icon_path)
            except Exception:
                pass
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────
    # GEOMETRIA DA JANELA
    # ─────────────────────────────────────────────────────────────
    def _save_window_geometry(self) -> None:
        """Salva posição + tamanho da janela em profiles/window.json."""
        try:
            path = os.path.join(_ROOT, "profiles", "window.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # Se estiver em fullscreen, não persistir esse estado — salva último tamanho normal
            if self._is_fullscreen:
                w, h = self._pre_fs_size
                x, y = self._pre_fs_pos
            else:
                w, h = self.winfo_width(), self.winfo_height()
                x, y = self.winfo_x(), self.winfo_y()
            data = {"x": x, "y": y, "w": w, "h": h, "theme": self._current_theme}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _restore_window_geometry(self) -> None:
        """Restaura posição + tamanho + tema de profiles/window.json, se disponível."""
        try:
            path = os.path.join(_ROOT, "profiles", "window.json")
            if not os.path.exists(path):
                return
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            x, y = data.get("x", 0), data.get("y", 0)
            w, h = data.get("w", 660), data.get("h", 780)
            saved_theme = data.get("theme", "dark")
            # Clamp para tela atual + respeitar min size
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w = max(560, min(w, sw))
            h = max(600, min(h, sh))
            if 0 <= x <= sw - 100 and 0 <= y <= sh - 50:
                self.geometry(f"{w}x{h}+{x}+{y}")
            # Aplicar tema salvo se diferente do default (dark)
            if saved_theme == "light" and self._current_theme == "dark":
                self._toggle_theme()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # FULLSCREEN
    # ─────────────────────────────────────────────────────────────
    def _toggle_fullscreen(self) -> None:
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self) -> None:
        if self._is_fullscreen:
            return
        # Salvar tamanho/pos atuais pra restaurar ao sair
        self._pre_fs_size = (self.winfo_width(), self.winfo_height())
        self._pre_fs_pos  = (self.winfo_x(),    self.winfo_y())
        self.attributes("-fullscreen", True)
        self._is_fullscreen = True

    def _exit_fullscreen(self) -> None:
        if not self._is_fullscreen:
            return
        self.attributes("-fullscreen", False)
        self._is_fullscreen = False
        # Restaurar tamanho anterior (Windows às vezes não restaura sozinho)
        try:
            w, h = self._pre_fs_size
            x, y = self._pre_fs_pos
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # TEMA (toggle claro/escuro)
    # ─────────────────────────────────────────────────────────────
    def _toggle_theme(self) -> None:
        """Alterna entre tema claro e escuro. Reconstrói UI preservando estado."""
        # 1. Salvar estado da UI que não está em instance vars
        text_content = ""
        try:
            if hasattr(self, "type_text") and self.type_text:
                text_content = self.type_text.get("1.0", "end-1c")
        except Exception:
            pass
        # Tab ativa
        try:
            current_tab = self._nb.index("current") if hasattr(self, "_nb") else 0
        except Exception:
            current_tab = 0

        # 2. Trocar tema
        new_theme = "light" if self._current_theme == "dark" else "dark"
        T.clear()
        T.update(THEME_LIGHT if new_theme == "light" else THEME_DARK)
        self._current_theme = new_theme

        # 3. Atualizar bg da raiz e titlebar
        self.configure(bg=T["bg"])
        try:
            self._driver.set_dark_mode(self.winfo_id(), enable=(new_theme == "dark"))
        except TypeError:
            # set_dark_mode talvez não aceite arg `enable` — fallback silencioso
            try:
                if new_theme == "dark":
                    self._driver.set_dark_mode(self.winfo_id())
            except Exception:
                pass
        except Exception:
            pass

        # 4. Destruir e reconstruir UI
        for child in list(self.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        self._init_style()
        self._build_ui()

        # 5. Restaurar estado da UI
        try:
            if text_content and hasattr(self, "type_text"):
                self.type_text.delete("1.0", "end")
                self.type_text.insert("1.0", text_content)
        except Exception:
            pass
        # Restaurar conteúdo dos treeviews (a partir das listas em memória)
        try:
            for pos in self._seq_positions:
                self.seq_tree.insert("", "end",
                    values=(pos.get("x", 0), pos.get("y", 0), pos.get("delay_ms", 0)))
        except Exception:
            pass
        try:
            self._macro_refresh_tree()
        except Exception:
            pass
        # Restaurar aba ativa
        try:
            if hasattr(self, "_nb"):
                self._nb.select(current_tab)
        except Exception:
            pass
        # Restaurar estado visual dos botões de Start/Stop e pills
        try:
            if self._click_running:
                self.click_btn.config(bg=T["red"], fg="#ffffff")
                self.click_btn_var.set("⏹  STOP AUTOCLICK   F6")
                self._set_pill(self._pill_clk, True, T["green"])
                self._start_pulse(self.click_btn)
            if self._type_running:
                self.key_btn.config(bg=T["red"], fg="#ffffff")
                self.key_btn_var.set("⏹  STOP AUTOKEYBOARD   F7")
                self._set_pill(self._pill_key, True, T["green"])
                self._start_pulse(self.key_btn)
            if self._macro_running:
                self.macro_btn.config(bg=T["red"], fg="#ffffff")
                self.macro_btn_var.set("⏹  STOP MACRO   F9")
                self._set_pill(self._pill_mcr, True, T["green"])
                self._start_pulse(self.macro_btn)
            if self._recorder_running:
                self._set_pill(self._pill_rec, True, T["red"])
        except Exception:
            pass

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

    def _warn_missing_deps(self) -> None:
        """Verifica dependências críticas no startup e avisa via status bar."""
        missing = []
        try:
            if not self._driver.has_opencv():
                missing.append("opencv-python (image_click/if_image)")
        except Exception:
            pass
        try:
            if not self._driver.has_tesseract():
                missing.append("Tesseract OCR (ocr_read)")
        except Exception:
            pass
        if missing:
            msg = "⚠  Dependências faltando: " + " • ".join(missing)
            self.after(800, lambda m=msg: self._set_status(m))

    def _show_donate_dialog(self) -> None:
        """Mostra diálogo com chave PIX e botão de copiar para clipboard."""
        dlg = tk.Toplevel(self)
        dlg.title("Apoiar via PIX")
        dlg.configure(bg=T["bg"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        # Header
        head = tk.Frame(dlg, bg=T["bg"])
        head.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(head, text="❤  Apoie o AutoClick Pro", bg=T["bg"], fg=T["accent"],
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(head, text="Cada PIX ajuda a manter o app vivo e melhorando.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 10)
                 ).pack(anchor="w", pady=(2, 0))

        # Separador
        tk.Frame(dlg, bg=T["line"], height=1).pack(fill="x", padx=24, pady=(8, 12))

        # Container info
        info = tk.Frame(dlg, bg=T["bg"])
        info.pack(fill="x", padx=24)

        tk.Label(info, text="Recebido por:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(info, text=PIX_OWNER, bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        tk.Label(info, text="Chave PIX:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        key_box = tk.Entry(info, font=("Consolas", 11),
                            bg=T["card"], fg=T["text"],
                            insertbackground=T["text"],
                            relief="flat", bd=6, justify="center", readonlybackground=T["card"])
        key_box.insert(0, PIX_KEY)
        key_box.config(state="readonly")
        key_box.pack(fill="x", pady=(2, 12))

        # Status de cópia (vazio inicial)
        status_lbl = tk.Label(info, text="", bg=T["bg"], fg=T["green"],
                               font=("Segoe UI", 9, "bold"))
        status_lbl.pack(anchor="w", pady=(0, 4))

        def _copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(PIX_KEY)
                self.update()
                status_lbl.config(text="✓  Chave copiada! Cole no app do seu banco.",
                                  fg=T["green"])
            except Exception as exc:
                status_lbl.config(text=f"Erro: {exc}", fg=T["red"])

        # Botões
        btns = tk.Frame(dlg, bg=T["bg"])
        btns.pack(fill="x", padx=24, pady=(4, 18))
        self._btn(btns, "📋  Copiar chave PIX", _copy,
                  bg=T["accent"], fg="#ffffff", bold=True, padx=14, pady=6
                  ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._btn(btns, "Fechar", dlg.destroy,
                  bg=T["card"], fg=T["text"], padx=14, pady=6).pack(side="left")

        # Hint pé do diálogo
        tk.Label(dlg, text="No app do seu banco: PIX → Pix Copia e Cola (ou chave PIX) → colar",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(pady=(0, 14), padx=24)

        # Centraliza
        dlg.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - dlg.winfo_width())  // 2
        py = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{px}+{py}")

    def _uninstall_app(self) -> None:
        """Desinstala o app com confirmação dupla.

        Localiza desinstalar.bat em %LOCALAPPDATA%\\AutoClickPro\\, para todas as
        automações, lança o .bat desacoplado com delay de 2s (pra deixar o
        processo Python encerrar antes do rmdir), e fecha o app.
        """
        import subprocess

        # Primeira confirmação — explica o que será removido
        if not messagebox.askyesno(
            "Desinstalar AutoClick Pro",
            "Tem certeza que deseja desinstalar o AutoClick Pro?\n\n"
            "Isso vai remover:\n"
            "  •  Todos os arquivos do programa\n"
            "  •  Atalhos da Área de Trabalho e Menu Iniciar\n"
            "  •  Todas as suas configurações e perfis salvos\n\n"
            "O Tesseract OCR (instalado separadamente) NÃO será removido.",
            icon="warning",
            parent=self,
        ):
            return

        # Segunda confirmação — texto mais firme
        if not messagebox.askyesno(
            "Última chance",
            "Esta ação é IRREVERSÍVEL.\n\n"
            "Todos os seus macros gravados, perfis salvos e configurações\n"
            "serão perdidos permanentemente.\n\n"
            "Deseja mesmo continuar?",
            icon="warning",
            parent=self,
        ):
            return

        # Localizar desinstalar.bat
        local_app = os.environ.get("LOCALAPPDATA", "")
        install_dir = os.path.join(local_app, "AutoClickPro")
        uninstall_bat = os.path.join(install_dir, "desinstalar.bat")

        if not os.path.exists(uninstall_bat):
            messagebox.showerror(
                "Desinstalador não encontrado",
                f"O arquivo 'desinstalar.bat' não foi encontrado em:\n{install_dir}\n\n"
                "Isso geralmente significa que o app está rodando direto da pasta\n"
                "do projeto (modo dev), sem ter passado pelo 'instalar.bat'.\n\n"
                "Pra remover manualmente, apague a pasta do projeto.",
                parent=self,
            )
            return

        # Para todas as automações em curso (cliques, teclado, macro, gravador)
        try:
            if self._click_running:    self._stop_clicking()
            if self._type_running:     self._stop_typing()
            if self._macro_running:    self._stop_macro()
            if self._recorder_running: self._macro_toggle_recording()
        except Exception:
            pass

        # Remove atalhos (.lnk) antes de lançar o .bat — Python tem acesso melhor
        # aos caminhos %USERPROFILE%/%APPDATA% e o .bat foca só no rmdir
        appdata     = os.environ.get("APPDATA", "")
        userprofile = os.environ.get("USERPROFILE", "")
        shortcut_paths = [
            # Desktop
            os.path.join(userprofile, "Desktop", "AutoClick Pro.lnk"),
            os.path.join(userprofile, "OneDrive", "Desktop", "AutoClick Pro.lnk"),  # OneDrive sync
            # Menu Iniciar
            os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "AutoClick Pro.lnk"),
            # Barra de tarefas (pinned)
            os.path.join(appdata, "Microsoft", "Internet Explorer",
                          "Quick Launch", "User Pinned", "TaskBar", "AutoClick Pro.lnk"),
            # Quick Launch (legacy)
            os.path.join(appdata, "Microsoft", "Internet Explorer",
                          "Quick Launch", "AutoClick Pro.lnk"),
        ]
        for p in shortcut_paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass  # Permissão negada ou em uso — o .bat tenta de novo depois

        # Salva geometria/tema antes de morrer
        try:
            self._save_window_geometry()
        except Exception:
            pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self._tray:
            try: self._tray.stop()
            except Exception: pass

        # Lança o desinstalador em nova janela, com 2s de delay pro python sair
        # antes da tentativa de rmdir. `start` desacopla totalmente do processo pai.
        try:
            subprocess.Popen(
                f'start "AutoClick Pro - Desinstalador" cmd /c '
                f'"timeout /t 2 /nobreak >nul && \"{uninstall_bat}\""',
                shell=True,
                cwd=install_dir,
            )
        except Exception as exc:
            messagebox.showerror("Erro ao desinstalar",
                                  f"Não foi possível iniciar o desinstalador:\n{exc}",
                                  parent=self)
            return

        # Fecha o app — o .bat vai esperar 2s e depois apagar tudo
        self.destroy()

    def _quit_app(self) -> None:
        self._save_window_geometry()
        self.stop_all()
        try:
            self._hotstrings.stop()
        except Exception:
            pass
        try:
            self._ntfy.stop()
        except Exception:
            pass
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()


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


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import traceback
    _log = os.path.join(_ROOT, "error.log")
    try:
        app = AutoClickPro()
        app.mainloop()
    except Exception:
        with open(_log, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
