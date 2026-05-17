@echo off
setlocal enabledelayedexpansion
title AutoClick Pro - Instalador

set "INSTALL_DIR=%LOCALAPPDATA%\AutoClickPro"

echo.
echo  +--------------------------------------+
echo  ^|    Instalador do AutoClick Pro      ^|
echo  +--------------------------------------+
echo.
echo  Destino: %INSTALL_DIR%
echo.

:: 1. Localizar Python (ou instalar automaticamente se faltar)
echo  [1/5] Verificando Python...
set "PYTHON_CMD="

python -c "exit()" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=python"
    goto :found_python
)

py -c "exit()" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=py"
    goto :found_python
)

:: Verifica caminho padrão per-user (caso já tenha sido instalado mas PATH não atualizou)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :found_python
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found_python
)

:: Python não encontrado — tentar baixar e instalar automaticamente
echo  Python nao encontrado. Iniciando instalacao automatica...
if not exist "%~dp0install_python.ps1" (
    echo.
    echo  ERRO: install_python.ps1 nao encontrado no pacote.
    echo  Instale Python 3.10+ manualmente: https://python.org
    echo  IMPORTANTE: marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_python.ps1"
set "_PSEXIT=!errorlevel!"

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :found_python
)

echo.
echo  ERRO: Instalacao automatica do Python falhou ^(codigo !_PSEXIT!^).
echo  Possiveis causas:
echo    - Sem conexao com a internet
echo    - Antivirus bloqueando o download
echo    - Politica de execucao do PowerShell restrita
echo.
echo  Instale manualmente em: https://python.org
echo  IMPORTANTE: marque "Add Python to PATH" durante a instalacao.
echo.
pause
exit /b 1

:found_python
for /f "delims=" %%V in ('"!PYTHON_CMD!" --version 2^>^&1') do echo         OK - %%V

:: Detectar instalacao anterior — preserva profiles\ sempre, limpa o resto
set "_IS_UPGRADE="
if exist "%INSTALL_DIR%\AutoClickPro.py" set "_IS_UPGRADE=1"
if exist "%INSTALL_DIR%\core\driver.py"  set "_IS_UPGRADE=1"

if not defined _IS_UPGRADE goto :no_upgrade
echo.
echo  Versao anterior detectada em %INSTALL_DIR%
echo  Os perfis ^(profiles\^) serao preservados.
echo.
set /p "_CONF=Atualizar? [S/N]: "
if /i not "!_CONF!"=="S" (
    echo  Instalacao cancelada pelo usuario.
    pause
    exit /b 0
)
call :clean_old_install
:no_upgrade

:: 2. Copiar arquivos
if defined _IS_UPGRADE (
    echo  [2/5] Instalando arquivos novos em %INSTALL_DIR%...
) else (
    echo  [2/5] Copiando arquivos para %INSTALL_DIR%...
)
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

xcopy /e /i /y /q "%~dp0core" "%INSTALL_DIR%\core\" >nul 2>&1
if !errorlevel! neq 0 echo  AVISO: falha ao copiar core/

xcopy /e /i /y /q "%~dp0ui" "%INSTALL_DIR%\ui\" >nul 2>&1
if !errorlevel! neq 0 echo  AVISO: falha ao copiar ui/

if exist "%~dp0assets" (
    xcopy /e /i /y /q "%~dp0assets" "%INSTALL_DIR%\assets\" >nul 2>&1
) else (
    mkdir "%INSTALL_DIR%\assets" >nul 2>&1
)

copy /y "%~dp0AutoClickPro.py" "%INSTALL_DIR%\" >nul 2>&1
copy /y "%~dp0requirements.txt" "%INSTALL_DIR%\" >nul 2>&1
if exist "%~dp0README.txt" copy /y "%~dp0README.txt" "%INSTALL_DIR%\" >nul 2>&1
echo         OK

