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

from core.ai_client import call_llm, call_llm_stream


# System prompt que ensina a IA a gerar steps válidos.
# Lista compacta + few-shot examples cobrindo loops, condicionais, vision e API.
SYSTEM_PROMPT = """Voce e um assistente que gera macros de automacao para o AutoClick Pro.
Converte descricoes em portugues em JSON de steps validos.

Cada step e um dict com "action" + parametros. Acoes disponiveis:

INTERACAO:
- {"action": "click", "x": 100, "y": 200, "button": "left"}     // sem x/y = cursor atual
- {"action": "double_click", "x": null, "y": null}
- {"action": "right_click", "x": 500, "y": 300}
- {"action": "move", "x": 800, "y": 600}
- {"action": "drag", "x": 100, "y": 100, "x2": 500, "y2": 500, "drag_duration_ms": 300}
- {"action": "scroll", "scroll_dy": -3}                          // + cima, - baixo

TECLADO:
- {"action": "type", "text": "Hello world"}
- {"action": "key_press", "key": "enter"}                        // ou f5, ctrl+c, alt+tab, win+r

TEMPO:
- {"action": "wait", "delay_ms": 2000}
- {"action": "wait_window", "window_title": "Notepad", "window_timeout_ms": 5000}

VISAO:
- {"action": "wait_pixel", "x": 100, "y": 100, "color_rgb": [255,0,0], "color_tolerance": 10, "image_timeout_ms": 5000, "image_wait_for": "present"}
- {"action": "wait_image", "image_wait_for": "present", "image_timeout_ms": 30000}   // requer template (usuario captura no editor)
- {"action": "image_click", "image_threshold": 0.9}              // requer template
- {"action": "click_text", "text_to_find": "Aceitar", "text_match_mode": "contains"}
- {"action": "ocr_read", "x": 100, "y": 100, "ocr_w": 200, "ocr_h": 50, "ocr_var": "texto"}

LOGICA:
- {"action": "set_var", "var_name": "i", "var_value": "0", "var_op": "set"}
- {"action": "set_var", "var_name": "i", "var_value": "1", "var_op": "add"}     // tambem: sub, mul, div, concat
- {"action": "if", "cond_type": "var", "var_name": "i", "cond_op": "<", "cond_value": "10"}
- {"action": "else"}
- {"action": "endif"}
- {"action": "call_macro", "call_target_kind": "slot", "call_target": "1"}      // chama outro macro salvo

INTEGRACAO:
- {"action": "http_request", "http_url": "https://...", "http_method": "POST", "http_body": "{\\"k\\":\\"v\\"}"}
- {"action": "ai_prompt", "ai_backend": "ollama", "ai_model": "llama3.2", "ai_prompt_text": "...", "var_name": "out"}

CAMPOS UNIVERSAIS (qualquer step pode ter):
- "delay_ms": espera ANTES do step
- "repeat": quantas vezes repetir esta acao (default 1)

REGRAS IMPORTANTES:
1. Responda SEMPRE em portugues + bloco ```json com array de steps.
2. NUNCA invente acoes que nao estao na lista acima.
3. Para loops/repeticao, prefira o flag "rep_mode": "infinite" no editor (avise no texto).
4. Use null pra campos opcionais nao usados; omita campos que nao se aplicam.
5. Coordenadas que o usuario nao especificou: use posicoes razoaveis (centro = 960,540) ou null.

EXEMPLOS COMPLETOS:

[1] Anti-AFK simples
Usuario: "pressiona espaco a cada 60 segundos pra nao ficar AFK"
Voce: "Macro simples — configure rep_mode infinite no editor:
```json
[
  {"action": "key_press", "key": "space"},
  {"action": "wait", "delay_ms": 60000}
]
```"

[2] Loop com contador (clica N vezes e para)
Usuario: "clica 10 vezes no centro da tela com 200ms entre cada"
Voce: "Pra clicar exatamente 10 vezes use rep_mode=count, rep_count=10 no editor com:
```json
[
  {"action": "click", "x": 960, "y": 540, "delay_ms": 200}
]
```
Ou se quiser inline com contador:
```json
[
  {"action": "set_var", "var_name": "i", "var_value": "0", "var_op": "set"},
  {"action": "click", "x": 960, "y": 540, "delay_ms": 200},
  {"action": "set_var", "var_name": "i", "var_value": "1", "var_op": "add"},
  {"action": "if", "cond_type": "var", "var_name": "i", "cond_op": ">=", "cond_value": "10"}
]
```"

[3] Skill check de jogo (espera cor + reage)
Usuario: "no Roblox aparece uma barra que precisa apertar espaco quando ela fica verde no centro"
Voce: "Use wait_pixel monitorando o pixel central — capture a cor exata com F10 no editor:
```json
[
  {"action": "wait_pixel", "x": 960, "y": 540, "color_rgb": [0, 255, 0], "color_tolerance": 30, "image_timeout_ms": 5000, "image_wait_for": "present"},
  {"action": "key_press", "key": "space"}
]
```
Configure rep_mode=infinite pra rodar continuamente."

[4] Notificacao Discord ao final de farm
Usuario: "manda mensagem no meu webhook do discord avisando que terminou"
Voce: "Use http_request — substitua a URL pelo seu webhook real:
```json
[
  {"action": "http_request", "http_url": "https://discord.com/api/webhooks/SEU_WEBHOOK_AQUI", "http_method": "POST", "http_body": "{\\"content\\": \\"Farm terminou!\\"}"}
]
```"

[5] IA chamando IA (resumir texto da tela)
Usuario: "le o texto da tela e me da um resumo via Ollama"
Voce: "Combine ocr_read + ai_prompt:
```json
[
  {"action": "ocr_read", "x": 100, "y": 100, "ocr_w": 800, "ocr_h": 600, "ocr_var": "texto"},
  {"action": "ai_prompt", "ai_backend": "ollama", "ai_model": "llama3.2", "ai_prompt_text": "Resuma em uma frase: {texto}", "var_name": "resumo"},
  {"action": "clipboard_set", "var_value": "{resumo}"}
]
```
O resumo fica no clipboard pra colar onde quiser."
"""


