"""Variaveis persistentes entre execucoes de macro.

Convencao: qualquer variavel cujo nome comeca com '$' (ex: $kills, $money)
e gravada em disco a cada atualizacao e recarregada no inicio da proxima run.

Storage: profiles/persistent_vars.json — flat dict {nome: valor}.

Uso no engine:
  - MacroContext carrega via `load_all()` em __init__
  - Engine chama `save_one(name, value)` apos cada update de var que comeca com '$'

Falhas de IO sao silenciosas (return defaults) — persistir nunca pode
quebrar a execucao do macro.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from core.paths import PERSISTENT_VARS_PATH, PROFILES_DIR

# Lock de processo unico — protege escritas concorrentes se um dia rodar
# mais de um macro ao mesmo tempo.
_LOCK = threading.Lock()


def is_persistent_name(name: str) -> bool:
    """Retorna True se o nome da variavel comeca com '$' (e portanto persiste)."""
    return bool(name) and name.startswith("$")


def load_all() -> dict[str, Any]:
    """Carrega todas as variaveis persistentes do disco. Falha = dict vazio."""
    try:
        if not os.path.exists(PERSISTENT_VARS_PATH):
            return {}
        with open(PERSISTENT_VARS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def save_all(data: dict[str, Any]) -> bool:
    """Grava o dict inteiro no disco. Retorna True se sucesso."""
    try:
        os.makedirs(PROFILES_DIR, exist_ok=True)
        with _LOCK:
            with open(PERSISTENT_VARS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def save_one(name: str, value: Any) -> bool:
    """Atualiza uma unica variavel no arquivo, preservando as demais."""
    if not is_persistent_name(name):
        return False
    with _LOCK:
        try:
            data = {}
            if os.path.exists(PERSISTENT_VARS_PATH):
                with open(PERSISTENT_VARS_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            data[name] = value
            os.makedirs(PROFILES_DIR, exist_ok=True)
            with open(PERSISTENT_VARS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


def delete_one(name: str) -> bool:
    """Remove uma variavel do arquivo. Retorna True se removeu."""
    with _LOCK:
        try:
            if not os.path.exists(PERSISTENT_VARS_PATH):
                return False
            with open(PERSISTENT_VARS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or name not in data:
                return False
            del data[name]
            with open(PERSISTENT_VARS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
