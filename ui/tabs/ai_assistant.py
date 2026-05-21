"""
ui/tabs/ai_assistant.py — Aba 🤖 IA Assistente.

Chat com LLM que gera macros a partir de descrições em português.
Salva config (backend/modelo/key/url) em profiles/ai_assistant.json.
Histórico de chat é efêmero — perdido ao fechar o app.

Requisitos do host (AutoClickPro):
  Attrs:   tab_ai, _nb, _macro_steps
  Métodos: _make_scrollable, _section, _btn, _set_status,
           _apply_script, _macro_refresh_tree (opcional)
"""
from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.ai_assistant import AIAssistant, parse_macro_steps
from core.ai_client import list_ollama_models
from core.macro_schema import MacroScript
from core.paths import AI_CONFIG_PATH, PROFILES_DIR
from ui.theme import T


class AIAssistantMixin:
    # ─────────────────────────────────────────────────────────────
    # ABA: IA ASSISTENTE
    # ─────────────────────────────────────────────────────────────
    def _build_ai_assistant_tab(self) -> None:
        # Estado interno
        self._ai_assistant = AIAssistant()
        self._ai_busy = False
        self._ai_thinking_mark: str | None = None  # marca pra remover "🤖 IA pensando..."

        # Vars de configuração — carregadas de profiles/ai_assistant.json
        cfg = self._ai_load_config()
        self.var_ai_backend  = tk.StringVar(value=cfg.get("backend", "ollama"))
        self.var_ai_model    = tk.StringVar(value=cfg.get("model", "llama3.2"))
        self.var_ai_api_key  = tk.StringVar(value=cfg.get("api_key", ""))
        self.var_ai_base_url = tk.StringVar(value=cfg.get("base_url", ""))

        p = self._make_scrollable(self.tab_ai)

        # ── Header com descrição ─────────────────────────────────
        self._section(p, "IA Assistente — Gere macros conversando", "🤖 "
                       ).pack(fill="x", padx=8, pady=(10, 3))
        tk.Label(p, text="Descreva em português o que você quer que o macro faça.\n"
                          "A IA gera os steps prontos pra aplicar — grátis se usar Ollama local.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 9), justify="left"
                 ).pack(fill="x", padx=14, pady=(0, 6))

        # ── Configuração rápida ──────────────────────────────────
        cfg_row = tk.Frame(p, bg=T["bg"])
        cfg_row.pack(fill="x", padx=14, pady=(4, 4))

        tk.Label(cfg_row, text="Backend:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 9)
                 ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Combobox(cfg_row, textvariable=self.var_ai_backend,
                     values=["ollama", "openai", "openrouter", "groq", "custom"],
                     state="readonly", width=12, font=("Segoe UI", 9)
                     ).grid(row=0, column=1, padx=(0, 12))
        # Quando troca backend: atualiza dropdown de modelos com sugestões
        self.var_ai_backend.trace_add("write",
            lambda *_: self._ai_model_combo.config(values=self._ai_default_models()))

        tk.Label(cfg_row, text="Modelo:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 9)
                 ).grid(row=0, column=2, sticky="w", padx=(0, 4))
        self._ai_model_combo = ttk.Combobox(
            cfg_row, textvariable=self.var_ai_model, width=22,
            font=("Consolas", 10), values=self._ai_default_models())
        self._ai_model_combo.grid(row=0, column=3, padx=(0, 4))

        self._btn(cfg_row, "🔍", self._ai_detect_models,
                   bg=T["card"], fg=T["text"], padx=6
                   ).grid(row=0, column=4, padx=(0, 8))

        self._btn(cfg_row, "⚙ Avançado", self._ai_open_advanced,
                   bg=T["card"], fg=T["text"], padx=8
                   ).grid(row=0, column=5, padx=(4, 0))

        # Auto-detecta modelos Ollama no boot se backend padrão é ollama
        if self.var_ai_backend.get() == "ollama":
            self.after(500, self._ai_detect_models_silent)

        # ── Área de chat (Text scrollable) ───────────────────────
        chat_frame = tk.Frame(p, bg=T["bg"])
        chat_frame.pack(fill="both", expand=True, padx=14, pady=(8, 4))

        chat_scroll = ttk.Scrollbar(chat_frame, orient="vertical")
        chat_scroll.pack(side="right", fill="y")

        self._ai_chat = tk.Text(
            chat_frame, wrap="word", bg=T["bg_deep"], fg=T["text"],
            insertbackground=T["text"], font=("Segoe UI", 10),
            relief="flat", padx=10, pady=8, height=18,
            yscrollcommand=chat_scroll.set, state="disabled",
        )
        self._ai_chat.pack(side="left", fill="both", expand=True)
        chat_scroll.config(command=self._ai_chat.yview)

        # Tags de formatação
        self._ai_chat.tag_configure("user",
                                     foreground=T["accent2"],
                                     font=("Segoe UI", 10, "bold"))
        self._ai_chat.tag_configure("assistant", foreground=T["text"])
        self._ai_chat.tag_configure("error",     foreground=T["red"])
        self._ai_chat.tag_configure("status",    foreground=T["subtext"],
                                     font=("Segoe UI", 9, "italic"))

        self._ai_print("💡 Dica: experimente 'faz um clicker que clica a cada 100ms' "
                       "ou 'pressiona F5 a cada 30 segundos'.\n\n",
                       tag="status")

        # ── Input do usuário ─────────────────────────────────────
        input_frame = tk.Frame(p, bg=T["bg"])
        input_frame.pack(fill="x", padx=14, pady=(0, 10))

        self._ai_input = tk.Text(
            input_frame, height=3, wrap="word", bg=T["card"], fg=T["text"],
            insertbackground=T["text"], font=("Segoe UI", 10),
            relief="flat", padx=8, pady=6,
        )
        self._ai_input.pack(fill="x", pady=(0, 4))
        # Ctrl+Enter envia; Enter sozinho quebra linha normalmente
        self._ai_input.bind("<Control-Return>",
                             lambda e: (self._ai_send(), "break")[1])

        btn_row = tk.Frame(input_frame, bg=T["bg"])
        btn_row.pack(fill="x")

        self._ai_send_btn = self._btn(btn_row, "📤 Enviar  (Ctrl+Enter)",
                                       self._ai_send, bg=T["accent"], padx=12)
        self._ai_send_btn.pack(side="left", padx=(0, 4))

        self._btn(btn_row, "🗑 Limpar conversa", self._ai_clear,
                   bg=T["card"], fg=T["text"], padx=10
                   ).pack(side="left", padx=4)

    # ─────────────────────────────────────────────────────────────
    # CHAT — print e fluxo de envio
    # ─────────────────────────────────────────────────────────────
    def _ai_print(self, text: str, tag: str = "assistant") -> None:
        """Escreve no chat (com tag) e faz auto-scroll."""
        self._ai_chat.config(state="normal")
        self._ai_chat.insert("end", text, tag)
        self._ai_chat.see("end")
        self._ai_chat.config(state="disabled")

    def _ai_send(self) -> None:
        if self._ai_busy:
            return
        msg = self._ai_input.get("1.0", "end-1c").strip()
        if not msg:
            return

        self._ai_input.delete("1.0", "end")
        self._ai_print("👤 Você:\n", tag="user")
        self._ai_print(f"{msg}\n\n", tag="assistant")

        # Marca posição do "IA pensando" para remover depois
        self._ai_chat.config(state="normal")
        self._ai_thinking_mark = self._ai_chat.index("end-1c")
        self._ai_chat.config(state="disabled")
        self._ai_print("🤖 IA pensando...\n", tag="status")

        self._ai_busy = True
        self._ai_send_btn.config(state="disabled")
        self._ai_save_config()

        # Thread separada — request bloqueia até 90s
        threading.Thread(target=self._ai_call_thread, args=(msg,),
                         daemon=True).start()

    def _ai_call_thread(self, msg: str) -> None:
        """Streaming: itera chunks e atualiza UI a cada um via after()."""
        # 1. Limpa marca de "IA pensando" e imprime cabeçalho da resposta
        self.after(0, self._ai_stream_start)

        # 2. Pega snapshot do macro atual pra passar como contexto
        current_macro = list(getattr(self, "_macro_steps", []) or [])

        try:
            for chunk in self._ai_assistant.chat_stream(
                msg,
                backend=self.var_ai_backend.get() or "ollama",
                model=self.var_ai_model.get() or "llama3.2",
                api_key=self.var_ai_api_key.get(),
                base_url=self.var_ai_base_url.get(),
                timeout_s=120,
                temperature=0.4,
                current_macro=current_macro,
            ):
                self.after(0, self._ai_stream_chunk, chunk)
        except RuntimeError as exc:
            self.after(0, self._ai_stream_error, str(exc))
            return
        except Exception as exc:
            self.after(0, self._ai_stream_error, f"interno: {exc}")
            return

        self.after(0, self._ai_stream_end)

    def _ai_stream_start(self) -> None:
        """Roda na UI thread: remove 'IA pensando...' e imprime cabeçalho."""
        if self._ai_thinking_mark:
            self._ai_chat.config(state="normal")
            self._ai_chat.delete(self._ai_thinking_mark, "end-1c")
            self._ai_chat.config(state="disabled")
            self._ai_thinking_mark = None
        self._ai_print("🤖 IA:\n", tag="user")
        # Marca posição do início da resposta pra extrair full text depois
        self._ai_chat.config(state="normal")
        self._ai_response_start = self._ai_chat.index("end-1c")
        self._ai_chat.config(state="disabled")

    def _ai_stream_chunk(self, chunk: str) -> None:
        """Roda na UI thread: append chunk no chat."""
        self._ai_print(chunk, tag="assistant")

    def _ai_stream_error(self, msg: str) -> None:
        """Roda na UI thread: marca erro e libera o botão."""
        self._ai_busy = False
        self._ai_send_btn.config(state="normal")
        if self._ai_thinking_mark:
            self._ai_chat.config(state="normal")
            self._ai_chat.delete(self._ai_thinking_mark, "end-1c")
            self._ai_chat.config(state="disabled")
            self._ai_thinking_mark = None
        self._ai_print(f"\n[ERRO: {msg}]\n\n", tag="error")

    def _ai_stream_end(self) -> None:
        """Roda na UI thread: stream completou, oferece botão de aplicar se tiver JSON."""
        self._ai_busy = False
        self._ai_send_btn.config(state="normal")
        self._ai_print("\n", tag="assistant")

        # Extrai full response do chat (texto entre marca de início e fim)
        try:
            full_text = self._ai_chat.get(self._ai_response_start, "end-1c")
        except Exception:
            full_text = ""

        steps = parse_macro_steps(full_text)
        if steps:
            self._ai_offer_apply(steps)
        else:
            self._ai_print("(Sem bloco JSON detectado nesta resposta.)\n\n",
                            tag="status")

    def _ai_offer_apply(self, steps: list[dict]) -> None:
        """Insere botão 'Aplicar este macro' inline no chat."""
        self._ai_chat.config(state="normal")
        self._ai_chat.insert("end", "\n")
        btn = self._btn(self._ai_chat,
                        f"✓ Aplicar este macro ({len(steps)} steps)",
                        lambda s=steps: self._ai_apply(s),
                        bg=T["green"], padx=10)
        self._ai_chat.window_create("end", window=btn)
        self._ai_chat.insert("end", "\n\n")
        self._ai_chat.see("end")
        self._ai_chat.config(state="disabled")

    def _ai_apply(self, steps_dicts: list[dict]) -> None:
        """Aplica steps no editor de Macro (substitui o atual)."""
        if self._macro_steps:
            if not messagebox.askyesno(
                "Substituir macro atual?",
                f"Vai substituir os {len(self._macro_steps)} step(s) atuais "
                f"pelos {len(steps_dicts)} gerados pela IA.\n\nContinuar?",
                parent=self,
            ):
                return

        # _apply_script aceita macro_steps como list[dict] e reconstrói
        # via macrostep_from_dict (que ignora campos desconhecidos via defaults)
        script = MacroScript(macro_steps=steps_dicts,
                              rep_mode="infinite", macro_speed="1")
        self._apply_script(script)
        self._nb.select(self.tab_macro)
        self._set_status(
            f"🤖 {len(steps_dicts)} step(s) aplicados pela IA", toast=True)

    def _ai_clear(self) -> None:
        if self._ai_assistant.history and not messagebox.askyesno(
            "Limpar conversa?",
            "Apaga o histórico do chat e os botões de aplicar.\n"
            "Sua config (backend/modelo) é mantida.",
            parent=self,
        ):
            return
        self._ai_assistant.clear_history()
        self._ai_chat.config(state="normal")
        self._ai_chat.delete("1.0", "end")
        self._ai_chat.config(state="disabled")
        self._ai_print("💡 Conversa limpa. Comece de novo.\n\n", tag="status")

    # ─────────────────────────────────────────────────────────────
    # MODELOS (detecção via API e sugestões padrão)
    # ─────────────────────────────────────────────────────────────
    def _ai_default_models(self) -> list[str]:
        """Sugestões padrão por backend (mostra como fallback)."""
        b = self.var_ai_backend.get() or "ollama"
        return {
            "ollama":     ["llama3.2", "llama3.2-vision", "llama3.1", "mistral",
                           "gemma2", "phi3", "qwen2.5"],
            "openai":     ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            "openrouter": ["mistralai/mistral-7b-instruct",
                           "google/gemma-7b-it",
                           "meta-llama/llama-3-8b-instruct"],
            "groq":       ["llama3-8b-8192", "llama3-70b-8192",
                           "mixtral-8x7b-32768", "gemma-7b-it"],
            "custom":     [],
        }.get(b, [])

    def _ai_detect_models(self) -> None:
        """Botão 🔍: lista modelos Ollama instalados e popula o dropdown."""
        b = self.var_ai_backend.get() or "ollama"
        if b != "ollama":
            self._ai_print(f"💡 Detecção automática só funciona com Ollama. "
                            f"Backend atual: {b}\n", tag="status")
            self._ai_model_combo["values"] = self._ai_default_models()
            return

        self._ai_print("🔍 Procurando modelos Ollama instalados...\n", tag="status")
        # Roda em thread pra não travar (3s timeout)
        threading.Thread(target=self._ai_detect_models_thread,
                          daemon=True).start()

    def _ai_detect_models_silent(self) -> None:
        """Mesma coisa que _ai_detect_models mas sem mensagem no chat (auto-boot)."""
        if self.var_ai_backend.get() != "ollama":
            return
        threading.Thread(target=self._ai_detect_models_thread,
                          args=(True,), daemon=True).start()

    def _ai_detect_models_thread(self, silent: bool = False) -> None:
        models = list_ollama_models(self.var_ai_base_url.get())
        self.after(0, self._ai_detect_models_done, models, silent)

    def _ai_detect_models_done(self, models: list[str], silent: bool) -> None:
        if models:
            self._ai_model_combo["values"] = models
            # Se modelo atual não está na lista, seleciona o primeiro
            if self.var_ai_model.get() not in models:
                self.var_ai_model.set(models[0])
            if not silent:
                self._ai_print(f"✓ {len(models)} modelo(s) Ollama: "
                                f"{', '.join(models)}\n\n", tag="status")
        else:
            if not silent:
                self._ai_print("✗ Ollama nao respondeu (rodando em localhost:11434?). "
                                "Usando lista padrao de sugestoes.\n\n", tag="status")
            self._ai_model_combo["values"] = self._ai_default_models()

    # ─────────────────────────────────────────────────────────────
    # CONFIG (modal avançado + persistência)
    # ─────────────────────────────────────────────────────────────
    def _ai_open_advanced(self) -> None:
        """Modal para editar API key e URL base."""
        dlg = tk.Toplevel(self)
        dlg.title("Configuração IA — Avançado")
        dlg.configure(bg=T["bg"])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        f = tk.Frame(dlg, bg=T["bg"])
        f.pack(padx=18, pady=14, fill="both", expand=True)

        tk.Label(f, text="API Key (vazio para Ollama local):",
                 bg=T["bg"], fg=T["text"], font=("Segoe UI", 10)
                 ).grid(row=0, column=0, sticky="w", pady=(0, 2))
        tk.Entry(f, textvariable=self.var_ai_api_key, width=46,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 10), relief="flat", bd=4, show="•"
                 ).grid(row=1, column=0, sticky="we", pady=(0, 10))

        tk.Label(f, text="URL base (opcional — sobrescreve padrão do backend):",
                 bg=T["bg"], fg=T["text"], font=("Segoe UI", 10)
                 ).grid(row=2, column=0, sticky="w", pady=(0, 2))
        tk.Entry(f, textvariable=self.var_ai_base_url, width=46,
                 bg=T["card"], fg=T["text"], insertbackground=T["text"],
                 font=("Consolas", 10), relief="flat", bd=4
                 ).grid(row=3, column=0, sticky="we", pady=(0, 8))

        tk.Label(f, text="Padrão Ollama: http://localhost:11434  •  "
                          "OpenAI: https://api.openai.com/v1",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                 wraplength=420, justify="left"
                 ).grid(row=4, column=0, sticky="w", pady=(0, 6))

        tk.Label(f, text="⚠ A API key é salva em texto plano no JSON do perfil. "
                          "Não é password manager.",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                 wraplength=420, justify="left"
                 ).grid(row=5, column=0, sticky="w")

        btns = tk.Frame(dlg, bg=T["bg"])
        btns.pack(fill="x", padx=18, pady=(0, 14))
        self._btn(btns, "✔ OK",
                   lambda: (self._ai_save_config(), dlg.destroy()),
                   bg=T["accent"], padx=14).pack(side="left", padx=(0, 8))
        self._btn(btns, "✕ Cancelar", dlg.destroy,
                   bg=T["card"], fg=T["text"], padx=14).pack(side="left")

        # Centraliza modal na janela principal
        dlg.update_idletasks()
        px = self.winfo_x() + (self.winfo_width()  - dlg.winfo_width())  // 2
        py = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{px}+{py}")

    def _ai_load_config(self) -> dict:
        """Carrega config de profiles/ai_assistant.json. Retorna {} se não existe."""
        if not os.path.exists(AI_CONFIG_PATH):
            return {}
        try:
            with open(AI_CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _ai_save_config(self) -> None:
        """Persiste config em profiles/ai_assistant.json."""
        os.makedirs(PROFILES_DIR, exist_ok=True)
        try:
            with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "backend":  self.var_ai_backend.get() or "ollama",
                    "model":    self.var_ai_model.get() or "llama3.2",
                    "api_key":  self.var_ai_api_key.get() or "",
                    "base_url": self.var_ai_base_url.get() or "",
                }, f, indent=2)
        except OSError:
            pass