def _summarize_macro(steps: list) -> str:
    """Gera resumo compacto do macro atual pra mandar como contexto pra IA.

    Retorna formato 'N. action: detalhes' por linha. Pula campos default
    pra economizar tokens.
    """
    if not steps:
        return ""

    lines = []
    for i, s in enumerate(steps, 1):
        parts = [s.action]
        # Campos que vale a pena mostrar (só se preenchidos)
        if s.x is not None:
            parts.append(f"x={s.x}")
        if s.y is not None:
            parts.append(f"y={s.y}")
        if s.text:
            t = s.text[:40] + "..." if len(s.text) > 40 else s.text
            parts.append(f"text={t!r}")
        if s.key:
            parts.append(f"key={s.key}")
        if s.delay_ms:
            parts.append(f"delay={s.delay_ms}ms")
        if s.var_name:
            parts.append(f"var={s.var_name}")
        if s.image_data:
            parts.append("[template]")
        lines.append(f"{i}. {' '.join(parts)}")
    return "\n".join(lines)


def _build_context_message(macro_steps: list) -> str:
    """Constrói mensagem de system context sobre o macro carregado atualmente."""
    if not macro_steps:
        return ""
    summary = _summarize_macro(macro_steps)
    return (
        "CONTEXTO: O usuario tem este macro carregado no editor agora:\n\n"
        f"{summary}\n\n"
        "Se ele pedir pra 'modificar', 'adicionar', 'remover' ou 'mudar' algo, "
        "trabalhe com base nesse macro. Senao, ignore este contexto."
    )


class AIAssistant:
    """Sessão de chat com a IA. Histórico fica em memória até clear()."""

    def __init__(self) -> None:
        # Cada entry: {"role": "user"|"assistant", "content": "..."}
        self.history: list[dict] = []

    def _build_messages(self, user_message: str, current_macro: list | None) -> list[dict]:
        """Monta a lista de messages: system + contexto opcional + histórico + user."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        ctx = _build_context_message(current_macro or [])
        if ctx:
            messages.append({"role": "system", "content": ctx})
        messages.extend(self.history)
        messages.append({"role": "user", "content": user_message})
        return messages

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
        current_macro: list | None = None,
    ) -> tuple[bool, str]:
        """Versão não-streaming. Retorna (sucesso, resposta_ou_erro)."""
        messages = self._build_messages(user_message, current_macro)
        success, text = call_llm(
            backend=backend, model=model, messages=messages,
            api_key=api_key, base_url=base_url,
            timeout_s=timeout_s, temperature=temperature,
        )
        if success:
            self.history.append({"role": "user",      "content": user_message})
            self.history.append({"role": "assistant", "content": text})
        return success, text

    def chat_stream(
        self,
        user_message: str,
        *,
        backend: str = "ollama",
        model: str = "llama3.2",
        api_key: str = "",
        base_url: str = "",
        timeout_s: int = 120,
        temperature: float = 0.5,
        current_macro: list | None = None,
    ):
        """Generator que yields chunks de texto. Após completar, adiciona ao histórico.

        Em erro, levanta RuntimeError — histórico não é tocado.
        """
        messages = self._build_messages(user_message, current_macro)
        full_response = ""
        try:
            for chunk in call_llm_stream(
                backend=backend, model=model, messages=messages,
                api_key=api_key, base_url=base_url,
                timeout_s=timeout_s, temperature=temperature,
            ):
                full_response += chunk
                yield chunk
        except RuntimeError:
            # Erro durante streaming — não atualiza histórico, propaga
            raise

        # Streaming completou com sucesso — atualiza histórico
        self.history.append({"role": "user",      "content": user_message})
        self.history.append({"role": "assistant", "content": full_response})

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
