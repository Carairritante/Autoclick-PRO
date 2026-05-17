"""Constantes de caminho compartilhadas entre core/ e ui/.

Centraliza PROJECT_ROOT e subpastas para evitar import circular entre
core/engine.py (que precisa de PROFILES_DIR para call_macro) e ui/app.py
(que define _ROOT historicamente).
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(PROJECT_ROOT, "profiles")
NTFY_CONFIG_PATH = os.path.join(PROFILES_DIR, "ntfy.json")
HOTSTRINGS_PATH  = os.path.join(PROFILES_DIR, "hotstrings.json")
