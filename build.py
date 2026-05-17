"""
build.py — Gera autoclick_pro.exe standalone via Nuitka.

Uso:  python build.py
Saída: dist/autoclick_pro.exe  (~50-80 MB, tudo embutido)

Requisitos: pip install nuitka  (incluído em requirements.txt)
Nota SmartScreen: na primeira execução em outro PC, Windows pode pedir confirmação.
  Clique em "Mais informações" → "Executar mesmo assim".
"""
import subprocess
import sys
import os


def _ensure_icon() -> str | None:
    """Garante que assets/icon.ico existe. Retorna o caminho ou None."""
    root = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(root, "assets", "icon.ico")
    if os.path.exists(icon_path):
        return icon_path
    sys.path.insert(0, root)
    try:
        from core.icon_gen import generate_icon_ico
        if generate_icon_ico(icon_path):
            print(f"Ícone gerado em {icon_path}")
            return icon_path
    except Exception as e:
        print(f"Aviso: não foi possível gerar o ícone ({e}). Build continuará sem ícone.")
    return None


def _check_nuitka() -> bool:
    """Verifica se Nuitka está instalado."""
    result = subprocess.run(
        [sys.executable, "-m", "nuitka", "--version"],
        capture_output=True,
    )
    if result.returncode != 0:
        print("❌ Nuitka não encontrado. Execute: pip install nuitka")
        return False
    return True


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))

    if not _check_nuitka():
        sys.exit(1)

    icon = _ensure_icon()

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--windows-console-mode=disable",
        "--include-package=core",
        "--include-package=ui",
        "--include-package=keyboard",
        "--include-package=pyautogui",
        "--include-package=pynput",
        "--include-data-dir=assets=assets",
        "--output-dir=dist",
        "--output-filename=autoclick_pro",
    ]

    if icon:
        cmd.append(f"--windows-icon-from-ico={icon}")

    cmd.append("ui/app.py")

    print("Iniciando build com Nuitka...")
    print(" ".join(cmd))
    print()
    result = subprocess.run(cmd, cwd=root)
    if result.returncode == 0:
        print("\n✅ Build concluído! Executável em: dist/autoclick_pro.exe")
    else:
        print(f"\n❌ Build falhou com código {result.returncode}.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
