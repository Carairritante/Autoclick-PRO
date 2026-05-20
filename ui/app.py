"""
ui/app.py — Interface gráfica do AutoClick Pro.

Importa de core/ para toda lógica de automação e acesso ao WinAPI.
Este arquivo contém apenas código tkinter e orquestração de UI.
"""
from __future__ import annotations

import collections
import json
import math
import os
import struct
import threading
import wave
from tkinter import ttk
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
from core.ntfy_client import NtfyClient
from core.paths import HOTSTRINGS_PATH, NTFY_CONFIG_PATH, ONBOARDING_PATH, SCHEDULER_PATH
from core.recorder import MacroRecorder
from core.macro_schema import MacroStep, StopCondition
from core.scheduler import SchedulerWorker
from ui.tabs.ai_assistant import AIAssistantMixin
from ui.tabs.click import ClickMixin
from ui.tabs.hotstrings import HotstringTabMixin
from ui.tabs.keyboard import KeyboardMixin
from ui.tabs.macro import MacroMixin
from ui.tabs.monitor import MonitorMixin
from ui.tabs.scheduler import SchedulerMixin
from ui.tabs.settings import SettingsMixin
from ui.theme import T, THEME_DARK, THEME_LIGHT
from ui.widgets import make_button

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0
pyautogui.MINIMUM_DURATION = 0