:: Gerar desinstalador
(
  echo @echo off
  echo echo Desinstalando AutoClick Pro...
  echo rmdir /s /q "%INSTALL_DIR%"
  echo :: Atalhos: Area de Trabalho ^(local + OneDrive sync^)
  echo del /f /q "%USERPROFILE%\Desktop\AutoClick Pro.lnk" 2^>nul
  echo del /f /q "%USERPROFILE%\OneDrive\Desktop\AutoClick Pro.lnk" 2^>nul
  echo :: Atalho: Menu Iniciar
  echo del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\AutoClick Pro.lnk" 2^>nul
  echo :: Atalho: Barra de tarefas ^(pinned^)
  echo del /f /q "%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\AutoClick Pro.lnk" 2^>nul
  echo :: Atalho: Quick Launch legacy
  echo del /f /q "%APPDATA%\Microsoft\Internet Explorer\Quick Launch\AutoClick Pro.lnk" 2^>nul
  echo echo Desinstalacao concluida.
  echo pause
) > "%INSTALL_DIR%\desinstalar.bat"

:: 3. Instalar dependencias
echo  [3/5] Instalando dependencias Python...
set "_PIP_FAILED="
"!PYTHON_CMD!" -m pip install -r "%INSTALL_DIR%\requirements.txt" -q --disable-pip-version-check
if !errorlevel! neq 0 (
    set "_PIP_FAILED=1"
    echo.
    echo  AVISO: Falha ao instalar dependencias.
    echo  Possiveis causas: sem internet, antivirus bloqueando ou PyPI indisponivel.
    echo  Tente novamente apos resolver, ou rode manualmente:
    echo    "!PYTHON_CMD!" -m pip install -r "%INSTALL_DIR%\requirements.txt"
    echo.
) else (
    echo         OK
)

:: 3b. Verificar/Instalar Tesseract OCR (feature de OCR no macro)
echo  [3b/5] Verificando Tesseract OCR...
set "TESSERACT_FOUND="
where tesseract >nul 2>&1
if !errorlevel! equ 0 set "TESSERACT_FOUND=1"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESSERACT_FOUND=1"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESSERACT_FOUND=1"

if defined TESSERACT_FOUND (
    echo         OK ^(ja instalado^)
) else (
    if exist "%~dp0install_tesseract.ps1" (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_tesseract.ps1"
        if !errorlevel! equ 0 (
            echo         OK ^(Tesseract instalado^)
        ) else (
            echo.
            echo  AVISO: Tesseract nao foi instalado automaticamente.
            echo  OCR no macro nao funcionara ate instalar manualmente:
            echo  https://github.com/UB-Mannheim/tesseract/wiki
            echo.
        )
    ) else (
        echo         AVISO: install_tesseract.ps1 nao encontrado, pulando.
    )
)

:: 4. Gerar icone (apenas se nao existir um customizado em assets/)
echo  [4/5] Verificando icone...
if exist "%INSTALL_DIR%\assets\icon.ico" (
    echo         OK ^(usando icone existente^)
) else (
    "!PYTHON_CMD!" -c "import sys; sys.path.insert(0, r'%INSTALL_DIR%'); from core.icon_gen import generate_icon_ico; generate_icon_ico(r'%INSTALL_DIR%\assets\icon.ico')" >nul 2>&1
    echo         OK ^(gerado programaticamente^)
)

:: Localizar pythonw.exe (versao sem console — usado pelos atalhos)
set "PYTHONW="

:: Estrategia 1: derivar do PYTHON_CMD se for caminho absoluto
echo !PYTHON_CMD! | findstr /c:".exe" >nul
if !errorlevel! equ 0 (
    set "_TRY=!PYTHON_CMD:python.exe=pythonw.exe!"
    if exist "!_TRY!" set "PYTHONW=!_TRY!"
)

:: Estrategia 2: where pythonw no PATH
if not defined PYTHONW (
    for /f "delims=" %%P in ('where pythonw 2^>nul') do (
        if not defined PYTHONW set "PYTHONW=%%P"
    )
)

:: Estrategia 3: derivar de where python
if not defined PYTHONW (
    set "_PY="
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined _PY set "_PY=%%P"
    )
    if defined _PY (
        set "PYTHONW=!_PY:python.exe=pythonw.exe!"
        if not exist "!PYTHONW!" set "PYTHONW=!_PY!"
    )
)

:: Estrategia 4: caminho per-user padrao (Python recem-instalado, PATH ainda nao refrescou)
if not defined PYTHONW (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
        set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
        set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    )
)

