"""
ui/monitor_dialog.py — Diálogo modal para criar/editar um Monitor (ntfy).

Mirror reduzido de StopConditionDialog. Reusa helpers de captura de imagem
e cor herdados do mesmo padrão (overlay translúcido pra arrastar região,
captura de cor em 3s).
"""
from __future__ import annotations

import base64
import io
import threading
import time
import tkinter as tk
from tkinter import ttk

from core.ntfy_client import Monitor
from ui.widgets import make_button


TRIGGER_TYPES = ["image", "pixel", "event"]
EVENT_NAMES   = [
    "macro_started",
    "macro_stopped",
    "macro_stopped_by_cond",
    "hotstring_fired",
]
EVENT_LABELS: dict[str, str] = {
    "macro_started":         "Macro iniciou",
    "macro_stopped":         "Macro parou (normal)",
    "macro_stopped_by_cond": "Macro parou por Stop Condition",
    "hotstring_fired":       "Hotstring disparou",
}


class MonitorDialog(tk.Toplevel):
    """Diálogo modal pra criar/editar um Monitor de ntfy."""

    def __init__(self, parent: tk.Tk, theme: dict, driver=None,
                 monitor: Monitor | None = None) -> None:
        super().__init__(parent)
        self._T = theme
        self._driver = driver
        self.result: Monitor | None = None
        self.title("Editar Monitor" if monitor else "Novo Monitor")
        self.configure(bg=theme["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Estado
        m = monitor
        self._v_name        = tk.StringVar(value=m.name if m else "")
        self._v_type        = tk.StringVar(value=m.trigger_type if m else "image")
        self._v_cooldown    = tk.StringVar(value=str(m.cooldown_s) if m else "30")
        self._v_enabled     = tk.BooleanVar(value=m.enabled if m else True)
        self._v_screenshot  = tk.BooleanVar(value=m.attach_screenshot if m else False)
        # Image
        self._image_data_b64: str | None = m.image_data if m else None
        self._v_threshold   = tk.StringVar(
            value=str(int((m.image_threshold if m else 0.9) * 100)))
        self._image_preview_label: tk.Label | None = None
        # Pixel
        self._v_x = tk.StringVar(value=str(m.x) if m and m.x is not None else "")
        self._v_y = tk.StringVar(value=str(m.y) if m and m.y is not None else "")
        rgb = m.color_rgb if m and m.color_rgb else [0, 0, 0]
        self._v_r   = tk.StringVar(value=str(rgb[0]))
        self._v_g   = tk.StringVar(value=str(rgb[1]))
        self._v_b   = tk.StringVar(value=str(rgb[2]))
        self._v_tol = tk.StringVar(value=str(m.color_tolerance if m else 10))
        self._color_preview: tk.Label | None = None
        # Event
        self._v_event = tk.StringVar(value=m.event_name if m and m.event_name
                                      else "macro_stopped")

        self._build()
        self._v_type.trace_add("write", lambda *_: self._refresh_fields())

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ─────────────────────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────────────────────
    def _build(self) -> None:
        T = self._T
        p = self

        # Nome
        top = tk.Frame(p, bg=T["bg"])
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Nome:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(top, textvariable=self._v_name, width=30, bg=T["card"],
                 fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                 relief="flat", bd=4).pack(side="left", padx=8)

        # Tipo
        type_row = tk.Frame(p, bg=T["bg"])
        type_row.pack(fill="x", padx=16, pady=4)
        tk.Label(type_row, text="Tipo de gatilho:", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Combobox(type_row, textvariable=self._v_type, values=TRIGGER_TYPES,
                     state="readonly", width=12, font=("Segoe UI", 10)
                     ).pack(side="left", padx=8)

        # Frame dinâmico (varia por tipo)
        self._fields = tk.Frame(p, bg=T["bg"])
        self._fields.pack(fill="x", padx=16, pady=4)
        self._refresh_fields()

        # Cooldown
        cd_row = tk.Frame(p, bg=T["bg"])
        cd_row.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(cd_row, text="Cooldown (s):", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Spinbox(cd_row, textvariable=self._v_cooldown, from_=0, to=3600,
                   width=6, bg=T["card"], fg=T["text"], relief="flat",
                   font=("Consolas", 10)).pack(side="left", padx=8)
        tk.Label(cd_row, text="(intervalo mínimo entre disparos)",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(side="left")

        # Flags
        tk.Checkbutton(p, text="Anexar screenshot da tela ao alerta",
                        variable=self._v_screenshot,
                        bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                        activebackground=T["bg"], font=("Segoe UI", 10)
                        ).pack(anchor="w", padx=16, pady=(6, 0))
        tk.Label(p, text="⚠ Screenshot envia sua tela inteira pelos servidores da ntfy.sh.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(anchor="w", padx=16, pady=(0, 4))
        tk.Checkbutton(p, text="Ativado", variable=self._v_enabled,
                        bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                        activebackground=T["bg"], font=("Segoe UI", 10)
                        ).pack(anchor="w", padx=16, pady=(2, 0))

        # Botões
        btns = tk.Frame(p, bg=T["bg"])
        btns.pack(fill="x", padx=16, pady=(12, 14))
        make_button(btns, "✔ OK", self._ok, T["accent"], fg="#ffffff",
                    padx=14, pady=6).pack(side="left", padx=(0, 8))
        make_button(btns, "✕ Cancelar", self.destroy, T["card"], fg=T["text"],
                    padx=12, pady=6).pack(side="left")

    def _refresh_fields(self) -> None:
        T = self._T
        f = self._fields
        for w in f.winfo_children():
            w.destroy()

        def lbl(text, row, col=0):
            tk.Label(f, text=text, bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=row, column=col,
                                                 sticky="w", pady=3)

        def entry(var, row, col=1, w=8):
            tk.Entry(f, textvariable=var, width=w, bg=T["card"], fg=T["text"],
                     insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4
                     ).grid(row=row, column=col, sticky="w")

        t = self._v_type.get()

        if t == "image":
            make_button(f, "📷 Capturar Região", self._capture_image,
                         T["accent2"], padx=8, pady=4
                         ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
            self._image_preview_label = tk.Label(f, bg=T["card"], width=8, height=4,
                                                  text="sem\ntemplate", fg=T["subtext"])
            self._image_preview_label.grid(row=0, column=2, rowspan=2, padx=8)
            self._update_image_preview()
            lbl("Confiança (%):", 1)
            tk.Spinbox(f, textvariable=self._v_threshold, from_=50, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)
                       ).grid(row=1, column=1, sticky="w")
            tk.Label(f, text="Alerta dispara quando a imagem APARECER na tela.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=2, column=0, columnspan=3, sticky="w")

        elif t == "pixel":
            lbl("X:", 0); entry(self._v_x, 0)
            lbl("Y:", 1); entry(self._v_y, 1)
            make_button(f, "🎨 Capturar Cor (3s)", self._capture_color,
                         T["accent2"], padx=6, pady=3
                         ).grid(row=0, column=2, rowspan=2, padx=8)
            self._color_preview = tk.Label(f, text="  ", bg=self._rgb_hex(),
                                            relief="solid", bd=1, width=4)
            self._color_preview.grid(row=0, column=3, rowspan=2, padx=4)

            lbl("R:", 2); entry(self._v_r, 2, w=5)
            lbl("G:", 3); entry(self._v_g, 3, w=5)
            lbl("B:", 4); entry(self._v_b, 4, w=5)
            for v in (self._v_r, self._v_g, self._v_b):
                v.trace_add("write", lambda *_: self._update_color_preview())
            lbl("Tolerância:", 5)
            tk.Spinbox(f, textvariable=self._v_tol, from_=0, to=255, width=5,
                       bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)
                       ).grid(row=5, column=1, sticky="w")
            tk.Label(f, text="Alerta dispara quando o pixel bater com a cor.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=6, column=0, columnspan=4, sticky="w")

        elif t == "event":
            lbl("Evento:", 0)
            cb = ttk.Combobox(f, textvariable=self._v_event,
                               values=EVENT_NAMES, state="readonly",
                               width=24, font=("Segoe UI", 10))
            cb.grid(row=0, column=1, columnspan=2, sticky="w")
            # Texto de ajuda dinâmico
            help_label = tk.Label(f, text="", bg=T["bg"], fg=T["accent2"],
                                   font=("Segoe UI", 9, "italic"),
                                   wraplength=320, justify="left", anchor="w")
            help_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=4)

            def _refresh_help(*_):
                ev = self._v_event.get()
                help_label.config(text=EVENT_LABELS.get(ev, ""))
            self._v_event.trace_add("write", _refresh_help)
            _refresh_help()

    # ─────────────────────────────────────────────────────────────
    # CAPTURA DE COR (3s timer, igual step_dialog)
    # ─────────────────────────────────────────────────────────────
    def _rgb_hex(self) -> str:
        try:
            r = max(0, min(255, int(self._v_r.get() or 0)))
            g = max(0, min(255, int(self._v_g.get() or 0)))
            b = max(0, min(255, int(self._v_b.get() or 0)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            return "#000000"

    def _update_color_preview(self) -> None:
        if self._color_preview:
            self._color_preview.config(bg=self._rgb_hex())

    def _capture_color(self) -> None:
        if not self._driver:
            return
        orig = self.title()
        self.title("Posicione o cursor sobre a cor... (3s)")
        def _do():
            time.sleep(3)
            x, y = self._driver.get_position()
            r, g, b = self._driver.get_pixel_color(int(x), int(y))
            self._v_x.set(str(int(x))); self._v_y.set(str(int(y)))
            self._v_r.set(str(r)); self._v_g.set(str(g)); self._v_b.set(str(b))
            self.after(0, lambda: self.title(orig))
            self.after(0, self._update_color_preview)
        threading.Thread(target=_do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────
    # CAPTURA DE IMAGEM (overlay translúcido, igual step_dialog)
    # ─────────────────────────────────────────────────────────────
    def _update_image_preview(self) -> None:
        if not self._image_preview_label:
            return
        if not self._image_data_b64:
            self._image_preview_label.config(image="", text="sem\ntemplate")
            return
        try:
            from PIL import Image, ImageTk
            raw = base64.b64decode(self._image_data_b64)
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((64, 64))
            photo = ImageTk.PhotoImage(img)
            self._image_preview_label.config(image=photo, text="")
            self._image_preview_label.image = photo
        except Exception:
            self._image_preview_label.config(image="", text="erro\npreview")

    def _capture_image(self) -> None:
        from PIL import ImageGrab
        self.withdraw()
        self.update()
        time.sleep(0.3)
        try:
            screenshot = ImageGrab.grab()
        except Exception:
            self.deiconify()
            return
        T = self._T
        sw, sh = screenshot.size

        overlay = tk.Toplevel(self)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.4)
        overlay.configure(bg="black")
        overlay.attributes("-topmost", True)
        overlay.config(cursor="crosshair")

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0,
                            cursor="crosshair")
        canvas.pack(fill="both", expand=True)
        sel = {"x0": 0, "y0": 0, "x1": 0, "y1": 0, "rect": None}

        def on_press(e):
            sel["x0"], sel["y0"] = e.x_root, e.y_root
            if sel["rect"]:
                canvas.delete(sel["rect"])
            sel["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                                   outline=T["accent2"], width=2)

        def on_drag(e):
            if sel["rect"] is None:
                return
            x0_local = sel["x0"] - overlay.winfo_rootx()
            y0_local = sel["y0"] - overlay.winfo_rooty()
            canvas.coords(sel["rect"], x0_local, y0_local, e.x, e.y)

        def on_release(e):
            sel["x1"], sel["y1"] = e.x_root, e.y_root
            overlay.destroy()

        def on_cancel(e):
            sel["x0"] = sel["x1"]; sel["y0"] = sel["y1"]
            overlay.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_cancel)
        overlay.wait_window()
        self.deiconify()
        self.lift()

        left, top = min(sel["x0"], sel["x1"]), min(sel["y0"], sel["y1"])
        right, bottom = max(sel["x0"], sel["x1"]), max(sel["y0"], sel["y1"])
        if right - left < 5 or bottom - top < 5:
            return  # área muito pequena, ignora
        left = max(0, min(left, sw)); top = max(0, min(top, sh))
        right = max(0, min(right, sw)); bottom = max(0, min(bottom, sh))

        cropped = screenshot.crop((left, top, right, bottom))
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        self._image_data_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self._update_image_preview()

    # ─────────────────────────────────────────────────────────────
    # OK
    # ─────────────────────────────────────────────────────────────
    def _ok(self) -> None:
        def _int(var, d=0):
            try: return int(var.get() or d)
            except ValueError: return d

        name = self._v_name.get().strip() or "Monitor sem nome"
        ttype = self._v_type.get()
        cd = max(0, _int(self._v_cooldown, 30))
        enabled = bool(self._v_enabled.get())
        screenshot = bool(self._v_screenshot.get())

        mon = Monitor(
            name=name,
            trigger_type=ttype,
            cooldown_s=cd,
            enabled=enabled,
            attach_screenshot=screenshot,
        )

        if ttype == "image":
            mon.image_data = self._image_data_b64
            mon.image_threshold = max(0.5, min(1.0, _int(self._v_threshold, 90) / 100))
        elif ttype == "pixel":
            mon.x = _int(self._v_x) if self._v_x.get().strip() else None
            mon.y = _int(self._v_y) if self._v_y.get().strip() else None
            r = max(0, min(255, _int(self._v_r)))
            g = max(0, min(255, _int(self._v_g)))
            b = max(0, min(255, _int(self._v_b)))
            mon.color_rgb = [r, g, b]
            mon.color_tolerance = max(0, min(255, _int(self._v_tol, 10)))
        elif ttype == "event":
            mon.event_name = self._v_event.get() or "macro_stopped"

        self.result = mon
        self.destroy()
