"""
ui/tabs/settings.py — Aba ⚙ Configurações + hotkeys, perfis (slots / arquivos),
diálogos de about/donate/uninstall.

Requisitos do host (AutoClickPro):
  Attrs:   _driver, _hotstrings, _ntfy, _tray, _hk_capture_hook,
           tab_cfg, var_hk_*, var_sound, var_slot_names, _click_running,
           _type_running, _macro_running, _recorder_running
  Métodos: _make_scrollable, _section, _btn, _set_status, _play_tick,
           _collect_script, _collect_ui_profile, _apply_script,
           _apply_ui_profile, _stop_clicking, _stop_typing, _stop_macro,
           _macro_toggle_recording, _save_window_geometry, toggle_clicking,
           toggle_typing, toggle_macro, _toggle_pause, stop_all
"""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import keyboard

from core.macro_schema import (
    profile_to_dict,
    script_from_dict,
    ui_from_dict,
)
from core.paths import PROFILES_DIR
from ui.theme import PIX_KEY, PIX_OWNER, T


class SettingsMixin:
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
        os.makedirs(PROFILES_DIR, exist_ok=True)
        path = os.path.join(PROFILES_DIR, f"slot{slot}.json")
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
        path = os.path.join(PROFILES_DIR, f"slot{slot}.json")
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
    # DIÁLOGOS / WARNINGS
    # ─────────────────────────────────────────────────────────────
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
