"""
ui/step_dialog.py — Diálogo modal para adicionar/editar um MacroStep.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk

from core.macro_schema import MacroStep
from ui.widgets import make_button

# Reutiliza o tema de ui/app.py (passado pelo caller) — fallback monocromático
T_DEFAULT = {
    "bg": "#313338", "panel": "#2b2d31", "card": "#232428",
    "accent": "#5865f2", "accent2": "#c7ccff",
    "text": "#dbdee1", "subtext": "#949ba4",
    "green": "#23a55a", "red": "#f23f43", "border": "#3f4147",
    "bg_deep": "#1e1f22", "line": "#3f4147", "line_2": "#4e5058",
    "card_h": "#3f4147", "sel": "#3c4070",
}

# Mapa ação → label e emoji para o Treeview
ACTION_LABELS: dict[str, str] = {
    "click":          "🖱 Click",
    "double_click":   "🖱🖱 Double Click",
    "right_click":    "🖱 Right Click",
    "mouse_down":     "🖱⬇ Mouse Down (segurar)",
    "mouse_up":       "🖱⬆ Mouse Up (soltar)",
    "move":           "➡ Mover",
    "drag":           "↔ Arrastar",
    "type":           "⌨ Digitar",
    "wait":           "⏱ Aguardar",
    "wait_image":     "⏳ Aguardar Imagem",
    "wait_pixel":     "⏳ Aguardar Pixel (cor)",
    "wait_window":    "🪟 Aguardar Janela",
    "scroll":         "🖱 Scroll",
    "key_press":      "🔑 Tecla",
    "pixel_check":    "🎨 Pixel Check",
    "image_click":    "🖼 Image Click",
    "click_text":     "🔤 Click Texto (OCR)",
    "ocr_read":       "📖 OCR (Ler Texto)",
    "set_var":        "📝 Set Variável",
    "clipboard_set":  "📋 Clipboard Set",
    "clipboard_get":  "📋 Clipboard Get",
    "call_macro":     "📞 Chamar Macro",
    "http_request":   "🌐 HTTP Request",
    "ai_prompt":      "🤖 Prompt IA",
    "fishing_pd_track": "🎣 Pesca PD Tracking",
    "note":           "📌 Nota (comentário)",
    "if":             "🔀 If (condição)",
    "else":           "↪ Else",
    "endif":          "⏹ EndIf",
}

OCR_LANGS = ["eng", "por", "spa", "fra", "deu", "ita", "jpn", "chi_sim", "kor", "rus"]
TEXT_MATCH_MODES = ["contains", "exact", "regex"]
VAR_OPS   = ["set", "add", "sub", "mul", "div", "concat", "from_clipboard", "to_clipboard"]
WAIT_IMG_OPS = ["present", "absent"]
CALL_KINDS   = ["slot", "file"]

# Descrição em linguagem leiga de cada ação — usada no diálogo (texto que
# aparece abaixo do dropdown) E nos tooltips do Treeview de steps no macro tab.
ACTION_DESCRIPTIONS: dict[str, str] = {
    "click":        "Clica uma vez num ponto da tela. Use 'Capturar' pra pegar a posição do cursor.",
    "double_click": "Dois cliques rápidos no mesmo ponto. Útil pra abrir arquivos/apps.",
    "right_click":  "Clica com o botão direito — abre menus de contexto.",
    "mouse_down":   "Pressiona e SEGURA o botão do mouse (não solta). Combine com mouse_up depois — útil pra hold/release de pesca, charge attacks, etc.",
    "mouse_up":     "Solta o botão do mouse previamente segurado com mouse_down.",
    "move":         "Só move o cursor pro ponto, sem clicar.",
    "drag":         "Pressiona em A, segura, arrasta até B e solta. Funciona em Roblox/jogos.",
    "type":         "Digita um texto. Use {ENTER}, {TAB}, {F1}…{F12} pra teclas especiais.",
    "wait":         "Pausa por X milissegundos antes do próximo step.",
    "wait_image":   "Espera uma imagem aparecer ou sumir da tela antes de continuar.",
    "wait_pixel":   "Espera um pixel ficar de uma cor específica. Rápido (~5ms reação) — ideal pra skill checks de jogos.",
    "scroll":       "Rola o scroll do mouse (positivo = sobe, negativo = desce).",
    "key_press":    "Aperta uma tecla. Aceita combos como ctrl+c, alt+f4, shift+tab.",
    "pixel_check":  "Lê a cor de um pixel — se bater (ou não), pula N steps. É um 'if' visual.",
    "image_click":  "Procura uma imagem na tela e clica nela. Se move junto se a UI mudar.",
    "click_text":   "Procura uma palavra/frase na tela (qualquer fonte/cor) e clica. Ex: digite 'EASY' e ele clica onde achar.",
    "ocr_read":     "Lê texto de uma região da tela e guarda numa variável.",
    "set_var":      "Cria/altera variável: set, add, sub, mul, div, concat, e ler/escrever clipboard.",
    "clipboard_set":"Copia um texto pro clipboard (área de transferência). Aceita {variavel} pra interpolar.",
    "clipboard_get":"Lê o texto atual do clipboard e salva numa variável pra usar depois.",
    "wait_window":  "Pausa o macro até uma janela com título (parcial) aparecer. Útil pra esperar app abrir.",
    "call_macro":   "Executa outro macro inteiro (slot 1/2/3 ou arquivo .json). Reusa lógica.",
    "http_request": "Chama uma API REST (Discord webhook, Telegram bot, Home Assistant, etc). Salva a resposta numa variável.",
    "ai_prompt":    "Manda um prompt pra uma IA (Ollama local grátis, ou OpenAI/Groq/OpenRouter). Salva a resposta numa variável. Aceita {variavel} no prompt.",
    "fishing_pd_track": "Pesca avancada com PD control: rastreia marcador movel via 3 cores (guia + peixe + alvo) e segura/solta o mouse pra manter alinhado. Pra GPO Roblox e jogos similares.",
    "note":         "Nao faz nada — so exibe um label/comentario na lista de steps. Use pra documentar macros longos.",
    "if":           "Inicia bloco condicional. Steps até Else/EndIf rodam só se a condição der true.",
    "else":         "Marca o bloco que roda se o If for falso. Precisa estar entre If e EndIf.",
    "endif":        "Fecha o bloco If/Else.",
}
COND_TYPES = ["var", "image", "pixel"]
COND_OPS_VAR    = ["==", "!=", "<", ">", "<=", ">=", "contains", "starts_with"]
COND_OPS_IMAGE  = ["present", "absent"]
COND_OPS_PIXEL  = ["match", "no_match"]

ACTIONS = list(ACTION_LABELS.keys())

# Categoria de cada acao — usada pra cor de fundo no Treeview de steps
# (ver ui/theme.py CATEGORY_TINTS_*). Toda nova acao precisa entrar aqui.
ACTION_CATEGORY: dict[str, str] = {
    "click": "mouse", "double_click": "mouse", "right_click": "mouse",
    "mouse_down": "mouse", "mouse_up": "mouse",
    "move": "mouse", "drag": "mouse", "scroll": "mouse",
    "type": "keyboard", "key_press": "keyboard",
    "wait": "wait", "wait_image": "wait", "wait_pixel": "wait", "wait_window": "wait",
    "pixel_check": "vision", "image_click": "vision",
    "click_text": "vision", "ocr_read": "vision",
    "if": "logic", "else": "logic", "endif": "logic", "call_macro": "logic",
    "set_var": "variable", "clipboard_set": "variable", "clipboard_get": "variable",
    "http_request": "integration", "ai_prompt": "integration",
    "fishing_pd_track": "fishing",
    "note": "note",
}


def get_action_category(action: str) -> str:
    """Retorna categoria do step (ex: 'mouse', 'vision') — default '_default'."""
    return ACTION_CATEGORY.get(action, "_default")


# Label amigavel de cada categoria + ordem de exibicao no picker.
CATEGORY_LABELS: dict[str, str] = {
    "mouse":       "🖱  Mouse & Cliques",
    "keyboard":    "⌨  Teclado",
    "wait":        "⏱  Esperas",
    "vision":      "👁  Visão (OCR, Imagem, Pixel)",
    "logic":       "🔀  Lógica & Fluxo",
    "variable":    "📝  Variáveis",
    "integration": "🌐  Integrações (HTTP, IA)",
    "fishing":     "🎣  Pesca",
    "note":        "📌  Comentários",
}
CATEGORY_ORDER: list[str] = list(CATEGORY_LABELS.keys())

# Teclas comuns para key_press
COMMON_KEYS = [
    "enter", "tab", "escape", "space", "backspace", "delete",
    "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "f10", "f11", "f12",
    "ctrl", "alt", "shift", "win",
    "ctrl+c", "ctrl+v", "ctrl+z", "ctrl+a",
]


def step_to_params_str(step: MacroStep) -> str:
    """Gera string resumida de parâmetros para exibição no Treeview."""
    a = step.action
    if a in ("click", "double_click", "right_click", "move"):
        coord = f"({step.x}, {step.y})" if step.x is not None else "(cursor)"
        if a != "move":
            return f"{coord} {step.button}"
        return coord
    elif a == "mouse_down":
        coord = f"({step.x}, {step.y}) " if step.x is not None else ""
        return f"{coord}{step.button} ⬇ segura"
    elif a == "mouse_up":
        return f"{step.button} ⬆ solta"
    elif a == "drag":
        src = f"({step.x},{step.y})" if step.x is not None else "(?)"
        dst = f"({step.x2},{step.y2})" if step.x2 is not None else "(?)"
        return f"{src} → {dst} {step.drag_duration_ms}ms {step.button}"
    elif a == "wait_image":
        wf = step.image_wait_for or "present"
        has = "✓" if step.image_data else "✗"
        return f"{wf} ({has} tpl) timeout={step.image_timeout_ms}ms"
    elif a == "wait_pixel":
        coord = f"({step.x}, {step.y})" if step.x is not None else "(?)"
        rgb = f"RGB{tuple(step.color_rgb)}" if step.color_rgb else "RGB(?)"
        wf = step.image_wait_for or "present"
        return f"{coord} {rgb} tol={step.color_tolerance} {wf} t/o={step.image_timeout_ms}ms"
    elif a == "call_macro":
        import os
        kind = step.call_target_kind or "slot"
        if kind == "slot":
            return f"slot {step.call_target}"
        return f"file: {os.path.basename(step.call_target or '?')}"
    elif a == "type":
        txt = (step.text or "")[:30]
        return f'"{txt}"' + ("…" if len(step.text or "") > 30 else "")
    elif a == "wait":
        if (step.delay_ms_max and step.delay_ms_max > 0
                and step.delay_ms_max >= max(0, step.delay_ms_min or 0)):
            return f"{step.delay_ms_min or 0}-{step.delay_ms_max} ms (rand)"
        return f"{step.delay_ms} ms"
    elif a == "note":
        txt = (step.text or "")[:60]
        return f"📌 {txt}" + ("…" if len(step.text or "") > 60 else "")
    elif a == "scroll":
        coord = f"({step.x}, {step.y})" if step.x is not None else "(cursor)"
        dire = "↑" if step.scroll_dy > 0 else "↓"
        return f"{coord} {dire}{abs(step.scroll_dy)}"
    elif a == "key_press":
        return step.key or ""
    elif a == "pixel_check":
        coord = f"({step.x}, {step.y})" if step.x is not None else "(cursor)"
        rgb = f"RGB{tuple(step.color_rgb)}" if step.color_rgb else "RGB(?)"
        cond = "==" if step.color_condition == "match" else "!="
        return f"{coord} {rgb} tol={step.color_tolerance} {cond} skip={step.skip_steps}"
    elif a == "image_click":
        has = "✓ template" if step.image_data else "sem template"
        thr = f"{int(step.image_threshold * 100)}%"
        return f"{has}  conf={thr}  timeout={step.image_timeout_ms}ms  skip={step.image_skip_steps}"
    elif a == "click_text":
        txt = (step.text_to_find or "")[:20] or "(vazio)"
        scope = "região" if step.text_use_region else "tela inteira"
        case = " Aa" if step.text_case_sensitive else ""
        return f"'{txt}' [{step.text_match_mode}{case}] {scope}  skip={step.text_skip_steps}"
    elif a == "ocr_read":
        var = step.ocr_var or "?"
        size = f"{step.ocr_w}×{step.ocr_h}" if step.ocr_w and step.ocr_h else "?"
        num = " (num)" if step.ocr_to_number else ""
        return f"({step.x},{step.y}) {size} → {{{var}}} [{step.ocr_lang}]{num}"
    elif a == "set_var":
        name = step.var_name or "?"
        return f"{{{name}}} {step.var_op} {step.var_value!r}"
    elif a == "clipboard_set":
        v = (step.var_value or "")[:30]
        return f"clipboard ← {v!r}" + ("…" if len(step.var_value or "") > 30 else "")
    elif a == "clipboard_get":
        name = step.var_name or "?"
        return f"{{{name}}} ← clipboard"
    elif a == "wait_window":
        title = (step.window_title or "?")[:30]
        return f"'{title}' timeout={step.window_timeout_ms}ms"
    elif a == "http_request":
        method = step.http_method or "POST"
        url = step.http_url or "?"
        if len(url) > 40:
            url = url[:37] + "…"
        extras = []
        if step.http_auth_kind and step.http_auth_kind != "none":
            extras.append(step.http_auth_kind)
        if step.var_name:
            extras.append(f"→{{{step.var_name}}}")
        return f"{method} {url}" + (f"  [{' '.join(extras)}]" if extras else "")
    elif a == "fishing_pd_track":
        guide = f"RGB{tuple(step.color_rgb)}" if step.color_rgb else "RGB(?)"
        region = f"{step.ocr_w}x{step.ocr_h}" if step.ocr_w and step.ocr_h else "?"
        extras = []
        if step.fish_wall_ratio and step.fish_wall_ratio > 0:
            extras.append(f"wall={step.fish_wall_ratio}")
        if step.fish_fps and step.fish_fps != 30:
            extras.append(f"fps={step.fish_fps}")
        extra_str = f"  [{' '.join(extras)}]" if extras else ""
        return f"({step.x},{step.y}) {region}  guia={guide}  kp={step.fish_kp} kd={step.fish_kd}{extra_str}"
    elif a == "ai_prompt":
        backend = step.ai_backend or "ollama"
        model   = step.ai_model or "?"
        preview = (step.ai_prompt_text or "")[:28]
        if len(step.ai_prompt_text or "") > 28:
            preview += "…"
        out = f"[{backend}/{model}]  \"{preview}\""
        if getattr(step, "ai_vision_enabled", False):
            out += "  👁"
        if step.var_name:
            out += f"  →{{{step.var_name}}}"
        return out
    elif a == "if":
        ct = step.cond_type or "var"
        op = step.cond_op or ""
        if ct == "var":
            return f"if {{{step.var_name or '?'}}} {op} {step.cond_value!r}"
        if ct == "image":
            has = "✓" if step.image_data else "✗"
            thr = int((step.image_threshold or 0.9) * 100)
            return f"if image {op} ({has} tpl, conf={thr}%)"
        if ct == "pixel":
            rgb = f"RGB{tuple(step.color_rgb)}" if step.color_rgb else "RGB(?)"
            return f"if pixel ({step.x},{step.y}) {op} {rgb} tol={step.color_tolerance}"
        return f"if {ct}"
    elif a == "else":  return "—"
    elif a == "endif": return "—"
    return ""


class ActionPickerDialog(tk.Toplevel):
    """Modal estilo Spotlight: busca acoes por nome/descricao + agrupamento por categoria.

    Substitui o Combobox de 25+ itens. Permite achar qualquer step com 2 cliques
    ou digitando 2-3 letras.

    Uso:
        picker = ActionPickerDialog(parent, T, current_action="click")
        parent.wait_window(picker)
        if picker.result:
            ... usar picker.result (str: action name)
    """

    def __init__(self, parent: tk.Tk, T: dict, current_action: str = "click") -> None:
        super().__init__(parent)
        self._T = T
        self.result: str | None = None
        self._current = current_action

        self.title("Escolher ação")
        self.configure(bg=T["bg"])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._build()
        self._populate()

        self.update_idletasks()
        # Centraliza no parent
        try:
            px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
            py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        # Foco no search box
        self._search_entry.focus_set()

    def _build(self) -> None:
        T = self._T

        # ── Search box ───────────────────────────────────────────
        top = tk.Frame(self, bg=T["bg"])
        top.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(top, text="🔍", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 13)).pack(side="left", padx=(0, 6))
        self._var_search = tk.StringVar()
        self._search_entry = tk.Entry(
            top, textvariable=self._var_search,
            bg=T["card"], fg=T["text"], insertbackground=T["text"],
            font=("Segoe UI", 12), relief="flat", bd=6,
        )
        self._search_entry.pack(side="left", fill="x", expand=True)
        self._var_search.trace_add("write", lambda *_: self._refilter())

        # Hint debaixo do search
        tk.Label(self, text="Digite pra filtrar  •  ↑↓ navegar  •  Enter selecionar  •  Esc cancelar",
                 bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                 ).pack(fill="x", padx=14, pady=(0, 6))

        # ── Treeview com categorias e acoes ──────────────────────
        tree_frame = tk.Frame(self, bg=T["bg"])
        tree_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

        self._tree = ttk.Treeview(
            tree_frame, columns=("label",), show="tree",
            height=14, selectmode="browse", style="Seq.Treeview",
        )
        self._tree.column("#0", width=40, stretch=False)   # icon/expand
        self._tree.column("label", width=420, anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Descricao da acao selecionada
        self._desc_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._desc_var, bg=T["bg"], fg=T["accent2"],
                 font=("Segoe UI", 9, "italic"), wraplength=460, justify="left",
                 anchor="w", height=2
                 ).pack(fill="x", padx=14, pady=(0, 8))

        # ── Botoes ───────────────────────────────────────────────
        btns = tk.Frame(self, bg=T["bg"])
        btns.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(btns, text="Cancelar", command=self._on_cancel,
                  bg=T["card"], fg=T["text"], activebackground=T["card_h"],
                  font=("Segoe UI", 10), relief="flat", padx=14, pady=6,
                  cursor="hand2"
                  ).pack(side="right", padx=(4, 0))
        tk.Button(btns, text="Selecionar", command=self._on_confirm,
                  bg=T["accent"], fg="white", activebackground=T["accent_h"],
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=14, pady=6,
                  cursor="hand2"
                  ).pack(side="right")

        # ── Bindings ─────────────────────────────────────────────
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda e: self._on_confirm())
        self.bind("<Return>", lambda e: self._on_confirm())
        self.bind("<Escape>", lambda e: self._on_cancel())
        # Setas no search saltam pro tree
        self._search_entry.bind("<Down>", self._search_to_tree)
        self._search_entry.bind("<Return>", lambda e: self._on_confirm())

    def _search_to_tree(self, _e=None):
        """Setinha pra baixo no search: move foco pro primeiro item do tree."""
        children = self._tree.get_children()
        if children:
            # Primeiro item visivel pode ser categoria — desce pra primeira acao real
            for cat_id in children:
                actions = self._tree.get_children(cat_id)
                if actions:
                    self._tree.focus(actions[0])
                    self._tree.selection_set(actions[0])
                    self._tree.see(actions[0])
                    break
            self._tree.focus_set()
        return "break"

    def _populate(self) -> None:
        """Reconstroi tree com todas as categorias + acoes. Selecao inicial = current."""
        # Configura tags de cor por categoria (mesmo padrao do macro_tree)
        try:
            from ui.theme import CT
            for cat, color in CT.items():
                self._tree.tag_configure(cat, background=color, foreground=self._T["text"])
        except Exception:
            pass

        self._rebuild_items("")

        # Tenta selecionar a acao atual via iid (formato: "act::<action>")
        target_iid = f"act::{self._current}"
        if self._tree.exists(target_iid):
            self._tree.selection_set(target_iid)
            self._tree.focus(target_iid)
            self._tree.see(target_iid)
            self._update_desc(self._current)

    def _rebuild_items(self, query: str) -> None:
        """Limpa tree e reinsere filtrado por query (case-insensitive)."""
        for item in self._tree.get_children():
            self._tree.delete(item)

        q = query.strip().lower()
        for cat in CATEGORY_ORDER:
            # Coleta acoes dessa categoria que casam com query
            matches = []
            for action, cat_name in ACTION_CATEGORY.items():
                if cat_name != cat:
                    continue
                label = ACTION_LABELS.get(action, action)
                desc  = ACTION_DESCRIPTIONS.get(action, "")
                if not q or q in label.lower() or q in action.lower() or q in desc.lower():
                    matches.append((action, label, desc))
            if not matches:
                continue
            cat_label = CATEGORY_LABELS.get(cat, cat)
            cat_id = self._tree.insert("", "end", text="", values=(cat_label,),
                                        open=True, tags=())
            for action, label, _desc in matches:
                # iid="act::<action>" — usado pelo _on_confirm pra extrair acao
                self._tree.insert(cat_id, "end", text="", iid=f"act::{action}",
                                   values=(f"   {label}",), tags=(cat,))

        # Mostra contador no desc se houve filtragem
        if q:
            total = sum(len(self._tree.get_children(c)) for c in self._tree.get_children())
            if total == 0:
                self._desc_var.set(f"Nenhuma acao encontrada para '{query}'.")
            else:
                self._desc_var.set(f"{total} resultado(s) para '{query}'.")
        else:
            self._desc_var.set("")

    def _refilter(self) -> None:
        self._rebuild_items(self._var_search.get())
        # Auto-seleciona o primeiro match (entao Enter funciona direto)
        for cat_id in self._tree.get_children():
            for item in self._tree.get_children(cat_id):
                self._tree.selection_set(item)
                self._tree.focus(item)
                self._tree.see(item)
                # Atualiza descricao
                act = item[len("act::"):] if item.startswith("act::") else ""
                if act:
                    self._update_desc(act)
                return

    def _update_desc(self, action: str) -> None:
        desc = ACTION_DESCRIPTIONS.get(action, "")
        if not desc and not self._var_search.get():
            self._desc_var.set("")
        elif desc:
            self._desc_var.set(desc)

    def _on_select(self, _e=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("act::"):
            self._update_desc(iid[len("act::"):])

    def _on_confirm(self, _e=None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("act::"):
            self.result = iid[len("act::"):]
            self.destroy()

    def _on_cancel(self, _e=None) -> None:
        self.result = None
        self.destroy()


class StepDialog(tk.Toplevel):
    """Diálogo modal para criar ou editar um MacroStep."""

    def __init__(
        self,
        parent: tk.Tk,
        T: dict,
        driver=None,
        step: MacroStep | None = None,
    ) -> None:
        super().__init__(parent)
        self._T      = T
        self._driver = driver
        self._result: MacroStep | None = None

        self.title("Editar Step" if step else "Adicionar Step")
        self.configure(bg=T["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build(step)

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    # ─────────────────────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────────────────────
    def _build(self, step: MacroStep | None) -> None:
        T = self._T
        p = self  # raiz do diálogo

        # ── Tipo de ação ─────────────────────────────────────────
        top = tk.Frame(p, bg=T["bg"])
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Tipo de ação:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 10)).pack(side="left")

        self._var_action = tk.StringVar(value=step.action if step else "click")
        # Botao que abre ActionPickerDialog (Spotlight-style com search + categorias)
        # Substitui o antigo Combobox de 25+ itens flat.
        self._action_btn_var = tk.StringVar()
        self._set_action_btn_label(self._var_action.get())
        action_btn = tk.Button(
            top, textvariable=self._action_btn_var, command=self._open_action_picker,
            bg=T["card"], fg=T["text"], activebackground=T["card_h"],
            font=("Segoe UI", 10), relief="flat", padx=12, pady=4,
            cursor="hand2", anchor="w", width=28,
        )
        action_btn.pack(side="left", padx=8)

        # ── Descrição da ação (atualiza dinamicamente em _refresh_fields) ──
        self._desc_label = tk.Label(p, text="", bg=T["bg"], fg=T["accent2"],
                                     font=("Segoe UI", 9, "italic"),
                                     wraplength=440, justify="left", anchor="w")
        self._desc_label.pack(fill="x", padx=16, pady=(0, 4))

        # ── Campos dinâmicos ─────────────────────────────────────
        self._fields_frame = tk.Frame(p, bg=T["bg"])
        self._fields_frame.pack(fill="x", padx=16, pady=4)

        # Variáveis de estado
        self._var_x         = tk.StringVar(value=str(step.x) if step and step.x is not None else "")
        self._var_y         = tk.StringVar(value=str(step.y) if step and step.y is not None else "")
        self._var_delay     = tk.StringVar(value=str(step.delay_ms) if step else "0")
        self._var_button    = tk.StringVar(value=step.button if step else "left")
        self._var_text      = tk.StringVar()
        self._var_key       = tk.StringVar(value=step.key if step and step.key else "enter")
        self._var_scroll_dy = tk.StringVar(value=str(step.scroll_dy) if step else "3")
        self._var_scroll_smooth = tk.BooleanVar(
            value=bool(getattr(step, "scroll_smooth", False)) if step else False)
        self._var_repeat    = tk.StringVar(value=str(step.repeat) if step else "1")
        self._var_wait_min  = tk.StringVar(value=str(step.delay_ms_min) if step and step.delay_ms_min else "0")
        self._var_wait_max  = tk.StringVar(value=str(step.delay_ms_max) if step and step.delay_ms_max else "0")
        self._text_widget: tk.Text | None = None
        self._note_text_widget: tk.Text | None = None
        # pixel_check
        _rgb = step.color_rgb if step and step.color_rgb else [0, 0, 0]
        self._var_color_r   = tk.StringVar(value=str(_rgb[0]))
        self._var_color_g   = tk.StringVar(value=str(_rgb[1]))
        self._var_color_b   = tk.StringVar(value=str(_rgb[2]))
        self._var_tolerance = tk.StringVar(value=str(step.color_tolerance) if step else "10")
        self._var_skip      = tk.StringVar(value=str(step.skip_steps) if step else "1")
        self._var_condition = tk.StringVar(value=step.color_condition if step else "match")
        self._color_preview: tk.Label | None = None
        # image_click
        self._image_data_b64: str | None = step.image_data if step else None
        self._image_preview_label: tk.Label | None = None
        self._var_threshold   = tk.StringVar(
            value=str(int(step.image_threshold * 100)) if step else "90")
        self._var_img_timeout = tk.StringVar(
            value=str(step.image_timeout_ms) if step else "5000")
        self._var_img_skip    = tk.StringVar(
            value=str(step.image_skip_steps) if step else "0")
        # ocr_read
        self._var_ocr_w        = tk.StringVar(value=str(step.ocr_w) if step else "0")
        self._var_ocr_h        = tk.StringVar(value=str(step.ocr_h) if step else "0")
        self._var_ocr_var      = tk.StringVar(value=step.ocr_var if step else "texto")
        self._var_ocr_lang     = tk.StringVar(value=step.ocr_lang if step else "eng")
        self._var_ocr_whitelist = tk.StringVar(value=step.ocr_whitelist if step else "")
        self._var_ocr_to_number = tk.BooleanVar(value=bool(step.ocr_to_number) if step else False)
        self._lbl_ocr_test: tk.Label | None = None
        # set_var
        self._var_var_name  = tk.StringVar(value=step.var_name if step else "contador")
        self._var_var_value = tk.StringVar(value=step.var_value if step else "0")
        self._var_var_op    = tk.StringVar(value=step.var_op if step else "set")
        # if/condition
        self._var_cond_type  = tk.StringVar(value=step.cond_type if step else "var")
        self._var_cond_op    = tk.StringVar(value=step.cond_op if step else "==")
        self._var_cond_value = tk.StringVar(value=step.cond_value if step else "")
        # drag
        self._var_x2 = tk.StringVar(value=str(step.x2) if step and step.x2 is not None else "")
        self._var_y2 = tk.StringVar(value=str(step.y2) if step and step.y2 is not None else "")
        self._var_drag_duration = tk.StringVar(
            value=str(step.drag_duration_ms) if step else "300")
        # wait_image
        self._var_img_wait_for = tk.StringVar(
            value=step.image_wait_for if step else "present")
        # call_macro
        self._var_call_kind   = tk.StringVar(
            value=step.call_target_kind if step else "slot")
        self._var_call_target = tk.StringVar(
            value=step.call_target if step else "1")
        # click_text
        self._var_text_to_find    = tk.StringVar(
            value=step.text_to_find if step else "")
        self._var_text_match_mode = tk.StringVar(
            value=step.text_match_mode if step else "contains")
        self._var_text_case       = tk.BooleanVar(
            value=bool(step.text_case_sensitive) if step else False)
        self._var_text_use_region = tk.BooleanVar(
            value=bool(step.text_use_region) if step else False)
        self._var_text_skip       = tk.StringVar(
            value=str(step.text_skip_steps) if step else "0")
        # wait_window
        self._var_window_title      = tk.StringVar(
            value=step.window_title if step else "")
        self._var_window_timeout_ms = tk.StringVar(
            value=str(step.window_timeout_ms) if step else "5000")
        # http_request
        self._var_http_url           = tk.StringVar(value=step.http_url if step else "")
        self._var_http_method        = tk.StringVar(value=step.http_method if step else "POST")
        self._var_http_body          = tk.StringVar(value=step.http_body if step else "")
        self._var_http_headers       = tk.StringVar(value=step.http_headers if step else "")
        self._var_http_auth_kind     = tk.StringVar(value=step.http_auth_kind if step else "none")
        self._var_http_auth_value    = tk.StringVar(value=step.http_auth_value if step else "")
        self._var_http_timeout       = tk.StringVar(value=str(step.http_timeout_s) if step else "10")
        self._var_http_save_status   = tk.StringVar(value=step.http_save_status_var if step else "")
        # Auto-expande "Avançado" se step já tem qualquer config avançada preenchida
        self._var_http_show_advanced = tk.BooleanVar(value=bool(
            step and (step.http_headers or (step.http_auth_kind and step.http_auth_kind != "none")
                      or step.http_save_status_var or (step.action == "http_request" and step.var_name))
        ))
        self._http_body_widget: tk.Text | None = None
        self._http_headers_widget: tk.Text | None = None
        # ai_prompt
        self._var_ai_backend       = tk.StringVar(value=step.ai_backend if step else "ollama")
        self._var_ai_model         = tk.StringVar(value=step.ai_model if step else "")
        self._var_ai_prompt_text   = tk.StringVar(value=step.ai_prompt_text if step else "")
        self._var_ai_system_prompt = tk.StringVar(value=step.ai_system_prompt if step else "")
        self._var_ai_temperature   = tk.StringVar(value=str(step.ai_temperature) if step else "0.7")
        self._var_ai_base_url      = tk.StringVar(value=step.ai_base_url if step else "")
        self._var_ai_api_key       = tk.StringVar(value=step.ai_api_key if step else "")
        self._var_ai_timeout       = tk.StringVar(value=str(step.ai_timeout_s) if step else "30")
        self._var_ai_show_advanced = tk.BooleanVar(value=bool(
            step and step.action == "ai_prompt"
            and (step.ai_system_prompt or step.ai_api_key or step.ai_base_url)
        ))
        self._var_ai_vision_enabled = tk.BooleanVar(
            value=bool(step and getattr(step, "ai_vision_enabled", False)))
        self._ai_prompt_widget: tk.Text | None = None
        self._ai_system_widget: tk.Text | None = None
        # fishing_pd_track — cores do player e target (RGB sets separados)
        _pc = step.fish_player_color if step and step.fish_player_color else [255, 255, 255]
        _tc = step.fish_target_color if step and step.fish_target_color else [25, 25, 25]
        self._var_fish_player_r = tk.StringVar(value=str(_pc[0]))
        self._var_fish_player_g = tk.StringVar(value=str(_pc[1]))
        self._var_fish_player_b = tk.StringVar(value=str(_pc[2]))
        self._var_fish_target_r = tk.StringVar(value=str(_tc[0]))
        self._var_fish_target_g = tk.StringVar(value=str(_tc[1]))
        self._var_fish_target_b = tk.StringVar(value=str(_tc[2]))
        self._var_fish_kp = tk.StringVar(value=str(step.fish_kp) if step else "0.3")
        self._var_fish_kd = tk.StringVar(value=str(step.fish_kd) if step else "0.15")
        self._var_fish_pd_clamp   = tk.StringVar(value=str(step.fish_pd_clamp) if step else "1.0")
        self._var_fish_min_pixels = tk.StringVar(value=str(step.fish_min_pixels) if step else "3")
        self._var_fish_wall_ratio = tk.StringVar(value=str(step.fish_wall_ratio) if step else "0.0")
        self._var_fish_fps        = tk.StringVar(value=str(step.fish_fps) if step else "30")

        if step and step.text:
            self._var_text.set(step.text)

        self._refresh_fields()

        # ── Botões OK / Cancelar ─────────────────────────────────
        btns = tk.Frame(p, bg=T["bg"])
        btns.pack(fill="x", padx=16, pady=(8, 14))
        self._btn(btns, "✔ OK", self._ok,
                  T["accent"]).pack(side="left", padx=(0, 8))
        self._btn(btns, "✕ Cancelar", self.destroy,
                  T["card"], fg=T["text"]).pack(side="left")

    def _set_action_btn_label(self, action: str) -> None:
        """Atualiza o texto do botao de acao (com seta de dropdown)."""
        label = ACTION_LABELS.get(action, action)
        self._action_btn_var.set(f"{label}   ▾")

    def _open_action_picker(self) -> None:
        """Abre o ActionPickerDialog (Spotlight com search) pra trocar de acao."""
        picker = ActionPickerDialog(self, self._T,
                                     current_action=self._var_action.get())
        self.wait_window(picker)
        if picker.result and picker.result != self._var_action.get():
            self._var_action.set(picker.result)
            self._set_action_btn_label(picker.result)
            self._refresh_fields()

    def _refresh_fields(self) -> None:
        """Reconstrói os campos dinâmicos conforme a ação selecionada."""
        T = self._T
        for w in self._fields_frame.winfo_children():
            w.destroy()
        self._text_widget = None

        action = self._var_action.get()
        # Atualiza label do botao (caso _refresh_fields seja chamado sem passar pelo picker)
        if hasattr(self, "_action_btn_var"):
            self._set_action_btn_label(action)
        # Atualiza descrição leiga abaixo do dropdown
        if hasattr(self, "_desc_label"):
            self._desc_label.config(text=ACTION_DESCRIPTIONS.get(action, ""))
        f = self._fields_frame

        def lbl(text, row, col=0):
            tk.Label(f, text=text, bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10), anchor="w").grid(
                     row=row, column=col, sticky="w", pady=3, padx=(0, 6))

        def entry(var, row, col=1, w=8):
            tk.Entry(f, textvariable=var, width=w, bg=T["card"], fg=T["text"],
                     insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4).grid(
                     row=row, column=col, sticky="w")

        if action == "drag":
            lbl("X1 (início):", 0); entry(self._var_x, 0)
            lbl("Y1 (início):", 1); entry(self._var_y, 1)
            self._btn(f, "📍 Capturar Início (3s)", self._capture_xy,
                       T["accent2"], padx=6, pady=3
                       ).grid(row=0, column=2, rowspan=2, padx=8)
            lbl("X2 (fim):", 2); entry(self._var_x2, 2)
            lbl("Y2 (fim):", 3); entry(self._var_y2, 3)
            self._btn(f, "📍 Capturar Fim (3s)", self._capture_xy2,
                       T["accent2"], padx=6, pady=3
                       ).grid(row=2, column=2, rowspan=2, padx=8)
            lbl("Duração (ms):", 4)
            tk.Spinbox(f, textvariable=self._var_drag_duration, from_=50, to=5000,
                       increment=50, width=7, bg=T["card"], fg=T["text"],
                       relief="flat", font=("Consolas", 10)
                       ).grid(row=4, column=1, sticky="w")
            lbl("Botão:", 5)
            for c, (txt, val) in enumerate([("Esquerdo","left"),("Direito","right"),("Meio","middle")]):
                tk.Radiobutton(f, text=txt, variable=self._var_button, value=val,
                               bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                               activebackground=T["bg"],
                               font=("Segoe UI", 10)).grid(row=5, column=c+1, sticky="w")
            tk.Label(f, text="Funciona no Roblox e jogos DirectX (SendInput nativo).",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(4,0))
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "wait_image":
            cap_btn = self._btn(f, "📷 Capturar Região", self._capture_image_region,
                                T["accent2"], padx=8, pady=4)
            cap_btn.grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
            self._image_preview_label = tk.Label(f, bg=T["card"], width=8, height=4,
                                                  text="sem\ntemplate", fg=T["subtext"])
            self._image_preview_label.grid(row=0, column=2, rowspan=2, padx=8)
            self._update_image_preview()
            lbl("Aguardar:", 2)
            ttk.Combobox(f, textvariable=self._var_img_wait_for, values=WAIT_IMG_OPS,
                         state="readonly", width=12, font=("Segoe UI", 10)
                         ).grid(row=2, column=1, sticky="w")
            tk.Label(f, text="present = espera aparecer  •  absent = espera sumir",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=3, column=0, columnspan=3, sticky="w")
            lbl("Confiança (%):", 4)
            tk.Spinbox(f, textvariable=self._var_threshold, from_=50, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=4, column=1, sticky="w")
            lbl("Timeout (ms):", 5)
            entry(self._var_img_timeout, 5)
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "wait_pixel":
            lbl("X:", 0); entry(self._var_x, 0)
            lbl("Y:", 1); entry(self._var_y, 1)
            self._btn(f, "🎨 Capturar Cor (3s)", self._capture_color,
                      T["accent2"], padx=6, pady=3
                      ).grid(row=0, column=2, padx=8)
            self._btn(f, "🎯 Picker Visual", self._open_color_picker,
                      T["accent2"], padx=6, pady=3
                      ).grid(row=1, column=2, padx=8)
            self._color_preview = tk.Label(f, text="  ", bg=self._rgb_hex(),
                                           relief="solid", bd=1, width=4)
            self._color_preview.grid(row=0, column=3, rowspan=2, padx=4)

            lbl("R:", 2); entry(self._var_color_r, 2, w=5)
            lbl("G:", 3); entry(self._var_color_g, 3, w=5)
            lbl("B:", 4); entry(self._var_color_b, 4, w=5)
            for v in (self._var_color_r, self._var_color_g, self._var_color_b):
                v.trace_add("write", lambda *_: self._update_color_preview())

            lbl("Tolerância:", 5)
            tk.Spinbox(f, textvariable=self._var_tolerance, from_=0, to=255,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=5, column=1, sticky="w")
            tk.Label(f, text="0=exata; 20-40=tolera leve variação de iluminação",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=5, column=2, columnspan=2, sticky="w")

            lbl("Aguardar:", 6)
            ttk.Combobox(f, textvariable=self._var_img_wait_for, values=WAIT_IMG_OPS,
                         state="readonly", width=12, font=("Segoe UI", 10)
                         ).grid(row=6, column=1, sticky="w")
            tk.Label(f, text="present = espera a cor aparecer • absent = espera sumir",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=7, column=1, columnspan=3, sticky="w")

            lbl("Timeout (ms):", 8)
            entry(self._var_img_timeout, 8)
            tk.Label(f, text="Polling ~200Hz (5ms entre samples). Use 200-500ms pra skill checks.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=420, justify="left"
                     ).grid(row=9, column=1, columnspan=3, sticky="w")

            lbl("Pular N steps se timeout:", 10)
            tk.Spinbox(f, textvariable=self._var_img_skip, from_=0, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=10, column=1, sticky="w")
            tk.Label(f, text="Útil em loops: se a cor não veio, pula o key_press seguinte e tenta no próximo ciclo.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=420, justify="left"
                     ).grid(row=11, column=0, columnspan=4, sticky="w")

            lbl("Delay pré-step (ms):", 12)
            entry(self._var_delay, 12)
            return

        if action == "call_macro":
            lbl("Tipo de destino:", 0)
            ttk.Combobox(f, textvariable=self._var_call_kind, values=CALL_KINDS,
                         state="readonly", width=10, font=("Segoe UI", 10)
                         ).grid(row=0, column=1, sticky="w")
            self._var_call_kind.trace_add("write", lambda *_: self._refresh_fields())
            kind = self._var_call_kind.get() or "slot"
            if kind == "slot":
                lbl("Slot:", 1)
                # Garante que valor é "1", "2" ou "3"; se vier algo inválido, reseta
                if self._var_call_target.get() not in ("1", "2", "3"):
                    self._var_call_target.set("1")
                ttk.Combobox(f, textvariable=self._var_call_target,
                             values=["1", "2", "3"], state="readonly",
                             width=6, font=("Consolas", 11)
                             ).grid(row=1, column=1, sticky="w")
                tk.Label(f, text="Executa o macro salvo no slot escolhido.",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=2, column=0, columnspan=3, sticky="w")
            else:
                lbl("Arquivo:", 1)
                tk.Entry(f, textvariable=self._var_call_target, width=32, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 10),
                         relief="flat", bd=4).grid(row=1, column=1, columnspan=2, sticky="w")
                self._btn(f, "📂 Procurar", self._pick_macro_file, T["accent2"],
                           padx=6, pady=3).grid(row=1, column=3, padx=4)
                tk.Label(f, text="Caminho .json de um perfil exportado.",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=2, column=0, columnspan=4, sticky="w")
            tk.Label(f, text="⚠ Variáveis e contexto são compartilhados.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=3, column=0, columnspan=4, sticky="w")
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action in ("click", "double_click", "right_click", "move", "scroll"):
            lbl("X:", 0)
            entry(self._var_x, 0)
            lbl("Y:", 1)
            entry(self._var_y, 1)
            cap_btn = self._btn(f, "📍 Capturar (3s)", self._capture_xy, T["accent2"],
                                padx=6, pady=3)
            cap_btn.grid(row=0, column=2, rowspan=2, padx=8)
            if action in ("click", "double_click"):
                lbl("Botão:", 2)
                for c, (txt, val) in enumerate([("Esquerdo","left"),("Direito","right"),("Meio","middle")]):
                    tk.Radiobutton(f, text=txt, variable=self._var_button, value=val,
                                   bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                                   activebackground=T["bg"],
                                   font=("Segoe UI", 10)).grid(row=2, column=c+1, sticky="w")
            if action == "scroll":
                lbl("Scroll dy:", 2)
                tk.Label(f, text="(+ cima / − baixo)", bg=T["bg"], fg=T["subtext"],
                         font=("Segoe UI", 8)).grid(row=3, column=1, columnspan=2, sticky="w")
                entry(self._var_scroll_dy, 2)
                tk.Checkbutton(
                    f, text="Scroll suave (interpola — mais fluido em navegadores/PDF)",
                    variable=self._var_scroll_smooth,
                    bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                    activebackground=T["bg"], font=("Segoe UI", 9)
                ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))

        elif action == "type":
            lbl("Texto:", 0)
            self._text_widget = tk.Text(f, height=4, width=36,
                                        bg=T["card"], fg=T["text"],
                                        insertbackground=T["text"],
                                        font=("Consolas", 10), relief="flat",
                                        padx=6, pady=4, wrap="word")
            self._text_widget.grid(row=0, column=1, columnspan=3, pady=2)
            if self._var_text.get():
                self._text_widget.insert("1.0", self._var_text.get())
            tk.Label(f, text="Tokens: {ENTER}  {TAB}  {F1}…{F12}",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=1, column=1, columnspan=3, sticky="w")

        elif action == "key_press":
            lbl("Tecla:", 0)
            key_cb = ttk.Combobox(f, textvariable=self._var_key,
                                   values=COMMON_KEYS, width=16,
                                   font=("Consolas", 10))
            key_cb.grid(row=0, column=1, sticky="w")
            lbl("Repetir:", 1)
            entry(self._var_repeat, 1, w=5)

        elif action == "wait":
            lbl("Aguardar (ms):", 0)
            entry(self._var_delay, 0)
            lbl("Min (ms, opcional):", 1)
            entry(self._var_wait_min, 1)
            lbl("Max (ms, opcional):", 2)
            entry(self._var_wait_max, 2)
            tk.Label(f, text="Se min E max preenchidos (>0), sorteia um valor entre eles. Senao usa o fixo acima.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=460, justify="left"
                     ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))
            return  # wait não tem delay separado

        elif action == "note":
            lbl("Texto do comentario:", 0)
            note_text = tk.Text(f, height=4, width=44, bg=T["card"], fg=T["text"],
                                insertbackground=T["text"], font=("Consolas", 10),
                                relief="flat", padx=6, pady=4, wrap="word")
            note_text.grid(row=0, column=1, columnspan=3, sticky="we", pady=2)
            if self._var_text.get():
                note_text.insert("1.0", self._var_text.get())
            self._note_text_widget = note_text
            tk.Label(f, text="Nao executa nada — so aparece como label na lista de steps. Use pra organizar macros longos.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=460, justify="left"
                     ).grid(row=1, column=1, columnspan=3, sticky="w", pady=(4, 0))
            return

        elif action == "pixel_check":
            lbl("X:", 0)
            entry(self._var_x, 0)
            lbl("Y:", 1)
            entry(self._var_y, 1)
            cap_btn = self._btn(f, "🎨 Capturar Cor (3s)", self._capture_color,
                                T["accent2"], padx=6, pady=3)
            cap_btn.grid(row=0, column=2, padx=8)
            pick_btn = self._btn(f, "🎯 Picker Visual", self._open_color_picker,
                                 T["accent2"], padx=6, pady=3)
            pick_btn.grid(row=1, column=2, padx=8)

            # Preview da cor
            self._color_preview = tk.Label(f, text="  ", bg=self._rgb_hex(),
                                           relief="solid", bd=1, width=4)
            self._color_preview.grid(row=0, column=3, rowspan=2, padx=4)

            lbl("R:", 2); entry(self._var_color_r, 2, w=5)
            lbl("G:", 3); entry(self._var_color_g, 3, w=5)
            lbl("B:", 4); entry(self._var_color_b, 4, w=5)
            for v in (self._var_color_r, self._var_color_g, self._var_color_b):
                v.trace_add("write", lambda *_: self._update_color_preview())

            lbl("Tolerância:", 5)
            tk.Spinbox(f, textvariable=self._var_tolerance, from_=0, to=255,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=5, column=1, sticky="w")

            lbl("Condição:", 6)
            ttk.Combobox(f, textvariable=self._var_condition,
                         values=["match", "no_match"], state="readonly",
                         width=10, font=("Segoe UI", 10)
                         ).grid(row=6, column=1, sticky="w")
            tk.Label(f, text="match=pular se bater  /  no_match=pular se não bater",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=7, column=1, columnspan=3, sticky="w")

            lbl("Pular N steps:", 8)
            tk.Spinbox(f, textvariable=self._var_skip, from_=0, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=8, column=1, sticky="w")

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        elif action == "image_click":
            cap_btn = self._btn(f, "📷 Capturar Região", self._capture_image_region,
                                T["accent2"], padx=8, pady=4)
            cap_btn.grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

            # Preview (thumbnail ou "sem template")
            self._image_preview_label = tk.Label(f, bg=T["card"], width=8, height=4,
                                                  text="sem\ntemplate", fg=T["subtext"])
            self._image_preview_label.grid(row=0, column=2, rowspan=2, padx=8)
            self._update_image_preview()

            lbl("Confiança (%):", 2)
            tk.Spinbox(f, textvariable=self._var_threshold, from_=50, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=2, column=1, sticky="w")

            lbl("Timeout (ms):", 3)
            entry(self._var_img_timeout, 3)

            lbl("Pular N steps se não encontrar:", 4)
            tk.Spinbox(f, textvariable=self._var_img_skip, from_=0, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=4, column=1, sticky="w")

            tk.Label(f, text="Arraste para selecionar a região do botão a buscar",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        elif action == "click_text":
            lbl("Texto a procurar:", 0)
            tk.Entry(f, textvariable=self._var_text_to_find, width=32,
                     bg=T["card"], fg=T["text"], insertbackground=T["text"],
                     font=("Segoe UI", 11), relief="flat", bd=4
                     ).grid(row=0, column=1, columnspan=2, sticky="w", pady=2)

            lbl("Modo de busca:", 1)
            ttk.Combobox(f, textvariable=self._var_text_match_mode,
                         values=TEXT_MATCH_MODES, state="readonly",
                         width=10, font=("Segoe UI", 10)
                         ).grid(row=1, column=1, sticky="w")
            tk.Label(f, text="contains=contém  /  exact=igual  /  regex=padrão",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=1, column=2, sticky="w", padx=(6, 0))

            tk.Checkbutton(f, text="Diferenciar maiúsc/minúsc",
                           variable=self._var_text_case,
                           bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                           activebackground=T["bg"], font=("Segoe UI", 9)
                           ).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)

            tk.Checkbutton(f, text="Buscar só em uma região (mais rápido)",
                           variable=self._var_text_use_region,
                           bg=T["bg"], fg=T["text"], selectcolor=T["sel"],
                           activebackground=T["bg"], font=("Segoe UI", 9)
                           ).grid(row=3, column=0, columnspan=3, sticky="w", pady=2)

            cap_btn = self._btn(f, "📐 Selecionar Região (opcional)",
                                 self._capture_ocr_region,
                                 T["accent2"], padx=8, pady=4)
            cap_btn.grid(row=4, column=0, columnspan=3, sticky="w", pady=4)

            lbl("Região (x,y,w,h):", 5)
            reg_frame = tk.Frame(f, bg=T["bg"])
            reg_frame.grid(row=5, column=1, columnspan=2, sticky="w")
            for v, w in ((self._var_x, 5), (self._var_y, 5),
                         (self._var_ocr_w, 5), (self._var_ocr_h, 5)):
                tk.Entry(reg_frame, textvariable=v, width=w, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"],
                         font=("Consolas", 10), justify="center",
                         relief="flat", bd=4).pack(side="left", padx=(0, 4))

            lbl("Idioma OCR:", 6)
            ttk.Combobox(f, textvariable=self._var_ocr_lang, values=OCR_LANGS,
                         state="readonly", width=8, font=("Segoe UI", 10)
                         ).grid(row=6, column=1, sticky="w")

            lbl("Pular N steps se não achar:", 7)
            tk.Spinbox(f, textvariable=self._var_text_skip, from_=0, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=7, column=1, sticky="w")

            tk.Label(f, text="OCR de tela inteira leva ~500ms–2s. Use região "
                             "se possível pra rodar em ~100–300ms.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=440, justify="left"
                     ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "ocr_read":
            cap_btn = self._btn(f, "📐 Selecionar Região", self._capture_ocr_region,
                                T["accent2"], padx=8, pady=4)
            cap_btn.grid(row=0, column=0, columnspan=3, sticky="w", pady=4)

            lbl("X / Y:", 1)
            xy_frame = tk.Frame(f, bg=T["bg"])
            xy_frame.grid(row=1, column=1, columnspan=2, sticky="w")
            tk.Entry(xy_frame, textvariable=self._var_x, width=6, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4).pack(side="left", padx=(0,4))
            tk.Entry(xy_frame, textvariable=self._var_y, width=6, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4).pack(side="left")

            lbl("Largura × Altura:", 2)
            wh_frame = tk.Frame(f, bg=T["bg"])
            wh_frame.grid(row=2, column=1, columnspan=2, sticky="w")
            tk.Entry(wh_frame, textvariable=self._var_ocr_w, width=6, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4).pack(side="left", padx=(0,4))
            tk.Entry(wh_frame, textvariable=self._var_ocr_h, width=6, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4).pack(side="left")

            lbl("Variável de saída:", 3)
            tk.Entry(f, textvariable=self._var_ocr_var, width=18, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=3, column=1, columnspan=2, sticky="w")

            lbl("Idioma:", 4)
            ttk.Combobox(f, textvariable=self._var_ocr_lang, values=OCR_LANGS,
                         width=10, font=("Segoe UI", 10)
                         ).grid(row=4, column=1, sticky="w")

            lbl("Whitelist (opc):", 5)
            tk.Entry(f, textvariable=self._var_ocr_whitelist, width=18, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=5, column=1, columnspan=2, sticky="w")
            tk.Label(f, text='Ex: "0123456789" só lê números',
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=6, column=1, columnspan=3, sticky="w")

            tk.Checkbutton(f, text="Converter resultado para número",
                           variable=self._var_ocr_to_number,
                           bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                           activebackground=T["bg"], font=("Segoe UI", 10)
                           ).grid(row=7, column=1, columnspan=3, sticky="w", pady=(4,2))

            test_btn = self._btn(f, "🔬 Testar OCR agora", self._test_ocr,
                                 T["card"], fg=T["text"], padx=6, pady=3)
            test_btn.grid(row=8, column=1, sticky="w", pady=4)
            self._lbl_ocr_test = tk.Label(f, text="", bg=T["bg"], fg=T["accent2"],
                                          font=("Consolas", 9), anchor="w",
                                          wraplength=320, justify="left")
            self._lbl_ocr_test.grid(row=9, column=0, columnspan=3, sticky="w", pady=(2,4))

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action in ("else", "endif"):
            tk.Label(f, text=("Marca o início do bloco else." if action == "else"
                              else "Encerra o bloco if/else."),
                     bg=T["bg"], fg=T["text"], font=("Segoe UI", 10),
                     wraplength=380, justify="left", anchor="w"
                     ).grid(row=0, column=0, columnspan=3, sticky="w", pady=6)
            tk.Label(f, text="(Sem parâmetros — apenas selecione e salve.)",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=1, column=0, columnspan=3, sticky="w")
            return

        if action == "if":
            lbl("Tipo de condição:", 0)
            ttk.Combobox(f, textvariable=self._var_cond_type, values=COND_TYPES,
                         state="readonly", width=10, font=("Segoe UI", 10)
                         ).grid(row=0, column=1, sticky="w")
            self._var_cond_type.trace_add("write", lambda *_: self._refresh_fields())

            ct = self._var_cond_type.get() or "var"

            if ct == "var":
                lbl("Variável:", 1)
                tk.Entry(f, textvariable=self._var_var_name, width=18, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=1, column=1, columnspan=2, sticky="w")
                lbl("Operador:", 2)
                # Garante que op atual é válido pra esse tipo, senão reset
                if self._var_cond_op.get() not in COND_OPS_VAR:
                    self._var_cond_op.set("==")
                ttk.Combobox(f, textvariable=self._var_cond_op, values=COND_OPS_VAR,
                             state="readonly", width=12, font=("Segoe UI", 10)
                             ).grid(row=2, column=1, sticky="w")
                lbl("Valor:", 3)
                tk.Entry(f, textvariable=self._var_cond_value, width=22, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=3, column=1, columnspan=2, sticky="w")
                tk.Label(f, text='Use "{nome}" para comparar com outra variável.',
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=4, column=1, columnspan=3, sticky="w")

            elif ct == "image":
                cap_btn = self._btn(f, "📷 Capturar Região", self._capture_image_region,
                                    T["accent2"], padx=8, pady=4)
                cap_btn.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
                self._image_preview_label = tk.Label(f, bg=T["card"], width=8, height=4,
                                                      text="sem\ntemplate", fg=T["subtext"])
                self._image_preview_label.grid(row=1, column=2, rowspan=2, padx=8)
                self._update_image_preview()

                lbl("Operador:", 2)
                if self._var_cond_op.get() not in COND_OPS_IMAGE:
                    self._var_cond_op.set("present")
                ttk.Combobox(f, textvariable=self._var_cond_op, values=COND_OPS_IMAGE,
                             state="readonly", width=12, font=("Segoe UI", 10)
                             ).grid(row=2, column=1, sticky="w")

                lbl("Confiança (%):", 3)
                tk.Spinbox(f, textvariable=self._var_threshold, from_=50, to=100,
                           width=5, bg=T["card"], fg=T["text"], relief="flat",
                           font=("Consolas", 10)).grid(row=3, column=1, sticky="w")

                lbl("Timeout (ms):", 4)
                entry(self._var_img_timeout, 4)
                tk.Label(f, text="0 = tentar 1 vez; >0 = retry até encontrar/timeout",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=5, column=1, columnspan=3, sticky="w")

            elif ct == "pixel":
                lbl("X:", 1); entry(self._var_x, 1)
                lbl("Y:", 2); entry(self._var_y, 2)
                cap_btn = self._btn(f, "🎨 Capturar Cor (3s)", self._capture_color,
                                    T["accent2"], padx=6, pady=3)
                cap_btn.grid(row=1, column=2, padx=8)
                pick_btn = self._btn(f, "🎯 Picker Visual", self._open_color_picker,
                                     T["accent2"], padx=6, pady=3)
                pick_btn.grid(row=2, column=2, padx=8)
                self._color_preview = tk.Label(f, text="  ", bg=self._rgb_hex(),
                                               relief="solid", bd=1, width=4)
                self._color_preview.grid(row=1, column=3, rowspan=2, padx=4)

                lbl("R:", 3); entry(self._var_color_r, 3, w=5)
                lbl("G:", 4); entry(self._var_color_g, 4, w=5)
                lbl("B:", 5); entry(self._var_color_b, 5, w=5)
                for v in (self._var_color_r, self._var_color_g, self._var_color_b):
                    v.trace_add("write", lambda *_: self._update_color_preview())

                lbl("Tolerância:", 6)
                tk.Spinbox(f, textvariable=self._var_tolerance, from_=0, to=255,
                           width=5, bg=T["card"], fg=T["text"], relief="flat",
                           font=("Consolas", 10)).grid(row=6, column=1, sticky="w")

                lbl("Operador:", 7)
                if self._var_cond_op.get() not in COND_OPS_PIXEL:
                    self._var_cond_op.set("match")
                ttk.Combobox(f, textvariable=self._var_cond_op, values=COND_OPS_PIXEL,
                             state="readonly", width=12, font=("Segoe UI", 10)
                             ).grid(row=7, column=1, sticky="w")

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "clipboard_set":
            lbl("Texto a copiar:", 0)
            tk.Entry(f, textvariable=self._var_var_value, width=32, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=0, column=1, columnspan=2, sticky="w")
            tk.Label(f, text='Use "{nome}" pra interpolar variável  •  ex: {ocr_var} ou "olá mundo"',
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=1, column=1, columnspan=3, sticky="w")
            tk.Label(f, text="Dica: combine com 'Tecla ctrl+v' depois pra colar na janela ativa.",
                     bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8, "italic")
                     ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "clipboard_get":
            lbl("Salvar em:", 0)
            tk.Entry(f, textvariable=self._var_var_name, width=20, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=0, column=1, columnspan=2, sticky="w")
            tk.Label(f, text='Nome da variável que vai receber o conteúdo do clipboard.',
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=1, column=1, columnspan=3, sticky="w")
            tk.Label(f, text="Depois use {nome} em outro step (set_var concat, type, etc).",
                     bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8, "italic")
                     ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "wait_window":
            lbl("Título (parcial):", 0)
            tk.Entry(f, textvariable=self._var_window_title, width=32, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=0, column=1, columnspan=2, sticky="w")
            self._btn(f, "🪟 Escolher janela aberta", self._pick_window_title,
                       T["accent2"], padx=6, pady=3
                       ).grid(row=1, column=1, sticky="w", pady=4)
            tk.Label(f, text="Busca substring no título (case-insensitive). Ex: 'notepad' bate em 'Sem título — Bloco de Notas'.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=420, justify="left"
                     ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))
            lbl("Timeout (ms):", 3)
            entry(self._var_window_timeout_ms, 3)
            tk.Label(f, text="Macro continua quando janela aparecer ou timeout estourar.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=4, column=0, columnspan=4, sticky="w")
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "http_request":
            # ── MODO SIMPLES ──
            lbl("URL:", 0)
            tk.Entry(f, textvariable=self._var_http_url, width=44,
                     bg=T["card"], fg=T["text"], insertbackground=T["text"],
                     font=("Consolas", 10), relief="flat", bd=4
                     ).grid(row=0, column=1, columnspan=3, sticky="we", pady=2)

            lbl("Método:", 1)
            ttk.Combobox(f, textvariable=self._var_http_method,
                         values=["GET", "POST", "PUT", "DELETE", "PATCH"],
                         state="readonly", width=10, font=("Segoe UI", 10)
                         ).grid(row=1, column=1, sticky="w")

            lbl("Body:", 2)
            body_text = tk.Text(f, height=4, width=44, bg=T["card"], fg=T["text"],
                                insertbackground=T["text"], font=("Consolas", 10),
                                relief="flat", padx=6, pady=4, wrap="word")
            body_text.grid(row=2, column=1, columnspan=3, sticky="we", pady=2)
            if self._var_http_body.get():
                body_text.insert("1.0", self._var_http_body.get())
            self._http_body_widget = body_text
            tk.Label(f, text='JSON ou texto. Aceita {variavel}. Ex: {"content": "{nome}"}',
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=3, column=1, columnspan=3, sticky="w")

            # ── TOGGLE AVANÇADO ──
            tk.Checkbutton(f, text="🔧 Mostrar opções avançadas (headers, auth, timeout, salvar resposta)",
                           variable=self._var_http_show_advanced,
                           command=self._refresh_fields,
                           bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                           activebackground=T["bg"], font=("Segoe UI", 9)
                           ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 4))

            if self._var_http_show_advanced.get():
                lbl("Headers (Key: Value por linha):", 5)
                hdr_text = tk.Text(f, height=3, width=44, bg=T["card"], fg=T["text"],
                                   insertbackground=T["text"], font=("Consolas", 9),
                                   relief="flat", padx=6, pady=4, wrap="none")
                hdr_text.grid(row=5, column=1, columnspan=3, sticky="we", pady=2)
                if self._var_http_headers.get():
                    hdr_text.insert("1.0", self._var_http_headers.get())
                self._http_headers_widget = hdr_text
                tk.Label(f, text="Content-Type: application/json é automático se body não vazio.",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=6, column=1, columnspan=3, sticky="w")

                lbl("Autenticação:", 7)
                ttk.Combobox(f, textvariable=self._var_http_auth_kind,
                             values=["none", "bearer", "basic"], state="readonly",
                             width=10, font=("Segoe UI", 10)
                             ).grid(row=7, column=1, sticky="w")
                self._var_http_auth_kind.trace_add("write", lambda *_: self._refresh_fields())

                ak = self._var_http_auth_kind.get() or "none"
                if ak == "bearer":
                    lbl("Token:", 8)
                    tk.Entry(f, textvariable=self._var_http_auth_value, width=36, bg=T["card"],
                             fg=T["text"], insertbackground=T["text"], font=("Consolas", 10),
                             relief="flat", bd=4, show="•"
                             ).grid(row=8, column=1, columnspan=2, sticky="w")
                elif ak == "basic":
                    lbl("user:pass:", 8)
                    tk.Entry(f, textvariable=self._var_http_auth_value, width=36, bg=T["card"],
                             fg=T["text"], insertbackground=T["text"], font=("Consolas", 10),
                             relief="flat", bd=4, show="•"
                             ).grid(row=8, column=1, columnspan=2, sticky="w")
                if ak in ("bearer", "basic"):
                    tk.Label(f, text="⚠ Salvo em texto plano no slot/arquivo. Não é password manager.",
                             bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                             ).grid(row=9, column=1, columnspan=3, sticky="w")

                lbl("Timeout (s):", 10)
                tk.Spinbox(f, textvariable=self._var_http_timeout, from_=1, to=120,
                           width=5, bg=T["card"], fg=T["text"], relief="flat",
                           font=("Consolas", 10)).grid(row=10, column=1, sticky="w")

                lbl("Salvar body em var:", 11)
                tk.Entry(f, textvariable=self._var_var_name, width=20, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=11, column=1, sticky="w")

                lbl("Salvar status HTTP em var:", 12)
                tk.Entry(f, textvariable=self._var_http_save_status, width=20, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=12, column=1, sticky="w")
                tk.Label(f, text="Status -1 = erro de rede/timeout. Use If pra checar.",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=13, column=1, columnspan=3, sticky="w")

            lbl("Delay pré-step (ms):", 14)
            entry(self._var_delay, 14)
            return

        if action in ("mouse_down", "mouse_up"):
            tk.Label(f, text=ACTION_DESCRIPTIONS[action], bg=T["bg"], fg=T["accent2"],
                     font=("Segoe UI", 9), wraplength=440, justify="left"
                     ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(2, 6))
            if action == "mouse_down":
                lbl("X (opc):", 1); entry(self._var_x, 1)
                lbl("Y (opc):", 2); entry(self._var_y, 2)
                self._btn(f, "📍 Capturar (3s)", self._capture_xy,
                           T["accent2"], padx=6, pady=3
                           ).grid(row=1, column=2, rowspan=2, padx=8)
                tk.Label(f, text="Vazio = pressiona na posicao atual do cursor.",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=3, column=0, columnspan=3, sticky="w")
            lbl("Botao:", 4)
            ttk.Combobox(f, textvariable=self._var_button,
                         values=["left", "right", "middle"], state="readonly",
                         width=10, font=("Segoe UI", 10)
                         ).grid(row=4, column=1, sticky="w")
            lbl("Delay pre-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action == "ai_prompt":
            lbl("Backend:", 0)
            ttk.Combobox(f, textvariable=self._var_ai_backend,
                         values=["ollama", "openai", "openrouter", "groq", "custom"],
                         state="readonly", width=14, font=("Segoe UI", 10)
                         ).grid(row=0, column=1, sticky="w")
            self._var_ai_backend.trace_add("write", lambda *_: self._refresh_fields())

            backend = self._var_ai_backend.get() or "ollama"

            lbl("Modelo:", 1)
            _model_suggestions = {
                "ollama":     ["llama3.2", "llama3.2-vision", "llama3.1",
                               "mistral", "gemma2", "phi3", "qwen2.5"],
                "openai":     ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                "openrouter": ["mistralai/mistral-7b-instruct", "google/gemma-7b-it",
                               "meta-llama/llama-3-8b-instruct"],
                "groq":       ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768"],
                "custom":     [],
            }
            if not self._var_ai_model.get():
                _defaults = {"ollama": "llama3.2", "openai": "gpt-4o-mini",
                             "openrouter": "mistralai/mistral-7b-instruct",
                             "groq": "llama3-8b-8192", "custom": ""}
                self._var_ai_model.set(_defaults.get(backend, ""))
            model_combo = ttk.Combobox(f, textvariable=self._var_ai_model,
                         values=_model_suggestions.get(backend, []),
                         width=26, font=("Consolas", 10))
            model_combo.grid(row=1, column=1, sticky="w")

            # Botão 🔍 detecta modelos Ollama instalados
            def _detect_ollama_models():
                if (self._var_ai_backend.get() or "ollama") != "ollama":
                    return
                from core.ai_client import list_ollama_models
                models = list_ollama_models(self._var_ai_base_url.get())
                if models:
                    model_combo["values"] = models
                    if self._var_ai_model.get() not in models:
                        self._var_ai_model.set(models[0])
            self._btn(f, "🔍", _detect_ollama_models, T["card"], fg=T["text"],
                       padx=4, pady=2).grid(row=1, column=2, sticky="w", padx=(4, 0))

            lbl("Prompt:", 2)
            prompt_text = tk.Text(f, height=5, width=44, bg=T["card"], fg=T["text"],
                                  insertbackground=T["text"], font=("Consolas", 10),
                                  relief="flat", padx=6, pady=4, wrap="word")
            prompt_text.grid(row=2, column=1, columnspan=3, sticky="we", pady=2)
            if self._var_ai_prompt_text.get():
                prompt_text.insert("1.0", self._var_ai_prompt_text.get())
            self._ai_prompt_widget = prompt_text
            tk.Label(f, text='Aceita {variavel}. Ex: "Traduza pro ingles: {texto}"',
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=3, column=1, columnspan=3, sticky="w")

            lbl("Salvar resposta em var:", 4)
            tk.Entry(f, textvariable=self._var_var_name, width=20, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=4, column=1, sticky="w")

            # ── VISION (multimodal): captura região da tela e envia como imagem ──
            tk.Checkbutton(f, text="👁 Incluir screenshot de uma regiao da tela (vision)",
                           variable=self._var_ai_vision_enabled,
                           command=self._refresh_fields,
                           bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                           activebackground=T["bg"], font=("Segoe UI", 9)
                           ).grid(row=4, column=2, columnspan=2, sticky="w", padx=(20, 0))

            if self._var_ai_vision_enabled.get():
                # Reusa _capture_ocr_region (já existe) — preenche x/y/ocr_w/ocr_h
                self._btn(f, "📐 Selecionar Regiao", self._capture_ocr_region,
                           T["accent2"], padx=8, pady=3
                           ).grid(row=4, column=4, sticky="w", padx=(8, 0))
                _region_label = "Regiao: "
                if (self._var_x.get() and self._var_y.get()
                        and self._var_ocr_w.get() and self._var_ocr_h.get()):
                    _region_label += (f"({self._var_x.get()},{self._var_y.get()}) "
                                       f"{self._var_ocr_w.get()}x{self._var_ocr_h.get()}")
                else:
                    _region_label += "(nao definida)"
                tk.Label(f, text=_region_label,
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=4, column=5, sticky="w", padx=(6, 0))
                tk.Label(f, text="Use modelo com suporte a vision: "
                                  "llama3.2-vision (Ollama) ou gpt-4o-mini (OpenAI).",
                         bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8, "italic"),
                         wraplength=460, justify="left"
                         ).grid(row=4, column=1, columnspan=5, sticky="w",
                                 padx=(0, 0), pady=(22, 0))

            tk.Checkbutton(f, text="🔧 Avancado (system prompt, temperatura, API key, URL base)",
                           variable=self._var_ai_show_advanced,
                           command=self._refresh_fields,
                           bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                           activebackground=T["bg"], font=("Segoe UI", 9)
                           ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 4))

            if self._var_ai_show_advanced.get():
                lbl("System prompt:", 6)
                sys_text = tk.Text(f, height=3, width=44, bg=T["card"], fg=T["text"],
                                   insertbackground=T["text"], font=("Consolas", 10),
                                   relief="flat", padx=6, pady=4, wrap="word")
                sys_text.grid(row=6, column=1, columnspan=3, sticky="we", pady=2)
                if self._var_ai_system_prompt.get():
                    sys_text.insert("1.0", self._var_ai_system_prompt.get())
                self._ai_system_widget = sys_text
                tk.Label(f, text='Ex: "Responda sempre em portugues em no maximo 1 frase."',
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=7, column=1, columnspan=3, sticky="w")

                lbl("Temperatura:", 8)
                tk.Spinbox(f, textvariable=self._var_ai_temperature, from_=0.0, to=2.0,
                           increment=0.1, width=5, bg=T["card"], fg=T["text"],
                           relief="flat", font=("Consolas", 10), format="%.1f"
                           ).grid(row=8, column=1, sticky="w")
                tk.Label(f, text="0=determinístico  1=criativo  (Ollama ignora este campo)",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=8, column=2, columnspan=2, sticky="w", padx=8)

                if backend != "ollama":
                    lbl("API Key:", 9)
                    tk.Entry(f, textvariable=self._var_ai_api_key, width=38,
                             bg=T["card"], fg=T["text"], insertbackground=T["text"],
                             font=("Consolas", 10), relief="flat", bd=4, show="•"
                             ).grid(row=9, column=1, columnspan=2, sticky="w")
                    tk.Label(f, text="Salva em texto plano no slot/arquivo. Nao e password manager.",
                             bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                             ).grid(row=10, column=1, columnspan=3, sticky="w")

                if backend in ("ollama", "custom"):
                    lbl("URL base:", 11)
                    tk.Entry(f, textvariable=self._var_ai_base_url, width=38,
                             bg=T["card"], fg=T["text"], insertbackground=T["text"],
                             font=("Consolas", 10), relief="flat", bd=4
                             ).grid(row=11, column=1, columnspan=2, sticky="w")
                    _placeholder = ("http://localhost:11434" if backend == "ollama"
                                    else "https://sua-api.com/v1")
                    tk.Label(f, text=f"Padrao: {_placeholder}",
                             bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                             ).grid(row=12, column=1, columnspan=3, sticky="w")

                lbl("Timeout (s):", 13)
                tk.Spinbox(f, textvariable=self._var_ai_timeout, from_=5, to=300,
                           width=5, bg=T["card"], fg=T["text"], relief="flat",
                           font=("Consolas", 10)).grid(row=13, column=1, sticky="w")

            lbl("Delay pre-step (ms):", 15)
            entry(self._var_delay, 15)
            return

        if action == "fishing_pd_track":
            # ── Região do medidor ────────────────────────────────────
            self._btn(f, "📐 Selecionar Regiao do Medidor", self._capture_ocr_region,
                       T["accent2"], padx=8, pady=4
                       ).grid(row=0, column=0, columnspan=3, sticky="w", pady=4)
            lbl("X / Y:", 1)
            xy_frame = tk.Frame(f, bg=T["bg"])
            xy_frame.grid(row=1, column=1, columnspan=2, sticky="w")
            for v, w in ((self._var_x, 6), (self._var_y, 6)):
                tk.Entry(xy_frame, textvariable=v, width=w, bg=T["card"], fg=T["text"],
                         insertbackground=T["text"], font=("Consolas", 11),
                         justify="center", relief="flat", bd=4).pack(side="left", padx=(0, 4))
            lbl("Largura x Altura:", 2)
            wh_frame = tk.Frame(f, bg=T["bg"])
            wh_frame.grid(row=2, column=1, columnspan=2, sticky="w")
            for v, w in ((self._var_ocr_w, 6), (self._var_ocr_h, 6)):
                tk.Entry(wh_frame, textvariable=v, width=w, bg=T["card"], fg=T["text"],
                         insertbackground=T["text"], font=("Consolas", 11),
                         justify="center", relief="flat", bd=4).pack(side="left", padx=(0, 4))

            # ── 3 cores: guia, player, target ────────────────────────
            def _color_row(label_text, vr, vg, vb, row):
                lbl(label_text, row)
                cf = tk.Frame(f, bg=T["bg"])
                cf.grid(row=row, column=1, columnspan=2, sticky="w")
                for v in (vr, vg, vb):
                    tk.Entry(cf, textvariable=v, width=5, bg=T["card"], fg=T["text"],
                             insertbackground=T["text"], font=("Consolas", 11),
                             justify="center", relief="flat", bd=4
                             ).pack(side="left", padx=(0, 4))
                # Preview da cor (label colorido)
                try:
                    rr = max(0, min(255, int(vr.get() or 0)))
                    gg = max(0, min(255, int(vg.get() or 0)))
                    bb = max(0, min(255, int(vb.get() or 0)))
                    hex_color = f"#{rr:02x}{gg:02x}{bb:02x}"
                except ValueError:
                    hex_color = "#000000"
                tk.Label(cf, text="    ", bg=hex_color, width=4, relief="solid", bd=1
                         ).pack(side="left", padx=(6, 0))

            _color_row("Cor GUIA  (R G B):",   self._var_color_r,  self._var_color_g,  self._var_color_b,  3)
            _color_row("Cor PEIXE (R G B):",   self._var_fish_player_r, self._var_fish_player_g, self._var_fish_player_b, 4)
            _color_row("Cor ALVO  (R G B):",   self._var_fish_target_r, self._var_fish_target_g, self._var_fish_target_b, 5)

            self._btn(f, "📷 Capturar Guia",   self._capture_color, T["accent2"], padx=6, pady=2
                       ).grid(row=3, column=3, sticky="w", padx=(8, 0))
            self._btn(f, "📷 Capturar Peixe",
                       lambda: self._capture_color_into(self._var_fish_player_r,
                                                        self._var_fish_player_g,
                                                        self._var_fish_player_b,
                                                        "cor do PEIXE"),
                       T["accent2"], padx=6, pady=2
                       ).grid(row=4, column=3, sticky="w", padx=(8, 0))
            self._btn(f, "📷 Capturar Alvo",
                       lambda: self._capture_color_into(self._var_fish_target_r,
                                                        self._var_fish_target_g,
                                                        self._var_fish_target_b,
                                                        "cor do ALVO"),
                       T["accent2"], padx=6, pady=2
                       ).grid(row=5, column=3, sticky="w", padx=(8, 0))

            lbl("Tolerancia cor:", 6); entry(self._var_tolerance, 6, w=5)

            lbl("kp (proporcional):", 7); entry(self._var_fish_kp, 7, w=6)
            lbl("kd (derivativo):", 8);   entry(self._var_fish_kd, 8, w=6)

            # ── Avancado: anti-overcorrection / anti-ruido / wall-clamp / fps ──
            lbl("PD clamp (max):", 9);     entry(self._var_fish_pd_clamp, 9, w=6)
            lbl("Min pixels:", 10);        entry(self._var_fish_min_pixels, 10, w=6)
            lbl("Wall ratio (0-0.5):", 11); entry(self._var_fish_wall_ratio, 11, w=6)
            lbl("FPS scan:", 12);          entry(self._var_fish_fps, 12, w=6)

            lbl("Botao do mouse:", 13)
            ttk.Combobox(f, textvariable=self._var_button,
                         values=["left", "right"], state="readonly",
                         width=10, font=("Segoe UI", 10)
                         ).grid(row=13, column=1, sticky="w")

            lbl("Timeout (ms):", 14); entry(self._var_img_timeout, 14)

            tk.Label(f, text="Defaults GPO: guia=RGB(85,170,255), peixe=(255,255,255), alvo=(25,25,25).",
                     bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8, "italic"),
                     wraplength=460, justify="left"
                     ).grid(row=15, column=0, columnspan=4, sticky="w", pady=(6, 0))
            tk.Label(f, text="Capture a regiao do medidor inteiro. Cor GUIA = coluna fixa (azul). "
                              "PEIXE = marcador que voce controla. ALVO = barra que se move.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=460, justify="left"
                     ).grid(row=16, column=0, columnspan=4, sticky="w", pady=(2, 0))
            tk.Label(f, text="Avancado: PD clamp=limite max do controle (1.0 OK). Min pixels=filtro de ruido (3+). "
                              "Wall ratio=0.1 forca borda nos extremos (0=off). FPS scan=30 OK; menor=menos CPU.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8),
                     wraplength=460, justify="left"
                     ).grid(row=17, column=0, columnspan=4, sticky="w", pady=(2, 0))

            lbl("Delay pre-step (ms):", 19)
            entry(self._var_delay, 19)
            return

        if action == "set_var":
            lbl("Variável:", 0)
            tk.Entry(f, textvariable=self._var_var_name, width=20, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=0, column=1, columnspan=2, sticky="w")

            lbl("Operação:", 1)
            ttk.Combobox(f, textvariable=self._var_var_op, values=VAR_OPS,
                         state="readonly", width=14, font=("Segoe UI", 10)
                         ).grid(row=1, column=1, sticky="w")
            self._var_var_op.trace_add("write", lambda *_: self._refresh_fields())

            current_op = self._var_var_op.get() or "set"
            if current_op == "from_clipboard":
                tk.Label(f, text="Lê o texto do clipboard pra variável.",
                         bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 9)
                         ).grid(row=2, column=0, columnspan=3, sticky="w", pady=4)
            elif current_op == "to_clipboard":
                lbl("Texto a copiar:", 2)
                tk.Entry(f, textvariable=self._var_var_value, width=24, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=2, column=1, columnspan=2, sticky="w")
                tk.Label(f, text='Use "{nome}" pra referenciar outra variável.',
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=3, column=1, columnspan=3, sticky="w")
            else:
                lbl("Valor:", 2)
                tk.Entry(f, textvariable=self._var_var_value, width=24, bg=T["card"],
                         fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                         relief="flat", bd=4).grid(row=2, column=1, columnspan=2, sticky="w")
                tk.Label(f, text='Use "{nome}" pra referenciar outra variável  •  ex: {hp} ou 10',
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=3, column=1, columnspan=3, sticky="w")
                tk.Label(f, text="set/concat aceitam texto  •  add/sub/mul/div só numéricos",
                         bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                         ).grid(row=4, column=1, columnspan=3, sticky="w")

            tk.Label(f, text="💾 Variaveis com nome iniciando em '$' (ex: $kills, $money) persistem "
                              "entre execucoes do macro — gravadas em profiles/persistent_vars.json.",
                     bg=T["bg"], fg=T["accent2"], font=("Segoe UI", 8, "italic"),
                     wraplength=460, justify="left"
                     ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))

            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
            return

        if action != "wait":
            lbl("Delay pré-step (ms):", 10)
            entry(self._var_delay, 10)
        if action not in ("wait", "type", "key_press"):
            lbl("Repetir:", 11)
            entry(self._var_repeat, 11, w=5)

    # ─────────────────────────────────────────────────────────────
    # HELPERS DE COR
    # ─────────────────────────────────────────────────────────────
    def _rgb_hex(self) -> str:
        try:
            r = max(0, min(255, int(self._var_color_r.get() or 0)))
            g = max(0, min(255, int(self._var_color_g.get() or 0)))
            b = max(0, min(255, int(self._var_color_b.get() or 0)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            return "#000000"

    def _update_color_preview(self) -> None:
        if self._color_preview:
            self._color_preview.config(bg=self._rgb_hex())

    def _capture_color(self) -> None:
        if not self._driver:
            return
        orig_title = self.title()
        self.title("Posicione o cursor sobre a cor... (3s)")

        def _do():
            time.sleep(3)
            x, y = self._driver.get_position()
            r, g, b = self._driver.get_pixel_color(int(x), int(y))
            self._var_x.set(str(int(x)))
            self._var_y.set(str(int(y)))
            self._var_color_r.set(str(r))
            self._var_color_g.set(str(g))
            self._var_color_b.set(str(b))
            self.after(0, lambda: self.title(orig_title))
            self.after(0, self._update_color_preview)

        threading.Thread(target=_do, daemon=True).start()

    def _capture_color_into(self, vr: tk.StringVar, vg: tk.StringVar, vb: tk.StringVar,
                            label: str = "cor") -> None:
        """Captura cor sob cursor depois de 3s e grava nas 3 vars dadas.
        Nao mexe em x/y (diferente do _capture_color que tambem grava posicao).
        Usado pelos botoes 'Capturar Peixe' e 'Capturar Alvo' no fishing_pd_track.
        """
        if not self._driver:
            return
        orig_title = self.title()
        self.title(f"Posicione o cursor sobre a {label}... (3s)")

        def _do():
            time.sleep(3)
            x, y = self._driver.get_position()
            r, g, b = self._driver.get_pixel_color(int(x), int(y))
            vr.set(str(r))
            vg.set(str(g))
            vb.set(str(b))
            self.after(0, lambda: self.title(orig_title))
            self.after(0, self._refresh_fields)  # repinta preview

        threading.Thread(target=_do, daemon=True).start()

    def _open_color_picker(self) -> None:
        """Picker visual: tooltip seguindo cursor mostra cor RGB live.

        Click confirma e preenche X/Y/RGB. Esc cancela. Diferente do
        _capture_color (espera 3s), aqui o usuário vê a cor antes de
        confirmar — sem contagem regressiva.
        """
        if not self._driver:
            return
        self.withdraw()
        self.update()
        time.sleep(0.2)

        T = self._T
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.attributes("-alpha", 0.95)
        tip.configure(bg=T["card"], bd=1, relief="solid")

        swatch = tk.Label(tip, bg="#000000", width=4, height=2, relief="solid", bd=1)
        swatch.pack(side="left", padx=4, pady=4)
        info = tk.Label(tip, text="", bg=T["card"], fg=T["text"],
                        font=("Consolas", 10), justify="left", anchor="w")
        info.pack(side="left", padx=(0, 8), pady=4)

        state = {"running": True, "x": 0, "y": 0, "r": 0, "g": 0, "b": 0}

        def tick():
            if not state["running"]:
                return
            try:
                x, y = self._driver.get_position()
                r, g, b = self._driver.get_pixel_color(int(x), int(y))
            except Exception:
                self.after(80, tick)
                return
            state.update(x=int(x), y=int(y), r=r, g=g, b=b)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            swatch.config(bg=hex_color)
            info.config(text=f"({x},{y})\nRGB({r},{g},{b})\n{hex_color}\n[Click=OK Esc=cancela]")
            tip.geometry(f"+{int(x) + 18}+{int(y) + 18}")
            self.after(80, tick)

        # pynput pra capturar click/Esc globalmente sem mexer no `keyboard`
        # global do app (F6/F7/F8 dependem dele).
        from pynput import mouse as pm, keyboard as pk

        def finalize(do_save: bool):
            if not state["running"]:
                return
            state["running"] = False
            try:
                mouse_listener.stop()
            except Exception:
                pass
            try:
                key_listener.stop()
            except Exception:
                pass
            tip.destroy()
            self.deiconify()
            self.lift()
            if do_save:
                self._var_x.set(str(state["x"]))
                self._var_y.set(str(state["y"]))
                self._var_color_r.set(str(state["r"]))
                self._var_color_g.set(str(state["g"]))
                self._var_color_b.set(str(state["b"]))
                self._update_color_preview()

        def on_click(_x, _y, button, pressed):
            if pressed and button == pm.Button.left:
                self.after(0, lambda: finalize(True))
                return False

        def on_key(key):
            if key == pk.Key.esc:
                self.after(0, lambda: finalize(False))
                return False
            if key == pk.Key.enter:
                self.after(0, lambda: finalize(True))
                return False

        mouse_listener = pm.Listener(on_click=on_click)
        key_listener = pk.Listener(on_press=on_key)
        mouse_listener.start()
        key_listener.start()
        tick()

    # ─────────────────────────────────────────────────────────────
    # IMAGE CLICK — captura de região e preview
    # ─────────────────────────────────────────────────────────────
    def _update_image_preview(self) -> None:
        """Atualiza o thumbnail do template no dialog."""
        if not self._image_preview_label:
            return
        if not self._image_data_b64:
            self._image_preview_label.config(image="", text="sem\ntemplate")
            return
        try:
            import base64, io
            from PIL import Image, ImageTk
            raw = base64.b64decode(self._image_data_b64)
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((64, 64))
            photo = ImageTk.PhotoImage(img)
            self._image_preview_label.config(image=photo, text="")
            self._image_preview_label.image = photo  # evita garbage collection
        except Exception:
            self._image_preview_label.config(image="", text="erro\npreview")

    def _select_screen_region(self, prompt: str = "Arraste para selecionar a regiao"):
        """Helper compartilhado: mostra overlay fullscreen com screenshot + HUD ao vivo.

        Retorna (left, top, width, height, screenshot_PIL) ou None se cancelado ou
        area muito pequena. Usado por _capture_image_region e _capture_ocr_region.

        Melhorias vs overlay antigo: HUD live (cursor + dimensoes), retangulo mais
        grosso com preenchimento stippled (efeito de transparencia), instrucoes
        visiveis, Esc cancela claramente.
        """
        from PIL import ImageGrab

        self.withdraw()
        self.update()
        time.sleep(0.3)

        try:
            screenshot = ImageGrab.grab()
        except Exception:
            self.deiconify()
            return None

        T = self._T
        sw, sh = screenshot.size

        overlay = tk.Toplevel(self)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.45)
        overlay.configure(bg="black")
        overlay.attributes("-topmost", True)
        overlay.config(cursor="crosshair")

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0,
                           cursor="crosshair")
        canvas.pack(fill="both", expand=True)

        # ── HUD ──────────────────────────────────────────────────────
        # Faixa superior com instrucao
        hud_top = tk.Frame(overlay, bg=T["accent"], padx=14, pady=6)
        hud_top.place(relx=0.5, y=10, anchor="n")
        tk.Label(hud_top, text=f"  {prompt}  •  Esc cancela  ",
                 bg=T["accent"], fg="white",
                 font=("Segoe UI", 11, "bold")).pack()

        # HUD inferior com coordenadas/dimensoes live
        hud_bot = tk.Frame(overlay, bg=T["bg_deep"], padx=14, pady=6)
        hud_bot.place(relx=0.5, rely=1.0, y=-12, anchor="s")
        hud_var = tk.StringVar(value="Cursor: (—, —)")
        tk.Label(hud_bot, textvariable=hud_var, bg=T["bg_deep"],
                 fg=T["accent2"], font=("Consolas", 12, "bold")).pack()

        sel = {"x0": 0, "y0": 0, "x1": 0, "y1": 0,
               "rect": None, "fill": None, "active": False}

        def update_hud(cur_x: int, cur_y: int):
            if sel["active"]:
                left = min(sel["x0"], cur_x)
                top  = min(sel["y0"], cur_y)
                w    = abs(cur_x - sel["x0"])
                h    = abs(cur_y - sel["y0"])
                hud_var.set(f"Origem: ({left}, {top})   Tamanho: {w} × {h} px")
            else:
                hud_var.set(f"Cursor: ({cur_x}, {cur_y})  —  clique e arraste pra selecionar")

        def on_motion(e):
            update_hud(e.x_root, e.y_root)

        def on_press(e):
            sel["x0"], sel["y0"] = e.x_root, e.y_root
            sel["active"] = True
            for k in ("rect", "fill"):
                if sel[k]:
                    canvas.delete(sel[k])
                    sel[k] = None
            # Preenchimento stipled (poor-man's transparencia em tk)
            sel["fill"] = canvas.create_rectangle(
                e.x, e.y, e.x, e.y,
                fill=T["accent"], stipple="gray25", outline="",
            )
            sel["rect"] = canvas.create_rectangle(
                e.x, e.y, e.x, e.y,
                outline=T["accent2"], width=3,
            )
            update_hud(e.x_root, e.y_root)

        def on_drag(e):
            if sel["rect"] is None:
                return
            x0_local = sel["x0"] - overlay.winfo_rootx()
            y0_local = sel["y0"] - overlay.winfo_rooty()
            canvas.coords(sel["rect"], x0_local, y0_local, e.x, e.y)
            canvas.coords(sel["fill"], x0_local, y0_local, e.x, e.y)
            update_hud(e.x_root, e.y_root)

        def on_release(e):
            sel["x1"], sel["y1"] = e.x_root, e.y_root
            overlay.destroy()

        def on_cancel(e):
            sel["x0"] = sel["x1"]  # garante area zero → aborta
            sel["y0"] = sel["y1"]
            overlay.destroy()

        canvas.bind("<Motion>", on_motion)
        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_cancel)
        overlay.wait_window()

        self.deiconify()
        self.lift()

        x0, y0, x1, y1 = sel["x0"], sel["y0"], sel["x1"], sel["y1"]
        left, top = min(x0, x1), min(y0, y1)
        right, bottom = max(x0, x1), max(y0, y1)
        if right - left < 5 or bottom - top < 5:
            return None

        left  = max(0, min(left, sw))
        top   = max(0, min(top, sh))
        right = max(0, min(right, sw))
        bottom = max(0, min(bottom, sh))
        return (int(left), int(top), int(right - left), int(bottom - top), screenshot)

    def _capture_image_region(self) -> None:
        """Captura região arrastada e salva como PNG (image_click step)."""
        result = self._select_screen_region("Selecione a IMAGEM (template) que sera procurada na tela")
        if result is None:
            return
        left, top, w, h, screenshot = result
        cropped = screenshot.crop((left, top, left + w, top + h))
        import base64, io
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        self._image_data_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self._update_image_preview()

    # ─────────────────────────────────────────────────────────────
    # OCR — captura de região e teste
    # ─────────────────────────────────────────────────────────────
    def _capture_ocr_region(self) -> None:
        """Captura região arrastada e preenche x/y/ocr_w/ocr_h (OCR/fishing/etc)."""
        result = self._select_screen_region("Selecione a REGIAO da tela")
        if result is None:
            return
        left, top, w, h, _screenshot = result
        self._var_x.set(str(left))
        self._var_y.set(str(top))
        self._var_ocr_w.set(str(w))
        self._var_ocr_h.set(str(h))

    def _test_ocr(self) -> None:
        """Executa OCR na região atual e mostra o resultado na UI."""
        if not self._driver:
            return
        if not self._lbl_ocr_test:
            return

        def _int(var, d=0):
            try: return int(var.get() or d)
            except ValueError: return d

        x, y = _int(self._var_x), _int(self._var_y)
        w, h = _int(self._var_ocr_w), _int(self._var_ocr_h)
        if w <= 0 or h <= 0:
            self._lbl_ocr_test.config(text="⚠ Selecione uma região primeiro", fg="#ff9966")
            return

        if not self._driver.has_tesseract():
            self._lbl_ocr_test.config(
                text="⚠ Tesseract OCR não instalado.\nBaixe: github.com/UB-Mannheim/tesseract/wiki",
                fg="#ff5b5b")
            return

        self._lbl_ocr_test.config(text="🔄 Executando OCR…", fg=self._T["subtext"])
        self.update_idletasks()

        def _do():
            img = self._driver.capture_region(x, y, w, h)
            text = self._driver.run_ocr(img, self._var_ocr_lang.get() or "eng",
                                         self._var_ocr_whitelist.get())
            display = text if text else "(vazio)"
            if len(display) > 200:
                display = display[:200] + "…"
            self.after(0, lambda: self._lbl_ocr_test.config(
                text=f"📖 Resultado: {display}", fg=self._T["accent2"]))

        threading.Thread(target=_do, daemon=True).start()

    # ─────────────────────────────────────────────────────────────
    # CAPTURAR POSIÇÃO
    # ─────────────────────────────────────────────────────────────
    def _capture_xy(self) -> None:
        if not self._driver:
            return
        orig_title = self.title()
        self.title("Mova o cursor... (3s)")

        def _do():
            time.sleep(3)
            x, y = self._driver.get_position()
            self._var_x.set(str(x))
            self._var_y.set(str(y))
            self.after(0, lambda: self.title(orig_title))

        threading.Thread(target=_do, daemon=True).start()

    def _capture_xy2(self) -> None:
        """Captura ponto final do drag em 3s."""
        if not self._driver:
            return
        orig_title = self.title()
        self.title("Mova o cursor para o destino... (3s)")

        def _do():
            time.sleep(3)
            x, y = self._driver.get_position()
            self._var_x2.set(str(x))
            self._var_y2.set(str(y))
            self.after(0, lambda: self.title(orig_title))

        threading.Thread(target=_do, daemon=True).start()

    def _pick_macro_file(self) -> None:
        """Abre filedialog para escolher um .json de macro (call_macro)."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self,
            title="Escolher arquivo de macro",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            self._var_call_target.set(path)

    def _pick_window_title(self) -> None:
        """Abre modal listando janelas abertas; preenche título escolhido."""
        from ui.window_picker import pick_window
        result = pick_window(
            self, self._T,
            title_text="Escolher janela",
            prompt="Selecione a janela cujo título o macro vai aguardar:",
        )
        if result:
            _hwnd, title = result
            self._var_window_title.set(title)

    # ─────────────────────────────────────────────────────────────
    # OK
    # ─────────────────────────────────────────────────────────────
    def _ok(self) -> None:
        action = self._var_action.get()

        def _int(var: tk.StringVar, default: int = 0) -> int:
            try:
                return int(var.get() or default)
            except ValueError:
                return default

        x = _int(self._var_x) if self._var_x.get().strip() else None
        y = _int(self._var_y) if self._var_y.get().strip() else None
        delay = max(0, _int(self._var_delay))
        repeat = max(1, _int(self._var_repeat, 1))

        text = None
        if action == "type":
            text = self._text_widget.get("1.0", "end-1c") if self._text_widget else ""
        elif action == "note":
            text = self._note_text_widget.get("1.0", "end-1c") if self._note_text_widget else self._var_text.get()

        # wait — opcional delay aleatorio (min/max)
        delay_ms_min = max(0, _int(self._var_wait_min)) if action == "wait" else 0
        delay_ms_max = max(0, _int(self._var_wait_max)) if action == "wait" else 0

        color_rgb = None
        skip_steps = 0
        color_condition = "match"
        color_tolerance = 10
        if action == "pixel_check":
            r = max(0, min(255, _int(self._var_color_r)))
            g = max(0, min(255, _int(self._var_color_g)))
            b = max(0, min(255, _int(self._var_color_b)))
            color_rgb = [r, g, b]
            skip_steps = max(0, _int(self._var_skip, 1))
            color_condition = self._var_condition.get()
            color_tolerance = max(0, min(255, _int(self._var_tolerance, 10)))

        image_data = None
        image_threshold = 0.9
        image_timeout_ms = 5000
        image_skip_steps = 0
        if action == "image_click":
            image_data = self._image_data_b64
            image_threshold = max(0.5, min(1.0, _int(self._var_threshold, 90) / 100))
            image_timeout_ms = max(100, _int(self._var_img_timeout, 5000))
            image_skip_steps = max(0, _int(self._var_img_skip, 0))

        # OCR fields — compartilhados entre ocr_read e click_text
        actions_using_ocr_region = ("ocr_read", "click_text")
        ocr_w = max(0, _int(self._var_ocr_w)) if action in actions_using_ocr_region else 0
        ocr_h = max(0, _int(self._var_ocr_h)) if action in actions_using_ocr_region else 0
        ocr_var = self._var_ocr_var.get().strip() if action == "ocr_read" else ""
        ocr_lang = (self._var_ocr_lang.get() or "eng") if action in actions_using_ocr_region else "eng"
        ocr_whitelist = self._var_ocr_whitelist.get() if action == "ocr_read" else ""
        ocr_to_number = bool(self._var_ocr_to_number.get()) if action == "ocr_read" else False

        # click_text fields
        text_to_find = ""
        text_match_mode = "contains"
        text_case_sensitive = False
        text_use_region = False
        text_skip_steps = 0
        if action == "click_text":
            text_to_find = self._var_text_to_find.get()
            text_match_mode = self._var_text_match_mode.get() or "contains"
            text_case_sensitive = bool(self._var_text_case.get())
            text_use_region = bool(self._var_text_use_region.get())
            text_skip_steps = max(0, _int(self._var_text_skip, 0))

        # Variable fields (compartilhado: set_var usa, if-var também, clipboard_*)
        var_name = ""
        var_value = ""
        var_op = "set"
        if action == "set_var":
            var_name  = self._var_var_name.get().strip()
            var_value = self._var_var_value.get()
            var_op    = self._var_var_op.get()
        elif action == "clipboard_set":
            var_value = self._var_var_value.get()
        elif action == "clipboard_get":
            var_name = self._var_var_name.get().strip()
        elif action == "if" and self._var_cond_type.get() == "var":
            var_name = self._var_var_name.get().strip()

        # wait_window — título (parcial) + timeout
        window_title = ""
        window_timeout_ms = 5000
        if action == "wait_window":
            window_title = self._var_window_title.get().strip()
            window_timeout_ms = max(100, _int(self._var_window_timeout_ms, 5000))

        # If/condition fields
        cond_type  = "var"
        cond_op    = "=="
        cond_value = ""
        if action == "if":
            cond_type  = self._var_cond_type.get() or "var"
            cond_op    = self._var_cond_op.get() or "=="
            cond_value = self._var_cond_value.get()
            # If de tipo image também usa image_data/threshold/timeout
            if cond_type == "image":
                image_data       = self._image_data_b64
                image_threshold  = max(0.5, min(1.0, _int(self._var_threshold, 90) / 100))
                image_timeout_ms = max(0, _int(self._var_img_timeout, 0))
            # If de tipo pixel usa color_rgb/tolerance
            if cond_type == "pixel":
                r = max(0, min(255, _int(self._var_color_r)))
                g = max(0, min(255, _int(self._var_color_g)))
                b = max(0, min(255, _int(self._var_color_b)))
                color_rgb       = [r, g, b]
                color_tolerance = max(0, min(255, _int(self._var_tolerance, 10)))

        # Drag — coords destino + duração
        x2 = _int(self._var_x2) if action == "drag" and self._var_x2.get().strip() else None
        y2 = _int(self._var_y2) if action == "drag" and self._var_y2.get().strip() else None
        drag_duration_ms = max(50, _int(self._var_drag_duration, 300)) if action == "drag" else 300

        # wait_image — usa image_data + threshold + timeout do bloco image; nova flag wait_for
        image_wait_for = "present"
        if action == "wait_image":
            image_data = self._image_data_b64
            image_threshold = max(0.5, min(1.0, _int(self._var_threshold, 90) / 100))
            image_timeout_ms = max(100, _int(self._var_img_timeout, 5000))
            image_wait_for = self._var_img_wait_for.get() or "present"

        # wait_pixel — reusa color_rgb/tolerance (do pixel_check) + image_timeout/wait_for/skip (do wait_image)
        if action == "wait_pixel":
            r = max(0, min(255, _int(self._var_color_r)))
            g = max(0, min(255, _int(self._var_color_g)))
            b = max(0, min(255, _int(self._var_color_b)))
            color_rgb       = [r, g, b]
            color_tolerance = max(0, min(255, _int(self._var_tolerance, 10)))
            image_timeout_ms = max(50, _int(self._var_img_timeout, 5000))
            image_wait_for   = self._var_img_wait_for.get() or "present"
            image_skip_steps = max(0, _int(self._var_img_skip, 0))

        # call_macro — kind + target
        call_target_kind = "slot"
        call_target = "1"
        if action == "call_macro":
            call_target_kind = self._var_call_kind.get() or "slot"
            call_target = self._var_call_target.get().strip()

        # fishing_pd_track — região + 3 cores + PD params
        fish_player_color = None
        fish_target_color = None
        fish_kp = 0.3
        fish_kd = 0.15
        fish_pd_clamp = 1.0
        fish_min_pixels = 3
        fish_wall_ratio = 0.0
        fish_fps = 30
        if action == "fishing_pd_track":
            # Player/target colors via 3 entries cada
            def _rgb(vr, vg, vb):
                return [max(0, min(255, _int(vr))),
                        max(0, min(255, _int(vg))),
                        max(0, min(255, _int(vb)))]
            fish_player_color = _rgb(self._var_fish_player_r,
                                      self._var_fish_player_g,
                                      self._var_fish_player_b)
            fish_target_color = _rgb(self._var_fish_target_r,
                                      self._var_fish_target_g,
                                      self._var_fish_target_b)
            try:
                fish_kp = max(0.01, float(self._var_fish_kp.get() or "0.3"))
            except ValueError:
                fish_kp = 0.3
            try:
                fish_kd = max(0.0, float(self._var_fish_kd.get() or "0.15"))
            except ValueError:
                fish_kd = 0.15
            try:
                fish_pd_clamp = max(0.01, float(self._var_fish_pd_clamp.get() or "1.0"))
            except ValueError:
                fish_pd_clamp = 1.0
            try:
                fish_min_pixels = max(1, _int(self._var_fish_min_pixels, 3))
            except ValueError:
                fish_min_pixels = 3
            try:
                fish_wall_ratio = max(0.0, min(0.5, float(self._var_fish_wall_ratio.get() or "0.0")))
            except ValueError:
                fish_wall_ratio = 0.0
            try:
                fish_fps = max(0, _int(self._var_fish_fps, 30))
            except ValueError:
                fish_fps = 30
            # Reusa color_rgb (guia), ocr_w/ocr_h (regiao), color_tolerance, image_timeout_ms
            color_rgb = _rgb(self._var_color_r, self._var_color_g, self._var_color_b)
            color_tolerance = max(0, min(255, _int(self._var_tolerance, 5)))
            ocr_w = max(0, _int(self._var_ocr_w))
            ocr_h = max(0, _int(self._var_ocr_h))
            image_timeout_ms = max(1000, _int(self._var_img_timeout, 60000))

        # ai_prompt — backend/model/prompts/temperature/key/url/timeout/vision
        ai_backend         = "ollama"
        ai_model           = ""
        ai_prompt_text     = ""
        ai_system_prompt   = ""
        ai_temperature     = 0.7
        ai_base_url        = ""
        ai_api_key         = ""
        ai_timeout_s       = 30
        ai_vision_enabled  = False
        if action == "ai_prompt":
            ai_backend   = self._var_ai_backend.get() or "ollama"
            ai_model     = self._var_ai_model.get().strip()
            ai_prompt_text = (self._ai_prompt_widget.get("1.0", "end-1c")
                              if self._ai_prompt_widget else self._var_ai_prompt_text.get())
            ai_system_prompt = (self._ai_system_widget.get("1.0", "end-1c")
                                if self._ai_system_widget else self._var_ai_system_prompt.get())
            try:
                ai_temperature = max(0.0, min(2.0, float(self._var_ai_temperature.get() or "0.7")))
            except ValueError:
                ai_temperature = 0.7
            ai_base_url  = self._var_ai_base_url.get().strip()
            ai_api_key   = self._var_ai_api_key.get()
            ai_timeout_s = max(5, _int(self._var_ai_timeout, 30))
            ai_vision_enabled = bool(self._var_ai_vision_enabled.get())
            var_name     = self._var_var_name.get().strip()
            # Vision: x/y/ocr_w/ocr_h vêm das vars compartilhadas (já populadas
            # via _capture_ocr_region quando usuário arrasta a região)
            if ai_vision_enabled:
                ocr_w = max(0, _int(self._var_ocr_w))
                ocr_h = max(0, _int(self._var_ocr_h))

        # http_request — URL/método/body/headers/auth/timeout + var_name pra resposta
        http_url = ""
        http_method = "POST"
        http_body = ""
        http_headers = ""
        http_auth_kind = "none"
        http_auth_value = ""
        http_timeout_s = 10
        http_save_status_var = ""
        if action == "http_request":
            http_url = self._var_http_url.get().strip()
            http_method = (self._var_http_method.get() or "POST").upper()
            # Body/Headers vêm dos Text widgets se existem (modo dialog aberto),
            # senão das StringVars (cobre carregamento de step salvo sem abrir)
            if self._http_body_widget:
                http_body = self._http_body_widget.get("1.0", "end-1c")
            else:
                http_body = self._var_http_body.get()
            if self._http_headers_widget:
                http_headers = self._http_headers_widget.get("1.0", "end-1c")
            else:
                http_headers = self._var_http_headers.get()
            http_auth_kind = self._var_http_auth_kind.get() or "none"
            http_auth_value = self._var_http_auth_value.get()
            http_timeout_s = max(1, _int(self._var_http_timeout, 10))
            http_save_status_var = self._var_http_save_status.get().strip()
            # var_name reaproveitado pra "salvar body em" — sobrescreve qualquer valor anterior
            var_name = self._var_var_name.get().strip()

        self._result = MacroStep(
            action=action,
            x=x,
            y=y,
            delay_ms=delay,
            button=self._var_button.get(),
            text=text,
            key=self._var_key.get() if action == "key_press" else None,
            scroll_dy=_int(self._var_scroll_dy, 3),
            scroll_smooth=bool(self._var_scroll_smooth.get()),
            repeat=repeat,
            color_rgb=color_rgb,
            skip_steps=skip_steps,
            color_condition=color_condition,
            color_tolerance=color_tolerance,
            image_data=image_data,
            image_threshold=image_threshold,
            image_timeout_ms=image_timeout_ms,
            image_skip_steps=image_skip_steps,
            ocr_w=ocr_w,
            ocr_h=ocr_h,
            ocr_var=ocr_var,
            ocr_lang=ocr_lang,
            ocr_whitelist=ocr_whitelist,
            ocr_to_number=ocr_to_number,
            var_name=var_name,
            var_value=var_value,
            var_op=var_op,
            cond_type=cond_type,
            cond_op=cond_op,
            cond_value=cond_value,
            x2=x2,
            y2=y2,
            drag_duration_ms=drag_duration_ms,
            image_wait_for=image_wait_for,
            call_target_kind=call_target_kind,
            call_target=call_target,
            text_to_find=text_to_find,
            text_match_mode=text_match_mode,
            text_case_sensitive=text_case_sensitive,
            text_use_region=text_use_region,
            text_skip_steps=text_skip_steps,
            window_title=window_title,
            window_timeout_ms=window_timeout_ms,
            http_url=http_url,
            http_method=http_method,
            http_body=http_body,
            http_headers=http_headers,
            http_auth_kind=http_auth_kind,
            http_auth_value=http_auth_value,
            http_timeout_s=http_timeout_s,
            http_save_status_var=http_save_status_var,
            ai_backend=ai_backend,
            ai_model=ai_model,
            ai_prompt_text=ai_prompt_text,
            ai_system_prompt=ai_system_prompt,
            ai_temperature=ai_temperature,
            ai_base_url=ai_base_url,
            ai_api_key=ai_api_key,
            ai_timeout_s=ai_timeout_s,
            ai_vision_enabled=ai_vision_enabled,
            fish_player_color=fish_player_color,
            fish_target_color=fish_target_color,
            fish_kp=fish_kp,
            fish_kd=fish_kd,
            fish_pd_clamp=fish_pd_clamp,
            fish_min_pixels=fish_min_pixels,
            fish_wall_ratio=fish_wall_ratio,
            fish_fps=fish_fps,
            delay_ms_min=delay_ms_min,
            delay_ms_max=delay_ms_max,
        )
        self.destroy()

    # ─────────────────────────────────────────────────────────────
    # HELPER BUTTON
    # ─────────────────────────────────────────────────────────────
    def _btn(self, parent, text, command, bg, fg=None, padx=12, pady=6):
        # Se fg não foi especificado, escolhe automaticamente baseado no bg
        if fg is None:
            try:
                r = int(bg[1:3], 16); g = int(bg[3:5], 16); b = int(bg[5:7], 16)
                fg = "#000000" if (r + g + b) / 3 > 128 else "#ededed"
            except Exception:
                fg = "#ededed"
        return make_button(parent, text, command, bg, fg=fg, padx=padx, pady=pady)

    # ─────────────────────────────────────────────────────────────
    # RESULTADO
    # ─────────────────────────────────────────────────────────────
    @property
    def result(self) -> MacroStep | None:
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# DIÁLOGO: Stop Condition
# ─────────────────────────────────────────────────────────────────────────────
from core.macro_schema import StopCondition


