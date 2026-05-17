"""
build.py — Empacota AutoClick Pro num ZIP de release.

Uso:
    python build.py              # gera dist/AutoClickPro-vX.Y.Z.zip
    python build.py 1.2.0        # sobrescreve a versão pela linha de comando

O ZIP contém tudo que o instalar.bat precisa para o usuário final:
arquivos .py, assets, scripts de instalação, README e LICENSE.
Arquivos de cache, builds antigos e dados locais são excluídos.

Copyright (C) 2026 Carairritante — licenciado sob GNU AGPL v3.0.
"""
import os
import sys
import zipfile
from pathlib import Path

VERSION = "1.0.0"

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"

INCLUDE_FILES = [
    "AutoClickPro.py",
    "requirements.txt",
    "instalar.bat",
    "install_python.ps1",
    "install_tesseract.ps1",
    "README.md",
    "README.txt",
    "LICENSE",
]

INCLUDE_DIRS = ["core", "ui", "assets"]

EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".swp"}


def should_skip(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    if any(part in EXCLUDE_NAMES for part in path.parts):
        return True
    return False


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else VERSION
    zip_name = f"AutoClickPro-v{version}.zip"
    zip_path = DIST / zip_name

    DIST.mkdir(exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    print(f"Gerando {zip_name}...")
    file_count = 0
    total_bytes = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in INCLUDE_FILES:
            src = ROOT / name
            if not src.is_file():
                print(f"  AVISO: {name} nao encontrado, pulando")
                continue
            zf.write(src, arcname=name)
            file_count += 1
            total_bytes += src.stat().st_size

        for dirname in INCLUDE_DIRS:
            src_dir = ROOT / dirname
            if not src_dir.is_dir():
                print(f"  AVISO: {dirname}/ nao encontrado, pulando")
                continue
            for path in sorted(src_dir.rglob("*")):
                if not path.is_file() or should_skip(path):
                    continue
                arcname = path.relative_to(ROOT).as_posix()
                zf.write(path, arcname=arcname)
                file_count += 1
                total_bytes += path.stat().st_size

    final_size = zip_path.stat().st_size
    ratio = (1 - final_size / total_bytes) * 100 if total_bytes else 0

    print(f"  {file_count} arquivos, {total_bytes / 1024:.1f} KB originais")
    print(f"  ZIP final: {final_size / 1024:.1f} KB ({ratio:.1f}% compactado)")
    print(f"\nPronto: {zip_path}")
    print("\nProximos passos para release no GitHub:")
    print(f"  1. git tag -a v{version} -m 'Release v{version}'")
    print(f"  2. git push origin v{version}")
    print(f"  3. Acesse https://github.com/Carairritante/Autoclick-PRO/releases/new")
    print(f"     escolha a tag v{version} e anexe o arquivo: {zip_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