# Caminho raiz do projeto (um nível acima de ui/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class AutoClickPro(
    ClickMixin,
    KeyboardMixin,
    MacroMixin,
    HotstringTabMixin,
    MonitorMixin,
    SchedulerMixin,
    AIAssistantMixin,
    SettingsMixin,
    tk.Tk,
):
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
        self._undo_stack: list[list] = []
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

        # Agendador (worker em background — dispara macros em horários marcados)
        self._scheduler = SchedulerWorker()
        # Quando worker dispara regra, chama _fire_schedule na main thread
        self._scheduler.on_fire = lambda rule: self.after(
            0, lambda r=rule: self._fire_schedule(r)
        )

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
        # Monitor → notificação na bandeja do PC (via tray). after() pra rodar
        # na thread main. Silencioso se tray não foi inicializado (sem PIL).
        self._ntfy.on_pc_notify = lambda msg, title: self.after(
            0, lambda m=msg, t=title:
                (self._tray.notify(m, t) if self._tray else None)
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
        self._generate_icon_ico()
        self._init_tray()
        self._warn_missing_deps()
        self._generate_tick_wav()
        self._hotstrings.load(HOTSTRINGS_PATH)
        self._refresh_hs_tree()
        self._scheduler.load(SCHEDULER_PATH)
        self._refresh_sched_tree()
        self._scheduler.start()
        self._restore_window_geometry()

        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        # Wizard de boas-vindas (só na primeira execução). Atrasa 400ms
        # pra UI principal terminar de renderizar antes do modal abrir.
        self._maybe_show_welcome()

    # ─────────────────────────────────────────────────────────────
    # WIZARD / TEMPLATES
    # ─────────────────────────────────────────────────────────────
    def _maybe_show_welcome(self) -> None:
        """Se primeira execução, agenda abertura da galeria em modo welcome."""
        try:
            if os.path.exists(ONBOARDING_PATH):
                with open(ONBOARDING_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("completed"):
                    return
        except (OSError, ValueError):
            pass  # arquivo inválido/ausente = trata como primeira vez (JSONDecodeError ⊂ ValueError)
        self.after(400, self._open_template_gallery_welcome)

    def _open_template_gallery_welcome(self) -> None:
        from ui.template_gallery import TemplateGallery
        TemplateGallery(self, T, self, welcome=True)

    def _open_template_gallery(self) -> None:
        from ui.template_gallery import TemplateGallery
        TemplateGallery(self, T, self, welcome=False)

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

        # Botão galeria de templates ("📚 Exemplos")
        self._templates_btn = tk.Button(right, text="📚 Exemplos",
                                         command=self._open_template_gallery,
                                         font=("Segoe UI", 9, "bold"),
                                         bg=T["bg_deep"], fg=T["subtext"],
                                         activebackground=T["card_h"],
                                         activeforeground=T["text"],
                                         relief="flat", bd=0, cursor="hand2",
                                         padx=8, pady=2, highlightthickness=0)
        self._templates_btn.pack(side="right", padx=(8, 0))
        self._templates_btn.bind("<Enter>", lambda e: self._templates_btn.config(fg=T["text"]))
        self._templates_btn.bind("<Leave>", lambda e: self._templates_btn.config(fg=T["subtext"]))

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

    # ─────────────────────────────────────────────────────────────
    # ANIMATION HELPERS
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _lerp_color(c1: str, c2: str, t: float) -> str:
        """Interpola linearmente entre duas cores hex, t em [0,1]."""
        t = max(0.0, min(1.0, t))
        try:
            r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
            r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
            r = int(r1 + (r2-r1)*t)
            g = int(g1 + (g2-g1)*t)
            b = int(b1 + (b2-b1)*t)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return c2

    def _fade_pill(self, pill: tk.Label, from_fg: str, to_fg: str,
                   from_hl: str, to_hl: str, step: int = 0, steps: int = 8) -> None:
        if step > steps:
            return
        t = step / steps
        try:
            pill.config(
                fg=self._lerp_color(from_fg, to_fg, t),
                highlightbackground=self._lerp_color(from_hl, to_hl, t),
            )
        except tk.TclError:
            return
        self.after(22, lambda: self._fade_pill(pill, from_fg, to_fg,
                                               from_hl, to_hl, step+1, steps))

    def _anim_color(self, widget, from_c: str, to_c: str,
                    step: int, steps: int, gen: int) -> None:
        """Anima bg de um widget via interpolação. Cancela se `gen` mudou."""
        if getattr(widget, "_anim_gen", 0) != gen:
            return
        t = step / steps
        try:
            widget.config(bg=self._lerp_color(from_c, to_c, t))
        except tk.TclError:
            return
        if step < steps:
            self.after(16, lambda: self._anim_color(widget, from_c, to_c,
                                                    step+1, steps, gen))

    def _btn_anim_hover(self, btn: tk.Button, target: str) -> None:
        """Dispara animação de hover no botão, cancelando a animação anterior."""
        gen = (getattr(btn, "_anim_gen", 0) + 1) & 0xFFFF
        btn._anim_gen = gen
        try:
            from_c = btn.cget("bg")
        except tk.TclError:
            return
        self._anim_color(btn, from_c, target, 0, 5, gen)

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
        """Liga/desliga uma pill de status com fade de cor."""
        if on:
            c = color or T["green"]
            cur_fg = pill.cget("fg")
            cur_hl = pill.cget("highlightbackground")
            self._fade_pill(pill, cur_fg, c, cur_hl, c)
        else:
            cur_fg = pill.cget("fg")
            cur_hl = pill.cget("highlightbackground")
            self._fade_pill(pill, cur_fg, T["subtext"], cur_hl, T["line_2"])

    # ── Notebook ──────────────────────────────────────────────────
    def _build_notebook(self) -> None:
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=(6, 4))
        self._nb = nb  # exposto pra _toggle_theme preservar aba ativa

        self.tab_click     = tk.Frame(nb, bg=T["bg"])
        self.tab_key       = tk.Frame(nb, bg=T["bg"])
        self.tab_macro     = tk.Frame(nb, bg=T["bg"])
        self.tab_hs        = tk.Frame(nb, bg=T["bg"])
        self.tab_monitor   = tk.Frame(nb, bg=T["bg"])
        self.tab_scheduler = tk.Frame(nb, bg=T["bg"])
        self.tab_ai        = tk.Frame(nb, bg=T["bg"])
        self.tab_cfg       = tk.Frame(nb, bg=T["bg"])

        nb.add(self.tab_click,     text="🖱  AutoClick")
        nb.add(self.tab_key,       text="⌨  AutoKeyboard")
        nb.add(self.tab_macro,     text="🤖  Macro")
        nb.add(self.tab_hs,        text="✨  Hotstrings")
        nb.add(self.tab_monitor,   text="📡  Monitoramento")
        nb.add(self.tab_scheduler, text="⏰  Agendador")
        nb.add(self.tab_ai,        text="🤖  IA Assistente")
        nb.add(self.tab_cfg,       text="⚙  Configurações")

        self._build_click_tab()
        self._build_keyboard_tab()
        self._build_macro_tab()
        self._build_hotstrings_tab()
        self._build_monitor_tab()
        self._build_scheduler_tab()
        self._build_ai_assistant_tab()
        self._build_settings_tab()

    # ── Footer (status bar terminal-like) ─────────────────────────
    def _build_footer(self) -> None:
        # Barra de progresso indeterminate (visível só quando rodando)
        style = ttk.Style()
        style.configure("Run.Horizontal.TProgressbar",
                        troughcolor=T["bg_deep"],
                        background=T["accent"],
                        thickness=3)
        self._run_bar = ttk.Progressbar(
            self, orient="horizontal", mode="indeterminate",
            style="Run.Horizontal.TProgressbar",
        )
        # Não empacota agora — só aparece quando automation inicia

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

    def _run_indicator_start(self) -> None:
        """Mostra barra de progresso + ativa pulse no status dot."""
        try:
            if not self._run_bar.winfo_ismapped():
                self._run_bar.pack(fill="x", side="bottom")
            self._run_bar.start(12)
        except Exception:
            pass
        self._dot_pulse_active = True
        self._dot_pulse_loop()

    def _run_indicator_stop(self) -> None:
        """Para barra de progresso + desativa pulse no status dot."""
        try:
            self._run_bar.stop()
            self._run_bar.pack_forget()
        except Exception:
            pass
        self._dot_pulse_active = False
        try:
            self._status_dot.config(text="○", fg=T["subtext"])
        except Exception:
            pass

    def _dot_pulse_loop(self) -> None:
        """Alterna ○ / ● enquanto _dot_pulse_active for True."""
        if not getattr(self, "_dot_pulse_active", False):
            return
        try:
            self._status_dot.config(
                text="●" if self._status_dot.cget("text") == "○" else "○",
                fg=T["green"],
            )
        except Exception:
            return
        self.after(550, self._dot_pulse_loop)

    def _show_toast(self, msg: str, duration_ms: int = 2800) -> None:
        """Pequeno painel no canto inferior direito que desaparece com fade."""
        # Cancela toast anterior se ainda visível
        prev = getattr(self, "_toast_win", None)
        if prev:
            try:
                prev.destroy()
            except Exception:
                pass

        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        try:
            toast.attributes("-alpha", 0.93)
        except Exception:
            pass
        toast.configure(bg=T["card"])
        self._toast_win = toast

        inner = tk.Frame(toast, bg=T["card"], padx=14, pady=10,
                         highlightbackground=T["accent"], highlightthickness=1)
        inner.pack(fill="both", expand=True)
        tk.Label(inner, text=msg, bg=T["card"], fg=T["text"],
                 font=("Segoe UI", 9), anchor="w").pack(anchor="w")

        # Posiciona no canto inferior direito da janela principal
        def _place() -> None:
            try:
                toast.update_idletasks()
                tw = toast.winfo_reqwidth()
                th = toast.winfo_reqheight()
                wx = self.winfo_x() + self.winfo_width()  - tw - 16
                wy = self.winfo_y() + self.winfo_height() - th - 56
                toast.geometry(f"+{max(0,wx)}+{max(0,wy)}")
            except Exception:
                pass

        self.after(10, _place)

        def _fade(step: int = 0, total: int = 12) -> None:
            if not toast.winfo_exists():
                return
            try:
                toast.attributes("-alpha", max(0.0, 0.93 * (1 - step / total)))
            except Exception:
                pass
            if step < total:
                self.after(35, lambda: _fade(step + 1, total))
            else:
                try:
                    toast.destroy()
                except Exception:
                    pass

        self.after(duration_ms, _fade)

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

    def _set_status(self, msg: str, toast: bool = False) -> None:
        self.lbl_status.config(text=msg)
        # Dot color só muda quando não está em pulse (pulse controla o dot)
        if not getattr(self, "_dot_pulse_active", False):
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
        if toast:
            self._show_toast(msg)

    def _fmt_time(self, secs: float) -> str:
        s = int(secs)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

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
    def _load_tray_image(self) -> "Image.Image":
        """Carrega assets/icon.ico como PIL Image 64×64 RGBA para o pystray.

        Usa _generate_icon_ico() que já foi chamado antes, então o arquivo
        deve existir. Cai no círculo roxo apenas se PIL não conseguir abrir.
        """
        icon_path = os.path.join(_ROOT, "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                img = img.convert("RGBA")
                img = img.resize((64, 64), Image.LANCZOS)
                return img
            except Exception:
                pass
        # fallback: círculo roxo
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(108, 99, 255, 255))
        draw.ellipse([22, 22, 42, 42], fill=(255, 255, 255, 200))
        return img

    def _init_tray(self) -> None:
        if not HAS_TRAY:
            return
        try:
            img = self._load_tray_image()

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
        # Hotstrings/scheduler/monitor: o _build_*_tab rebuilda treeview vazio.
        # scheduler/monitor já chamam refresh internamente; hotstrings precisa
        # de chamada explícita aqui pra repopular depois de troca de tema.
        try:
            self._refresh_hs_tree()
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
            self._scheduler.stop()
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