class StopConditionDialog(tk.Toplevel):
    """Diálogo modal para criar ou editar uma StopCondition."""

    def __init__(self, parent, T: dict, driver=None, sc: StopCondition | None = None) -> None:
        super().__init__(parent)
        self._T = T
        self._driver = driver
        self._result: StopCondition | None = None
        self._image_data_b64 = sc.image_data if sc else None
        self._image_preview_label: tk.Label | None = None

        self.title("Editar Condição de Parada" if sc else "Nova Condição de Parada")
        self.configure(bg=T["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # State vars
        self._v_type      = tk.StringVar(value=sc.type if sc else "image")
        self._v_label     = tk.StringVar(value=sc.label if sc else "")
        self._v_threshold = tk.StringVar(value=str(int((sc.image_threshold if sc else 0.9) * 100)))
        self._v_x         = tk.StringVar(value=str(sc.x) if sc and sc.x is not None else "")
        self._v_y         = tk.StringVar(value=str(sc.y) if sc and sc.y is not None else "")
        _rgb = sc.color_rgb if sc and sc.color_rgb else [0, 0, 0]
        self._v_r         = tk.StringVar(value=str(_rgb[0]))
        self._v_g         = tk.StringVar(value=str(_rgb[1]))
        self._v_b         = tk.StringVar(value=str(_rgb[2]))
        self._v_tol       = tk.StringVar(value=str(sc.color_tolerance if sc else 10))
        self._v_varname   = tk.StringVar(value=sc.var_name if sc else "")
        self._v_varop     = tk.StringVar(value=sc.var_op if sc else "==")
        self._v_varvalue  = tk.StringVar(value=sc.var_value if sc else "")
        self._v_enabled   = tk.BooleanVar(value=sc.enabled if sc else True)
        self._color_preview: tk.Label | None = None

        self._build()
        self._v_type.trace_add("write", lambda *_: self._refresh_fields())

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - self.winfo_width())  // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{px}+{py}")

    def _build(self) -> None:
        T = self._T

        top = tk.Frame(self, bg=T["bg"])
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="Tipo:", bg=T["bg"], fg=T["text"],
                 font=("Segoe UI", 10)).pack(side="left")
        ttk.Combobox(top, textvariable=self._v_type, values=["image", "pixel", "var"],
                     state="readonly", width=10, font=("Segoe UI", 10)
                     ).pack(side="left", padx=8)

        nm = tk.Frame(self, bg=T["bg"])
        nm.pack(fill="x", padx=16, pady=4)
        tk.Label(nm, text="Nome (label):", bg=T["bg"], fg=T["subtext"],
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(nm, textvariable=self._v_label, width=28, bg=T["card"],
                 fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                 relief="flat", bd=4).pack(side="left", padx=8)

        en = tk.Frame(self, bg=T["bg"])
        en.pack(fill="x", padx=16, pady=2)
        tk.Checkbutton(en, text="Ativada", variable=self._v_enabled,
                       bg=T["bg"], fg=T["text"], selectcolor=T.get("sel", "#7a1a1a"),
                       activebackground=T["bg"], font=("Segoe UI", 10)
                       ).pack(side="left")

        self._fields = tk.Frame(self, bg=T["bg"])
        self._fields.pack(fill="x", padx=16, pady=4)
        self._refresh_fields()

        btns = tk.Frame(self, bg=T["bg"])
        btns.pack(fill="x", padx=16, pady=(8, 14))
        make_button(btns, "✔ OK", self._ok, T["accent"], fg=T["bg"],
                    padx=10, pady=5).pack(side="left", padx=(0, 8))
        make_button(btns, "✕ Cancelar", self.destroy, T["card"], fg=T["text"],
                    padx=10, pady=5).pack(side="left")

    def _refresh_fields(self) -> None:
        T = self._T
        f = self._fields
        for w in f.winfo_children():
            w.destroy()

        def lbl(text, row, col=0):
            tk.Label(f, text=text, bg=T["bg"], fg=T["subtext"],
                     font=("Segoe UI", 10)).grid(row=row, column=col, sticky="w", pady=3)

        def entry(var, row, col=1, w=8):
            tk.Entry(f, textvariable=var, width=w, bg=T["card"], fg=T["text"],
                     insertbackground=T["text"], font=("Consolas", 11),
                     justify="center", relief="flat", bd=4
                     ).grid(row=row, column=col, sticky="w")

        t = self._v_type.get()

        if t == "image":
            make_button(f, "📷 Capturar Região", self._capture_image, T["accent2"],
                        padx=8, pady=4).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
            self._image_preview_label = tk.Label(f, bg=T["card"], width=8, height=4,
                                                  text="sem\ntemplate", fg=T["subtext"])
            self._image_preview_label.grid(row=0, column=2, rowspan=2, padx=8)
            self._update_image_preview()
            lbl("Confiança (%):", 1)
            tk.Spinbox(f, textvariable=self._v_threshold, from_=50, to=100,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=1, column=1, sticky="w")
            tk.Label(f, text="Macro para se essa imagem aparecer na tela.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=2, column=0, columnspan=3, sticky="w")

        elif t == "pixel":
            lbl("X:", 0); entry(self._v_x, 0)
            lbl("Y:", 1); entry(self._v_y, 1)
            make_button(f, "🎨 Capturar Cor (3s)", self._capture_color, T["accent2"],
                        padx=6, pady=3).grid(row=0, column=2, rowspan=2, padx=8)

            self._color_preview = tk.Label(f, text="  ",
                                            bg=self._hex(), relief="solid", bd=1, width=4)
            self._color_preview.grid(row=0, column=3, rowspan=2, padx=4)

            lbl("R:", 2); entry(self._v_r, 2, w=5)
            lbl("G:", 3); entry(self._v_g, 3, w=5)
            lbl("B:", 4); entry(self._v_b, 4, w=5)
            for v in (self._v_r, self._v_g, self._v_b):
                v.trace_add("write", lambda *_: self._update_color_preview())
            lbl("Tolerância:", 5)
            tk.Spinbox(f, textvariable=self._v_tol, from_=0, to=255,
                       width=5, bg=T["card"], fg=T["text"], relief="flat",
                       font=("Consolas", 10)).grid(row=5, column=1, sticky="w")
            tk.Label(f, text="Macro para se o pixel bater com essa cor.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=6, column=0, columnspan=4, sticky="w")

        elif t == "var":
            lbl("Variável:", 0)
            tk.Entry(f, textvariable=self._v_varname, width=18, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=0, column=1, columnspan=2, sticky="w")
            lbl("Operador:", 1)
            ttk.Combobox(f, textvariable=self._v_varop, values=COND_OPS_VAR,
                         state="readonly", width=12, font=("Segoe UI", 10)
                         ).grid(row=1, column=1, sticky="w")
            lbl("Valor:", 2)
            tk.Entry(f, textvariable=self._v_varvalue, width=22, bg=T["card"],
                     fg=T["text"], insertbackground=T["text"], font=("Consolas", 11),
                     relief="flat", bd=4).grid(row=2, column=1, columnspan=2, sticky="w")
            tk.Label(f, text="Macro para quando essa condição virar verdadeira.",
                     bg=T["bg"], fg=T["subtext"], font=("Segoe UI", 8)
                     ).grid(row=3, column=0, columnspan=3, sticky="w")

    def _hex(self) -> str:
        try:
            r = max(0, min(255, int(self._v_r.get() or 0)))
            g = max(0, min(255, int(self._v_g.get() or 0)))
            b = max(0, min(255, int(self._v_b.get() or 0)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except ValueError:
            return "#000000"

    def _update_color_preview(self) -> None:
        if self._color_preview:
            self._color_preview.config(bg=self._hex())

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

    def _update_image_preview(self) -> None:
        if not self._image_preview_label:
            return
        if not self._image_data_b64:
            self._image_preview_label.config(image="", text="sem\ntemplate")
            return
        try:
            import base64, io
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

        canvas = tk.Canvas(overlay, bg="black", highlightthickness=0, cursor="crosshair")
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
            return
        left = max(0, min(left, sw)); top = max(0, min(top, sh))
        right = max(0, min(right, sw)); bottom = max(0, min(bottom, sh))

        cropped = screenshot.crop((left, top, right, bottom))
        import base64, io
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        self._image_data_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self._update_image_preview()

    def _ok(self) -> None:
        def _int(var, d=0):
            try: return int(var.get() or d)
            except ValueError: return d

        t = self._v_type.get()
        sc = StopCondition(
            type=t,
            label=self._v_label.get().strip(),
            enabled=bool(self._v_enabled.get()),
        )
        if t == "image":
            sc.image_data      = self._image_data_b64
            sc.image_threshold = max(0.5, min(1.0, _int(self._v_threshold, 90) / 100))
        elif t == "pixel":
            sc.x = _int(self._v_x) if self._v_x.get().strip() else None
            sc.y = _int(self._v_y) if self._v_y.get().strip() else None
            r = max(0, min(255, _int(self._v_r)))
            g = max(0, min(255, _int(self._v_g)))
            b = max(0, min(255, _int(self._v_b)))
            sc.color_rgb       = [r, g, b]
            sc.color_tolerance = max(0, min(255, _int(self._v_tol, 10)))
        elif t == "var":
            sc.var_name  = self._v_varname.get().strip()
            sc.var_op    = self._v_varop.get() or "=="
            sc.var_value = self._v_varvalue.get()

        self._result = sc
        self.destroy()

    @property
    def result(self) -> StopCondition | None:
        return self._result
