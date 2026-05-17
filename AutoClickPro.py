"""
AutoClickPro.py — Ponto de entrada (alias para ui/app.py).

Execute: python AutoClickPro.py
Build:   python build.py

Copyright (C) 2026 Carairritante
Este programa é software livre: você pode redistribuí-lo e/ou modificá-lo
sob os termos da GNU Affero General Public License, versão 3, conforme
publicada pela Free Software Foundation. Veja o arquivo LICENSE.
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
