"""
core/ai_client.py — Cliente compartilhado para LLMs (Ollama, OpenAI-compatível).

Usado tanto pelo step `ai_prompt` (core/engine.py) quanto pelo painel
🤖 IA Assistente (ui/tabs/ai_assistant.py). Centraliza:
  - Roteamento por backend (ollama / openai / openrouter / groq / custom)
  - Tratamento de erros (timeout, conexão, HTTP, parse) com mensagens claras
  - Suporte a streaming (call_llm_stream) e vision (parâmetro images)
  - Listagem de modelos Ollama instalados (list_ollama_models)
"""
from __future__ import annotations

import json


# URLs padrão por backend (OpenAI-compatíveis usam /chat/completions)
DEFAULT_BASE_URLS = {
    "openai":     "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq":       "https://api.groq.com/openai/v1",
}

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _build_request(
    backend: str,
    model: str,
    messages: list[dict],
    *,
    api_key: str = "",
    base_url: str = "",
    temperature: float = 0.7,
    images: list[str] | None = None,
    stream: bool = False,
) -> tuple[str, dict, dict | None] | tuple[None, None, str]:
    """Monta (url, body, headers) ou retorna (None, None, erro) se config inválida.

    Se `images` for fornecido (lista de PNG base64), anexa à última mensagem 'user'
    no formato específico do backend (Ollama: campo 'images'; OpenAI: content array).
    """
    backend = backend or "ollama"

    # Anexa imagens à última mensagem 'user' se aplicável
    if images and messages and messages[-1].get("role") == "user":
        last = messages[-1]
        if backend == "ollama":
            messages = messages[:-1] + [{
                "role": "user",
                "content": last["content"],
                "images": images,
            }]
        else:
            content = [{"type": "text", "text": last["content"]}]
            for b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
            messages = messages[:-1] + [{"role": "user", "content": content}]

    if backend == "ollama":
        url  = (base_url or DEFAULT_OLLAMA_URL).rstrip("/") + "/api/chat"
        body = {"model": model, "messages": messages, "stream": stream}
        hdrs = None
        return url, body, hdrs

    key = (api_key or "").strip()
    if not key:
        return None, None, f"API key vazia para backend '{backend}'"
    base = (base_url or DEFAULT_BASE_URLS.get(
        backend, "https://api.openai.com/v1")).rstrip("/")
    url  = f"{base}/chat/completions"
    body = {"model": model, "messages": messages,
            "temperature": temperature, "stream": stream}
    hdrs = {"Authorization": f"Bearer {key}",
            "Content-Type": "application/json"}
    return url, body, hdrs


def call_llm(
    backend: str,
    model: str,
    messages: list[dict],
    *,
    api_key: str = "",
    base_url: str = "",
    timeout_s: int = 30,
    temperature: float = 0.7,
    images: list[str] | None = None,
) -> tuple[bool, str]:
    """Chama LLM (síncrono, sem streaming) e retorna (sucesso, texto_ou_erro).

    images: lista de PNG base64 pra ativar vision. Anexa à última mensagem user.

    Retorna:
      (True, resposta)        em sucesso
      (False, "[ERRO: ...]")  em falha — mensagem distingue causa
                              (timeout, conexão, HTTP, parse, key vazia)
    """
    try:
        import requests as _req
    except ImportError:
        return False, "[ERRO: biblioteca 'requests' nao instalada]"

    timeout = max(5, timeout_s or 30)

    result = _build_request(backend, model, messages,
                             api_key=api_key, base_url=base_url,
                             temperature=temperature, images=images, stream=False)
    if result[0] is None:
        return False, f"[ERRO: {result[2]}]"
    url, body, hdrs = result

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

    try:
        data = r.json()
        if (backend or "ollama") == "ollama":
            return True, data["message"]["content"]
        return True, data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        preview = (r.text or "")[:120].replace("\n", " ")
        return False, f"[ERRO: resposta inesperada ({exc.__class__.__name__}): {preview}]"


def call_llm_stream(
    backend: str,
    model: str,
    messages: list[dict],
    *,
    api_key: str = "",
    base_url: str = "",
    timeout_s: int = 120,
    temperature: float = 0.7,
    images: list[str] | None = None,
):
    """Generator que yields chunks de texto conforme chegam do LLM.

    Ollama: parsea NDJSON (uma linha por chunk).
    OpenAI-compatível: parsea SSE (linhas 'data: {...}').

    Em erro de rede/HTTP, levanta RuntimeError com mensagem clara.
    Em erro de parse de chunk individual, ignora silenciosamente (resiliente).
    """
    try:
        import requests as _req
    except ImportError:
        raise RuntimeError("biblioteca 'requests' nao instalada")

    timeout = max(5, timeout_s or 30)
    backend = backend or "ollama"

    result = _build_request(backend, model, messages,
                             api_key=api_key, base_url=base_url,
                             temperature=temperature, images=images, stream=True)
    if result[0] is None:
        raise RuntimeError(result[2])
    url, body, hdrs = result

    try:
        r = _req.post(url, json=body, headers=hdrs, timeout=timeout, stream=True)
    except _req.Timeout:
        raise RuntimeError(f"timeout apos {timeout}s")
    except _req.ConnectionError as exc:
        raise RuntimeError(f"conexao falhou ({exc.__class__.__name__})")
    except Exception as exc:
        raise RuntimeError(f"rede: {exc}")

    with r:
        if r.status_code >= 400:
            preview = (r.text or "")[:120].replace("\n", " ")
            raise RuntimeError(f"HTTP {r.status_code}: {preview}")

        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line:
                continue

            if backend == "ollama":
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                msg = obj.get("message") or {}
                chunk = msg.get("content", "")
                if chunk:
                    yield chunk
                if obj.get("done"):
                    return
            else:
                if not raw_line.startswith("data: "):
                    continue
                data_str = raw_line[6:].strip()
                if data_str == "[DONE]":
                    return
                try:
                    obj = json.loads(data_str)
                    delta = obj["choices"][0]["delta"]
                    chunk = delta.get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if chunk:
                    yield chunk


def list_ollama_models(base_url: str = "") -> list[str]:
    """Retorna lista de modelos Ollama instalados (via GET /api/tags).

    Retorna lista vazia se Ollama offline ou erro — chamador trata.
    Timeout curto (3s) pra não travar UI.
    """
    try:
        import requests as _req
        url = (base_url or DEFAULT_OLLAMA_URL).rstrip("/") + "/api/tags"
        r = _req.get(url, timeout=3)
        r.raise_for_status()
        data = r.json()
        models = data.get("models") or []
        return [m["name"] for m in models if isinstance(m, dict) and "name" in m]
    except Exception:
        return []
