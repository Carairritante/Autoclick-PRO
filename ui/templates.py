"""
ui/templates.py — Biblioteca de templates prontos + helper de aplicação.

Templates cobrem 4 tipos: autoclick, autokey, macro, hotstring. Cada um
configura a feature relevante via `var_*` ou objetos do schema. O usuário
escolhe na galeria (ui/template_gallery.py) e o app aplica via
`apply_template(app, tpl)`.

Adicionar template novo: anexar dict na lista TEMPLATES abaixo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from tkinter import messagebox


# ─── Categorias ──────────────────────────────────────────────────────
CAT_GAMES   = "🎮 Jogos"
CAT_WORK    = "💼 Trabalho"
CAT_ACCESS  = "♿ Acessibilidade"
CAT_HS      = "✨ Hotstrings"
# Ordem em que aparecem no notebook
CATEGORIES_ORDER = [CAT_GAMES, CAT_WORK, CAT_ACCESS, CAT_HS]


@dataclass
class Template:
    id: str                           # slug único, ex: "afk_clicker_2s"
    name: str                         # "AFK Clicker 2s"
    category: str                     # ver CAT_* acima
    icon: str                         # emoji exibido no card (renderizado grande)
    description: str                  # 1-2 frases curtas
    type: str                         # "autoclick" | "autokey" | "macro" | "hotstring"
    config: dict = field(default_factory=dict)
    warning: str = ""                 # opcional, ex: "Use com cuidado em jogos online"


# ─── Catálogo de templates ───────────────────────────────────────────
TEMPLATES: list[Template] = [
    # ═══ JOGOS ═══════════════════════════════════════════════════
    Template(
        id="afk_clicker_2s",
        name="AFK Clicker 2s",
        category=CAT_GAMES,
        icon="🐢",
        description="Clica sozinho a cada 2 segundos. Perfeito pra ficar AFK em jogos sem ser kickado.",
        type="autoclick",
        config={
            "var_mouse_btn": "left",
            "var_click_type": "single",
            "var_interval_h": "0", "var_interval_m": "0",
            "var_interval_s": "2", "var_interval_ms": "0",
            "var_pos_mode": "cursor",
            "var_rep_mode": "infinite",
            "var_burst": "1",
        },
    ),
    Template(
        id="spam_click_turbo",
        name="Spam Click Turbo",
        category=CAT_GAMES,
        icon="⚡",
        description="Clica freneticamente (50ms entre cliques). Útil pra farm/pesca em jogos offline.",
        type="autoclick",
        warning="Pode ser detectado como bot em jogos online com anti-cheat.",
        config={
            "var_mouse_btn": "left",
            "var_click_type": "single",
            "var_interval_h": "0", "var_interval_m": "0",
            "var_interval_s": "0", "var_interval_ms": "50",
            "var_pos_mode": "cursor",
            "var_rep_mode": "infinite",
            "var_burst": "1",
        },
    ),
    Template(
        id="spam_chat_msg",
        name="Spam mensagem chat",
        category=CAT_GAMES,
        icon="💬",
        description="Manda a mesma mensagem várias vezes no chat. Edite o texto e abra o chat antes.",
        type="autokey",
        config={
            "type_text": "Mensagem aqui",
            "var_type_paste": True,
            "var_type_enter": True,
            "var_type_interval": "1000",
            "var_type_interval_max": "",
            "var_type_rep_mode": "count",
            "var_type_rep_count": "50",
            "var_type_delay": "3",
        },
    ),
    Template(
        id="pesca_minecraft",
        name="Pesca Minecraft",
        category=CAT_GAMES,
        icon="🎣",
        description="Botão direito + espera 5s, em loop. Pesca AFK em Minecraft (foque o jogo antes).",
        type="macro",
        config={
            "macro_steps": [
                {"action": "click", "button": "right", "delay_ms": 0},
                {"action": "wait", "delay_ms": 5000},
            ],
            "macro_speed": "1",
            "rep_mode": "infinite",
        },
    ),
    Template(
        id="roblox_anti_afk",
        name="Anti-AFK Roblox",
        category=CAT_GAMES,
        icon="🚀",
        description="Aperta Space a cada 60s pra Roblox não te kickar por inatividade.",
        type="macro",
        config={
            "macro_steps": [
                {"action": "key_press", "key": "space", "delay_ms": 0},
                {"action": "wait", "delay_ms": 60000},
            ],
            "macro_speed": "1",
            "rep_mode": "infinite",
        },
    ),

    # ═══ TRABALHO ════════════════════════════════════════════════
    Template(
        id="hs_email",
        name="Email",
        category=CAT_WORK,
        icon="📧",
        description="Digita ':em:' em qualquer app pra inserir seu email automaticamente.",
        type="hotstring",
        config={
            "trigger": ":em:",
            "expand": "seu@email.com",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_assinatura",
        name="Assinatura de email",
        category=CAT_WORK,
        icon="✍",
        description="Digite ':sig:' pra inserir sua assinatura completa em emails e mensagens.",
        type="hotstring",
        config={
            "trigger": ":sig:",
            "expand": "Atenciosamente,\nSeu Nome\n📧 seu@email.com\n📱 (11) 99999-9999",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_pix",
        name="Chave PIX",
        category=CAT_WORK,
        icon="💰",
        description="Digite ':pix:' pra colar sua chave PIX (edite o texto depois).",
        type="hotstring",
        config={
            "trigger": ":pix:",
            "expand": "Chave PIX: seuemail@gmail.com\nNome: Seu Nome Completo",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_obg",
        name="Agradecimento",
        category=CAT_WORK,
        icon="🙏",
        description="Digite ':obg:' pra inserir resposta padrão de agradecimento.",
        type="hotstring",
        config={
            "trigger": ":obg:",
            "expand": "Muito obrigado pela atenção! Aguardo seu retorno.",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="form_tab_type",
        name="Preencher formulário",
        category=CAT_WORK,
        icon="📋",
        description="Preenche 3 campos com Tab entre eles. Edite os textos no editor depois.",
        type="macro",
        config={
            "macro_steps": [
                {"action": "type", "text": "Nome Completo", "delay_ms": 0},
                {"action": "key_press", "key": "tab", "delay_ms": 100},
                {"action": "type", "text": "email@exemplo.com", "delay_ms": 0},
                {"action": "key_press", "key": "tab", "delay_ms": 100},
                {"action": "type", "text": "Mensagem do formulário aqui", "delay_ms": 0},
            ],
            "macro_speed": "1",
            "rep_mode": "count",
            "rep_count": "1",
        },
    ),

    # ═══ ACESSIBILIDADE ══════════════════════════════════════════
    Template(
        id="refresh_f5",
        name="Auto-refresh F5",
        category=CAT_ACCESS,
        icon="🔄",
        description="Aperta F5 a cada 30s. Útil pra recarregar página/dashboard automaticamente.",
        type="autokey",
        config={
            "type_text": "{F5}",
            "var_type_paste": False,
            "var_type_enter": False,
            "var_type_interval": "30000",
            "var_type_interval_max": "",
            "var_type_rep_mode": "infinite",
            "var_type_rep_count": "10",
            "var_type_delay": "3",
        },
    ),
    Template(
        id="keep_alive_space",
        name="Manter ativo (Space)",
        category=CAT_ACCESS,
        icon="🚦",
        description="Aperta Space a cada 5 min. Mantém Teams/Slack/etc com status 'online'.",
        type="autokey",
        config={
            "type_text": "{SPACE}",
            "var_type_paste": False,
            "var_type_enter": False,
            "var_type_interval": "300000",
            "var_type_interval_max": "",
            "var_type_rep_mode": "infinite",
            "var_type_rep_count": "10",
            "var_type_delay": "3",
        },
    ),
    Template(
        id="scroll_loop",
        name="Scroll automático",
        category=CAT_ACCESS,
        icon="📜",
        description="Rola pra baixo de forma fluida em loop. Ideal pra ler textos longos sem mover a mão.",
        type="macro",
        config={
            "macro_steps": [
                # Scroll suave: quebra 1 unidade de wheel em 6 micro-scrolls com
                # 30ms entre eles — sensação de rolagem contínua.
                {"action": "scroll", "scroll_dy": -1, "scroll_smooth": True,
                 "delay_ms": 0},
                {"action": "wait", "delay_ms": 1200},
            ],
            "macro_speed": "1",
            "rep_mode": "infinite",
        },
    ),

    # ═══ HOTSTRINGS RÁPIDAS ══════════════════════════════════════
    Template(
        id="hs_oi",
        name="Saudação rápida",
        category=CAT_HS,
        icon="👋",
        description="':oi:' → 'Olá! Tudo bem?'",
        type="hotstring",
        config={
            "trigger": ":oi:",
            "expand": "Olá! Tudo bem?",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_lorem",
        name="Lorem ipsum",
        category=CAT_HS,
        icon="📝",
        description="':loren:' → texto Lorem Ipsum de 30 palavras pra testar layouts.",
        type="hotstring",
        config={
            "trigger": ":loren:",
            "expand": ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                       "Sed do eiusmod tempor incididunt ut labore et dolore magna "
                       "aliqua ut enim ad minim veniam quis nostrud exercitation."),
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_horario",
        name="Horário comercial",
        category=CAT_HS,
        icon="🕐",
        description="':horario:' → 'Segunda a sexta, 9h às 18h. Sábado 9h às 13h.'",
        type="hotstring",
        config={
            "trigger": ":horario:",
            "expand": "Segunda a sexta, 9h às 18h. Sábado 9h às 13h.",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_meet_link",
        name="Link do Google Meet",
        category=CAT_HS,
        icon="🎥",
        description="':meet:' → seu link permanente do Google Meet (edite depois).",
        type="hotstring",
        config={
            "trigger": ":meet:",
            "expand": "https://meet.google.com/seu-link-aqui",
            "enabled": True,
            "force_type": False,
        },
    ),
    Template(
        id="hs_zoom_link",
        name="Link do Zoom",
        category=CAT_HS,
        icon="📹",
        description="':zoom:' → seu link permanente do Zoom (edite depois).",
        type="hotstring",
        config={
            "trigger": ":zoom:",
            "expand": "https://zoom.us/j/seu-link-aqui",
            "enabled": True,
            "force_type": False,
        },
    ),
]


def templates_by_category() -> dict[str, list[Template]]:
    """Agrupa TEMPLATES por categoria, na ordem de CATEGORIES_ORDER."""
    out: dict[str, list[Template]] = {cat: [] for cat in CATEGORIES_ORDER}
    for t in TEMPLATES:
        out.setdefault(t.category, []).append(t)
    return out


def apply_template(app, tpl: Template) -> bool:
    """Aplica template no app. Retorna True se aplicou, False se cancelado.

    - autoclick/autokey: seta as var_* relevantes e troca pra aba certa
    - macro: confirma se já tem steps, depois aplica MacroScript
    - hotstring: bloqueia duplicatas; adiciona à lista e salva
    """
    if tpl.type == "autoclick":
        _set_vars(app, tpl.config)
        app._nb.select(app.tab_click)
        app._set_status(f"📚 Template carregado: {tpl.name}")
        return True

    if tpl.type == "autokey":
        if "type_text" in tpl.config:
            app.type_text.delete("1.0", "end")
            app.type_text.insert("1.0", tpl.config["type_text"])
        rest = {k: v for k, v in tpl.config.items() if k != "type_text"}
        _set_vars(app, rest)
        app._nb.select(app.tab_key)
        app._set_status(f"📚 Template carregado: {tpl.name}")
        return True

    if tpl.type == "macro":
        if app._macro_steps:
            if not messagebox.askyesno(
                "Substituir macro atual?",
                f"Vai substituir os {len(app._macro_steps)} step(s) atuais "
                f"por '{tpl.name}'.\n\nContinuar?",
                parent=app,
            ):
                return False
        from core.macro_schema import MacroScript
        script = MacroScript(**tpl.config)
        app._apply_script(script)
        app._nb.select(app.tab_macro)
        app._set_status(f"📚 Template carregado: {tpl.name}")
        return True

    if tpl.type == "hotstring":
        items = app._hotstrings.get_all()
        if any(h.get("trigger") == tpl.config.get("trigger") for h in items):
            messagebox.showinfo(
                "Hotstring já existe",
                f"O trigger '{tpl.config.get('trigger')}' já existe nas suas hotstrings.",
                parent=app,
            )
            return False
        items.append(dict(tpl.config))
        app._hotstrings.set_all(items)
        app._save_hotstrings()
        app._refresh_hs_tree()
        app._nb.select(app.tab_hs)
        app._set_status(f"📚 Hotstring '{tpl.config.get('trigger')}' adicionada.")
        return True

    return False


def _set_vars(app, config: dict) -> None:
    """Aplica config em var_* tk variables. Lida com Bool vs StringVar."""
    for var_name, val in config.items():
        try:
            var = getattr(app, var_name)
        except AttributeError:
            continue
        try:
            if isinstance(val, bool):
                var.set(val)  # BooleanVar
            else:
                var.set(str(val))  # StringVar
        except Exception:
            pass
