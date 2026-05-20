"""
core/ai_assistant.py — Assistente de IA que gera macros via LLM.

Mantém histórico de chat e parseia blocos ```json``` das respostas
extraindo arrays de MacroStep prontos pra aplicar no editor.

Stateless quanto a config (UI passa a cada chamada) — só guarda histórico
da conversa atual, que é efêmero (perdido ao fechar o app).
"""
from __future__ import annotations

import json
import re

from core.ai_client import call_llm


# System prompt que ensina a IA a gerar steps válidos.
# Lista compacta com formato + exemplos few-shot. Inclui ações principais
# (não todas — IA pode aprender pelo padrão).
SYSTEM_PROMPT = """Voce e um assistente que gera macros de automacao para o AutoClick Pro.
Converte descricoes em portugues em JSON de steps validos.

Cada step e um dict com "action" + parametros. Acoes disponiveis:

INTERACAO:
- {"action": "click", "x": 100, "y": 200, "button": "left"}   // sem x/y = cursor atual
- {"action": "double_click", "x": null, "y": null}
- {"action": "right_click", "x": 500, "y": 300}
- {"action": "move", "x": 800, "y": 600}
- {"action": "drag", "x": 100, "y": 100, "x2": 500, "y2": 500, "drag_duration_ms": 300}
- {"action": "scroll", "scroll_dy": -3}                       // + cima, - baixo

TECLADO:
- {"action": "type", "text": "Hello world"}
- {"action": "key_press", "key": "enter"}                     // ou f5, ctrl+c, alt+tab, etc

TEMPO:
- {"action": "wait", "delay_ms": 2000}
- {"action": "wait_window", "window_title": "Notepad", "window_timeout_ms": 5000}

VISAO:
- {"action": "wait_pixel", "x": 100, "y": 100, "color_rgb": [255,0,0], "color_tolerance": 10, "image_timeout_ms": 5000, "image_wait_for": "present"}
- {"action": "click_text", "text_to_find": "Aceitar", "text_match_mode": "contains"}

LOGICA:
- {"action": "set_var", "var_name": "contador", "var_value": "0", "var_op": "set"}
- {"action": "set_var", "var_name": "contador", "var_value": "1", "var_op": "add"}
- {"action": "if", "cond_type": "var", "var_name": "contador", "cond_op": ">", "cond_value": "10"}
- {"action": "else"}
- {"action": "endif"}

INTEGRACAO:
- {"action": "http_request", "http_url": "https://...", "http_method": "POST", "http_body": "{\\"k\\":\\"v\\"}"}
- {"action": "ai_prompt", "ai_backend": "ollama", "ai_model": "llama3.2", "ai_prompt_text": "...", "var_name": "out"}

CADA STEP PODE TER tambem "delay_ms" (espera ANTES) e "repeat" (quantas vezes).

REGRAS:
1. Responda SEMPRE com explicacao curta em portugues + bloco ```json com array de steps.
2. Para loops use 1 step com macro rodando em modo infinito (avise o usuario no texto).
3. NUNCA invente acoes que nao estao na lista acima.
4. Para coordenadas que o usuario nao especificou, use posicoes razoaveis ou null (cursor).
5. Use omissao para campos opcionais (nao preencha campos que nao se aplicam).

EXEMPLO DE RESPOSTA:
Usuario: "abre o notepad e digita oi"
Voce: "Aqui vai:
```json
[
  {"action": "key_press", "key": "win+r"},
  {"action": "wait", "delay_ms": 500},
  {"action": "type", "text": "notepad"},
  {"action": "key_press", "key": "enter"},
  {"action": "wait", "delay_ms": 1000},
  {"action": "type", "text": "oi"}
]
```"
"""


class AIAssistant:
    """Sessão de chat com a IA. Histórico fica em memória até clear()."""

    def __init__(self) -> None:
        # Cada entry: {"role": "user"|"assistant", "content": "..."}
        self.history: list[dict] = []

    def chat(
        self,
        user_message: str,
        *,
        backend: str = "ollama",
        model: str = "llama3.2",
        api_key: str = "",
        base_url: str = "",
        timeout_s: int = 60,
        temperature: float = 0.5,
    ) -> tuple[bool, str]:
        """Envia mensagem (com histórico) e retorna (sucesso, resposta).

        Em sucesso, adiciona user_message e resposta ao histórico.
        Em erro, NÃO adiciona nada — usuário pode tentar de novo limpo.
        """
        # Constrói messages com system + histórico + nova mensagem
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})

        success, text = call_llm(
            backend=backend, model=model, messages=messages,
            api_key=api_key, base_url=base_url,
            timeout_s=timeout_s, temperature=temperature,
        )

        if success:
            self.history.append({"role": "user",      "content": user_message})
            self.history.append({"role": "assistant", "content": text})

        return success, text

    def clear_history(self) -> None:
        self.history.clear()


# Regex pra extrair bloco ```json [...] ``` ou ``` [...] ```
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", re.IGNORECASE)
# Fallback: primeiro [ ... ] cru
_JSON_BARE_RE  = re.compile(r"(\[[\s\S]*\])")


def parse_macro_steps(text: str) -> list[dict]:
    """Extrai array JSON de steps de uma resposta da IA.

    Tolera comentarios //, vírgulas finais antes de ]/}, e múltiplos formatos.
    Retorna lista vazia se não conseguir parsear.
    """
    if not text:
        return []

    match = _JSON_BLOCK_RE.search(text) or _JSON_BARE_RE.search(text)
    if not match:
        return []

    raw = match.group(1)
    # Remove comentarios "// ..." (Python/JS-style)
    raw = re.sub(r"//[^\n]*", "", raw)
    # Remove vírgula final antes de ] ou }
    raw = re.sub(r",(\s*[\]}])", r"\1", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Filtra só dicts com 'action' string — defensivo
    return [s for s in data if isinstance(s, dict) and isinstance(s.get("action"), str)]
