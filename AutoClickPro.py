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

from ui.app import AutoClickPro

if __name__ == "__main__":
    _log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
    try:
        app = AutoClickPro()
        app.mainloop()
    except Exception:
        with open(_log, "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
