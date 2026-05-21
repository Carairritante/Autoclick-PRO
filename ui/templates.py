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
CAT_INTEG   = "🔌 Integrações"
CAT_HS      = "✨ Hotstrings"
# Ordem em que aparecem no notebook
CATEGORIES_ORDER = [CAT_GAMES, CAT_WORK, CAT_ACCESS, CAT_INTEG, CAT_HS]


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
    Template(
        id="gpo_fishing_auto_tap",
        name="Pesca GPO — PD Tracking",
        category=CAT_GAMES,
        icon="🎣",
        description=(
            "Pesca no Grand Piece Online via PD control: rastreia o marcador "
            "(peixe branco) vs alvo movel (barra cinza) e segura/solta o mouse "
            "pra manter alinhado. Igual ao macro dedicado do GPO."
        ),
        type="macro",
        warning=(
            "Como funciona o minigame GPO: o medidor tem uma coluna AZUL fixa "
            "que marca a area de pesca. Dentro dela, um PEIXE BRANCO sobe quando "
            "voce segura o mouse e cai quando solta. Voce deve manter o peixe "
            "alinhado com a BARRA CINZA que se move dentro do medidor.\n\n"
            "ANTES DE RODAR:\n"
            "1) Entre numa pescada (lance a vara e espere a mordida)\n"
            "2) Edite o step 'fishing_pd_track' e clique 'Selecionar Regiao do "
            "Medidor' — arraste cobrindo TODO o medidor vertical (coluna azul + "
            "marcadores).\n"
            "3) As 3 cores ja vem com os defaults do GPO:\n"
            "   - Guia (coluna azul): RGB(85, 170, 255)\n"
            "   - Peixe (marker branco): RGB(255, 255, 255)\n"
            "   - Alvo (barra cinza): RGB(25, 25, 25)\n"
            "   Se cor diferir no seu jogo, ajuste no editor.\n\n"
            "VOCE deve lancar a vara manualmente. O macro detecta quando a coluna "
            "azul aparece (= minigame ativo), faz PD control, e sai quando a "
            "coluna azul some (= peixe pego/perdido). Roda em loop infinito.\n\n"
            "Macros no Roblox violam os ToS — use por sua conta e risco."
        ),
        config={
            "macro_steps": [
                # ── PD tracking do minigame de pesca ─────────────
                # Regiao default: vai precisar ajustar via 'Selecionar Regiao'
                # Defaults GPO: coluna azul + peixe branco + barra cinza
                {"action": "fishing_pd_track",
                 "x": 1700, "y": 300,
                 "ocr_w": 50, "ocr_h": 400,
                 "color_rgb": [85, 170, 255],        # guia (coluna azul)
                 "fish_player_color": [255, 255, 255], # peixe (branco)
                 "fish_target_color": [25, 25, 25],   # alvo (cinza escuro)
                 "color_tolerance": 5,
                 "fish_kp": 0.3,
                 "fish_kd": 0.15,
                 "button": "left",
                 "image_timeout_ms": 60000,           # 60s max por pescada
                 "delay_ms": 0},
                # Aguarda 3s entre pescadas (animacao de loot + recasting)
                {"action": "wait", "delay_ms": 3000},
            ],
            "macro_speed": "1",
            "rep_mode": "infinite",
        },
    ),
    Template(
        id="naramo_manutencao_usina",
        name="Naramo — Skill Check E/Q",
        category=CAT_GAMES,
        icon="⚛",
        description=(
            "Pressiona E ou Q automaticamente quando a barra vermelha entra na zona "
            "azul. Voce segura o botao do mouse manualmente — o macro so cuida do timing."
        ),
        type="macro",
        warning=(
            "ANTES DE RODAR — entre no minigame uma vez e capture 2 cores no editor (F10):\n\n"
            "1) wait_pixel (step 1): clique 'Capturar Cor' apontando pro CENTRO da zona azul\n"
            "   no momento em que a barra vermelha esta passando por la — pega a cor\n"
            "   vermelha (algo como RGB ~220,30,30).\n\n"
            "2) if pixel (step 2): clique 'Capturar Cor' apontando pra um pixel\n"
            "   DENTRO do glifo da letra Q (de preferencia uma area que so existe em Q,\n"
            "   nao em E — exemplo: o 'rabinho' inferior direito de Q).\n\n"
            "Voce segura o mouse esquerdo o tempo todo do minigame. O macro fica em loop\n"
            "esperando barras chegarem e pressionando a tecla correta."
        ),
        config={
            "macro_steps": [
                # ── 1. Timing: aguarda barra vermelha chegar no centro da zona azul ──
                # EDITE x/y pro centro real da zona azul (use F10 / 'Capturar Cor')
                # EDITE color_rgb pra cor da PONTA da barra vermelha
                {"action": "wait_pixel",
                 "x": 960, "y": 540,
                 "color_rgb": [220, 30, 30],
                 "color_tolerance": 35,
                 "image_timeout_ms": 4000,
                 "image_wait_for": "present",
                 "image_skip_steps": 6,  # se nao chegar em 4s, pula todo o bloco
                 "delay_ms": 0},
                # ── 2. Detecta letra: pixel DENTRO do glifo Q (ausente em E) ──────
                # EDITE x/y pra pixel caracteristico de Q (ex: rabinho inferior)
                # EDITE color_rgb pra cor da letra renderizada (geralmente branca)
                {"action": "if",
                 "cond_type": "pixel",
                 "x": 960, "y": 480,
                 "color_rgb": [255, 255, 255],
                 "color_tolerance": 30,
                 "cond_op": "match",
                 "delay_ms": 0},
                # 3. Pixel branco encontrado → e a letra Q
                {"action": "key_press", "key": "q", "delay_ms": 0},
                {"action": "else"},
                # 4. Pixel ausente → e a letra E
                {"action": "key_press", "key": "e", "delay_ms": 0},
                {"action": "endif"},
                # ── 5. Anti-spam: nao deixa pressionar 2x na mesma zona ──────────
                {"action": "wait", "delay_ms": 100},
            ],
            "macro_speed": "1",
            "rep_mode": "infinite",
        },
    ),
    Template(
        id="naramo_reator_estabilizar",
        name="Naramo — Anti-AFK no plantao",
        category=CAT_GAMES,
        icon="🔧",
        description=(
            "Mantem o personagem ativo durante turnos longos no Naramo: "
            "movimenta WASD periodicamente pra nao ser kickado por AFK."
        ),
        type="macro",
        warning=(
            "Controlar reator/manutencao precisa de DECISOES baseadas em valores "
            "que mudam o tempo todo — um macro fixo nao consegue fazer isso bem. "
            "Este template so resolve o AFK durante plantoes longos.\n\n"
            "Para o minigame E/Q de reparo, use 'Naramo — Skill Check E/Q'."
        ),
        config={
            "macro_steps": [
                # ── Movimenta personagem brevemente (2 passos pra cada lado) ──
                {"action": "key_press", "key": "d", "delay_ms": 0},
                {"action": "wait", "delay_ms": 200},
                {"action": "key_press", "key": "a", "delay_ms": 0},
                # ── Aguarda 4 minutos antes do proximo movimento ──
                {"action": "wait", "delay_ms": 240000},
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

    # ═══ INTEGRAÇÕES (usam o step http_request) ══════════════════
    Template(
        id="discord_webhook_notify",
        name="Notificar Discord (Webhook)",
        category=CAT_INTEG,
        icon="💬",
        description="Manda 'Olá do AutoClick!' num canal do Discord via webhook. Edite a URL com seu webhook.",
        type="macro",
        warning="Cole a URL do seu webhook Discord no step (Config do canal → Integrações → Webhooks).",
        config={
            "macro_steps": [
                {"action": "http_request",
                 "http_url": "https://discord.com/api/webhooks/SEU/WEBHOOK_AQUI",
                 "http_method": "POST",
                 "http_body": '{"content": "Olá do AutoClick Pro! 🤖"}',
                 "delay_ms": 0},
            ],
            "macro_speed": "1",
            "rep_mode": "count",
            "rep_count": "1",
        },
    ),
    Template(
        id="telegram_bot_notify",
        name="Notificar Telegram (Bot)",
        category=CAT_INTEG,
        icon="✈",
        description="Manda mensagem via bot do Telegram. Precisa de bot token (@BotFather) e chat_id.",
        type="macro",
        warning="Substitua BOT_TOKEN e CHAT_ID na URL. Crie bot em @BotFather no Telegram.",
        config={
            "macro_steps": [
                {"action": "http_request",
                 "http_url": "https://api.telegram.org/botBOT_TOKEN/sendMessage",
                 "http_method": "POST",
                 "http_body": '{"chat_id": "CHAT_ID", "text": "Olá do AutoClick Pro!"}',
                 "delay_ms": 0},
            ],
            "macro_speed": "1",
            "rep_mode": "count",
            "rep_count": "1",
        },
    ),
    Template(
        id="alert_when_text_appears",
        name="Alerta: texto na tela → Discord",
        category=CAT_INTEG,
        icon="🚨",
        description="Vigia a tela toda. Quando 'GAME OVER' aparece (OCR), avisa no Discord. Edite o texto e URL.",
        type="macro",
        warning="Loop infinito + OCR a cada 2s. Edite o trigger 'GAME OVER' e a URL do webhook. Precisa do Tesseract OCR instalado.",
        config={
            "macro_steps": [
                {"action": "click_text",
                 "text_to_find": "GAME OVER",
                 "text_match_mode": "contains",
                 "text_use_region": False,
                 "text_skip_steps": 1,
                 "delay_ms": 0},
                {"action": "http_request",
                 "http_url": "https://discord.com/api/webhooks/SEU/WEBHOOK",
                 "http_method": "POST",
                 "http_body": '{"content": "🚨 Texto detectado na tela!"}',
                 "delay_ms": 0},
                {"action": "wait", "delay_ms": 2000},
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
        app._set_status(f"📚 Template carregado: {tpl.name}", toast=True)
        return True

    if tpl.type == "autokey":
        if "type_text" in tpl.config:
            app.type_text.delete("1.0", "end")
            app.type_text.insert("1.0", tpl.config["type_text"])
        rest = {k: v for k, v in tpl.config.items() if k != "type_text"}
        _set_vars(app, rest)
        app._nb.select(app.tab_key)
        app._set_status(f"📚 Template carregado: {tpl.name}", toast=True)
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
        app._set_status(f"📚 Template carregado: {tpl.name}", toast=True)
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
        app._set_status(f"📚 Hotstring '{tpl.config.get('trigger')}' adicionada.", toast=True)
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