:: Fallback final
if not defined PYTHONW set "PYTHONW=pythonw"

:: 5. Criar atalhos via VBScript
echo  [5/5] Criando atalhos...

set "ICON_PATH=%INSTALL_DIR%\assets\icon.ico"
set "TMPVBS=%TEMP%\autoclick_setup.vbs"

(
  echo Set WS = CreateObject^("WScript.Shell"^)
  echo desktop = WS.SpecialFolders^("Desktop"^)
  echo programs = WS.SpecialFolders^("Programs"^)
  echo Set S = WS.CreateShortcut^(desktop ^& "\AutoClick Pro.lnk"^)
  echo S.TargetPath = "%PYTHONW%"
  echo S.Arguments = Chr^(34^) ^& "%INSTALL_DIR%\AutoClickPro.py" ^& Chr^(34^)
  echo S.WorkingDirectory = "%INSTALL_DIR%"
  echo S.IconLocation = "%ICON_PATH%"
  echo S.Description = "AutoClick Pro"
  echo S.Save
  echo Set S = WS.CreateShortcut^(programs ^& "\AutoClick Pro.lnk"^)
  echo S.TargetPath = "%PYTHONW%"
  echo S.Arguments = Chr^(34^) ^& "%INSTALL_DIR%\AutoClickPro.py" ^& Chr^(34^)
  echo S.WorkingDirectory = "%INSTALL_DIR%"
  echo S.IconLocation = "%ICON_PATH%"
  echo S.Description = "AutoClick Pro"
  echo S.Save
) > "%TMPVBS%"

cscript //nologo "%TMPVBS%"
del /f /q "%TMPVBS%" >nul 2>&1
echo         OK

echo.
if defined _IS_UPGRADE (
    echo  +--------------------------------------+
    echo  ^|       Atualizacao concluida!        ^|
    echo  +--------------------------------------+
) else (
    echo  +--------------------------------------+
    echo  ^|       Instalacao concluida!         ^|
    echo  +--------------------------------------+
)
echo.

if defined _PIP_FAILED (
    echo  ATENCAO: dependencias Python NAO foram instaladas com sucesso.
    echo  O app pode nao abrir ate isso ser resolvido.
    echo  Veja a mensagem de erro acima ^(pode ser sem internet/antivirus^).
    echo.
)

echo   - Atalho criado na Area de Trabalho
echo   - Atalho criado no Menu Iniciar
echo.
echo  Para fixar na barra de tarefas:
echo    Clique com botao direito no icone da Area de Trabalho
echo    e escolha "Fixar na barra de tarefas"
echo.
echo  Para desinstalar:
echo    Execute: %INSTALL_DIR%\desinstalar.bat
echo.
pause
exit /b 0

:: ==============================================================
:: Subrotina: limpa instalacao anterior, preservando profiles\
:: ==============================================================
:clean_old_install
echo  Limpando versao anterior ^(preservando profiles\^)...
:: Pastas de codigo — regeneradas pela copia
if exist "%INSTALL_DIR%\core"          rmdir /s /q "%INSTALL_DIR%\core"
if exist "%INSTALL_DIR%\ui"            rmdir /s /q "%INSTALL_DIR%\ui"
if exist "%INSTALL_DIR%\assets"        rmdir /s /q "%INSTALL_DIR%\assets"
if exist "%INSTALL_DIR%\__pycache__"   rmdir /s /q "%INSTALL_DIR%\__pycache__"
:: Arquivos soltos — regenerados pela copia
del /f /q "%INSTALL_DIR%\AutoClickPro.py"   2>nul
del /f /q "%INSTALL_DIR%\requirements.txt"  2>nul
del /f /q "%INSTALL_DIR%\README.txt"        2>nul
del /f /q "%INSTALL_DIR%\desinstalar.bat"   2>nul
:: Atalhos antigos — recriados no passo [5/5]
del /f /q "%USERPROFILE%\Desktop\AutoClick Pro.lnk"                                 2>nul
del /f /q "%USERPROFILE%\OneDrive\Desktop\AutoClick Pro.lnk"                        2>nul
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\AutoClick Pro.lnk"       2>nul
echo         OK
exit /b 0
