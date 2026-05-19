"""
ui/tabs/monitor.py — Aba 📡 Monitoramento (ntfy.sh).

Requisitos do host (AutoClickPro):
  Attrs:   _driver, _ntfy, _macro_runner, _click_running, _type_running,
           _macro_running, tab_monitor, var_ntfy_active, var_slot_names
  Métodos: _make_scrollable, _section, _btn, _set_status,
           _stop_clicking, _stop_typing, _stop_macro, _start_macro,
           _toggle_pause, _load_slot
"""
from __future__ import annotations

import collections
import time
import tkinter as tk
from tkinter import messagebox, ttk

from core.paths import NTFY_CONFIG_PATH
from ui.monitor_dialog import MonitorDialog
from ui.theme import T
from ui.widgets import make_button


class MonitorMixin:
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
            columns=("name", "type", "alerta", "cooldown", "enabled"),
            show="headings", style="Seq.Treeview", height=8,
        )
        self.mon_tree.heading("name",     text="Nome")
        self.mon_tree.heading("type",     text="Tipo")
        self.mon_tree.heading("alerta",   text="Alerta")
        self.mon_tree.heading("cooldown", text="Cooldown")
        self.mon_tree.heading("enabled",  text="Ativo")
        self.mon_tree.column("name",     width=150, anchor="w")
        self.mon_tree.column("type",     width=60,  anchor="center")
        self.mon_tree.column("alerta",   width=60,  anchor="center")
        self.mon_tree.column("cooldown", width=70,  anchor="center")
        self.mon_tree.column("enabled",  width=50,  anchor="center")
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
            icons = ("📱" if m.notify_phone else "") + ("🖥️" if m.notify_pc else "")
            self.mon_tree.insert("", "end", values=(
                m.name or "(sem nome)",
                m.trigger_type,
                icons or "—",
                f"{m.cooldown_s}s",
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
