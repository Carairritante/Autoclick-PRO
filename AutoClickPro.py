"""
AutoClickPro.py — Ponto de entrada (alias para ui/app.py).

Execute: python AutoClickPro.py
Build:   python build.py
"""
import os
import sys
import traceback

# Garante que o diretório do projeto está no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _acquire_single_instance_lock():
    """Cria mutex nomeado do Windows. Retorna o handle (deve ficar vivo).

    Se o mutex já existir (outra instância rodando), traz a janela existente
    pra frente e encerra. Usa namespace 'Local\\' (per-session) — não exige
    privilégio admin que 'Global\\' exigiria.
    """
    import ctypes
    import ctypes.wintypes as wt

    _MUTEX_NAME = "Local\\AutoClickPro_SingleInstance"
    _ERROR_ALREADY_EXISTS = 183

    kernel32 = ctypes.windll.kernel32
    # bInitialOwner=False: só queremos checar existência, não posse
    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    last_err = kernel32.GetLastError()

    # Handle NULL = falha de criação (sem permissão, OOM, etc.). Sem mutex,
    # não dá pra garantir instância única — segue sem bloquear.
    if not handle:
        return None

    if last_err != _ERROR_ALREADY_EXISTS:
        return handle  # nova instância — manter referência viva

    # ── Mutex já existe: outra instância está aberta ─────────────────────
    user32 = ctypes.windll.user32
    found = wt.HWND(0)

    # Mantém referência viva da callback durante o EnumWindows (evita GC)
    _ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def _enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        if buf.value.startswith("AutoClick Pro"):
            found.value = hwnd
            return False
        return True

    _cb_ref = _ENUM_PROC(_enum_cb)
    user32.EnumWindows(_cb_ref, 0)

    if found.value:
        user32.ShowWindow(found.value, 9)        # SW_RESTORE
        user32.SetForegroundWindow(found.value)
    else:
        import tkinter as tk
        from tkinter import messagebox
        _r = tk.Tk(); _r.withdraw()
        messagebox.showwarning(
            "AutoClick Pro já aberto",
            "Uma instância do AutoClick Pro já está em execução.\n"
            "Feche a versão atual antes de abrir outra.",
        )
        _r.destroy()

    kernel32.CloseHandle(handle)
    sys.exit(0)


if __name__ == "__main__":
    _mutex = _acquire_single_instance_lock()

    _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
    try:
        from ui.app import AutoClickPro
        app = AutoClickPro()
        app.mainloop()
    except Exception:
        with open(_log, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
