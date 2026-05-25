"""Multi-Roblox: permite abrir multiplas instancias do Roblox no mesmo PC.

Roblox usa um mutex Windows chamado "ROBLOX_singletonEvent" pra impedir
multiplas instancias. Se um terceiro processo (este aqui) criar e segurar
esse mutex ANTES do Roblox abrir, o Roblox abre normalmente mas nao
consegue mais aplicar a regra de "instancia unica" — todas as instancias
extras coexistem.

Convencao:
  - O handle do mutex e armazenado em modulo (singleton)
  - enable() e idempotente: chamar 2x nao quebra
  - Mutex e liberado em disable() ou ao fechar o app (cleanup atexit)
  - Plataforma: Windows-only. Em outros OS, funcoes viram no-op com aviso.

Nao requer admin. Nao toca arquivos. Nao mata processos.
"""
from __future__ import annotations

import sys
import atexit

_ROBLOX_MUTEX_NAME = "ROBLOX_singletonEvent"
_mutex_handle: int | None = None   # handle Windows quando ativo
_kernel32 = None                    # ref pra ctypes.windll.kernel32

# Try import ctypes; falha graciosa em plataformas nao-Windows
try:
    import ctypes  # noqa: F401
    if sys.platform == "win32":
        _kernel32 = ctypes.windll.kernel32
        # Tipagens de retorno pra detectar erros corretamente
        _kernel32.CreateMutexW.restype = ctypes.c_void_p
        _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        _kernel32.CloseHandle.restype = ctypes.c_int
        _kernel32.GetLastError.restype = ctypes.c_ulong
except Exception:
    _kernel32 = None


def is_supported() -> bool:
    """Retorna True se plataforma suporta (Windows com ctypes)."""
    return _kernel32 is not None


def is_enabled() -> bool:
    """Retorna True se o mutex esta ativo (ja chamou enable)."""
    return _mutex_handle is not None


def enable() -> bool:
    """Cria o mutex se ainda nao existe. Idempotente. Retorna True se ativo."""
    global _mutex_handle
    if _mutex_handle is not None:
        return True   # ja ativo
    if not is_supported():
        return False
    try:
        # bInitialOwner=True garante que SOMOS o dono inicial — outras
        # tentativas de OpenMutex serao bem-sucedidas mas nao adquirem a posse.
        handle = _kernel32.CreateMutexW(None, True, _ROBLOX_MUTEX_NAME)
        if not handle:
            return False
        _mutex_handle = handle
        return True
    except Exception:
        return False


def disable() -> bool:
    """Libera o mutex se ativo. Idempotente. Retorna True se liberou ou ja inativo."""
    global _mutex_handle
    if _mutex_handle is None:
        return True
    if not is_supported():
        _mutex_handle = None
        return False
    try:
        _kernel32.CloseHandle(_mutex_handle)
    except Exception:
        pass
    _mutex_handle = None
    return True


# Cleanup automatico ao fechar o processo (protecao extra alem do disable manual)
atexit.register(disable)
