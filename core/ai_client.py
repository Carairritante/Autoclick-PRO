"""
core/ai_client.py — Cliente compartilhado para LLMs (Ollama, OpenAI-compatível).

Usado tanto pelo step `ai_prompt` (core/engine.py) quanto pelo painel
🤖 IA Assistente (ui/tabs/ai_assistant.py). Centraliza:
  - Roteamento por backend (ollama / openai / openrouter / groq / custom)
  - Tratamento de erros (timeout, conexão, HTTP, parse) com mensagens claras
  - Formato uniforme de retorno: (success, text_or_error)
"""
from __future__ import annotations


# URLs padrão por backend (OpenAI-compatíveis usam /chat/completions)
DEFAULT_BASE_URLS = {
    "openai":     "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq":       "https://api.groq.com/openai/v1",
}

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def call_llm(
    backend: str,
    model: str,
    messages: list[dict],
    *,
    api_key: str = "",
    base_url: str = "",
    timeout_s: int = 30,
    temperature: float = 0.7,
) -> tuple[bool, str]:
    """Chama uma LLM e retorna (sucesso, texto_ou_erro).

    backend: "ollama" | "openai" | "openrouter" | "groq" | "custom"
    messages: lista no formato OpenAI [{"role": "system", "content": "..."}, ...]

    Retorna:
      (True, resposta)        em sucesso
      (False, "[ERRO: ...]")  em falha — mensagem distingue causa
                              (timeout, conexão, HTTP, parse, key vazia)
    """
    try:
        import requests as _req
    except ImportError:
        return False, "[ERRO: biblioteca 'requests' nao instalada]"

    backend = backend or "ollama"
    timeout = max(5, timeout_s or 30)

    # ── Monta URL/body/headers conforme backend ──────────────────────
    if backend == "ollama":
        url  = (base_url or DEFAULT_OLLAMA_URL).rstrip("/") + "/api/chat"
        body = {"model": model, "messages": messages, "stream": False}
        hdrs = None
    else:
        key = (api_key or "").strip()
        if not key:
            return False, f"[ERRO: API key vazia para backend '{backend}']"
        base = (base_url or DEFAULT_BASE_URLS.get(
            backend, "https://api.openai.com/v1")).rstrip("/")
        url  = f"{base}/chat/completions"
        body = {"model": model, "messages": messages,
                "temperature": temperature}
        hdrs = {"Authorization": f"Bearer {key}",
                "Content-Type": "application/json"}

    # ── HTTP request, separando erros de rede ────────────────────────
    try:
        r = _req.post(url, json=body, headers=hdrs, timeout=timeout)
    except _req.Timeout:
        return False, f"[ERRO: timeout apos {timeout}s]"
    except _req.ConnectionError as exc:
        return False, f"[ERRO: conexao falhou ({exc.__class__.__name__})]"
    except Exception as exc:
        return False, f"[ERRO: rede: {exc}]"

    if r.status_code >= 400:
        preview = (r.text or "")[:120].replace("\n", " ")
        return False, f"[ERRO: HTTP {r.status_code}: {preview}]"

    # ── Extrai resposta do JSON conforme backend ────────────────────
    try:
        data = r.json()
        if backend == "ollama":
            return True, data["message"]["content"]
        return True, data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        preview = (r.text or "")[:120].replace("\n", " ")
        return False, f"[ERRO: resposta inesperada ({exc.__class__.__name__}): {preview}]"
