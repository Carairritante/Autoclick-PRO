"""
ui/theme.py — Constantes globais de tema, fonte e branding.

`T` é um dict mutável compartilhado. `_toggle_theme` em app.py muta
in-place (`T.clear(); T.update(...)`) — NUNCA reatribua `T = ...`, senão
módulos que já fizeram `from ui.theme import T` ficam com a referência
antiga e o tema quebra.
"""
from __future__ import annotations

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
# T mutável — _toggle_theme troca os valores in-place pra todos os widgets pegarem
T = dict(THEME_DARK)

# ─── FONTES ───────────────────────────────────────────────────────────────────
# Fonte mono (JetBrains Mono cai em Consolas se não instalado)
FONT_MONO = "JetBrains Mono"
FONT_UI   = "Segoe UI"

# ─── CHAVE PIX PARA DONATIONS ─────────────────────────────────────────────────
# Edite esta linha com sua chave PIX (CPF, email, celular ou aleatória).
# Aparece no botão "❤ Apoie o projeto" na aba Configurações.
PIX_KEY   = "ngnicol123.cs@gmail.com"
PIX_OWNER = "Nicolas Gabriel"   # Nome de quem recebe (aparece no diálogo)
