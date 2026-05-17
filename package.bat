@echo off
setlocal enableextensions

REM Sempre trabalha no diretorio do .bat (mesmo se chamado de outro lugar)
cd /d "%~dp0"

echo Gerando pacote AutoClickPro.zip...

REM Pasta temporaria para montar o zip
set "TMPDIR=%TEMP%\autoclick_pkg"
if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%"
mkdir "%TMPDIR%\AutoClickPro"

REM Copiar pastas
xcopy /e /i /y /q "core"   "%TMPDIR%\AutoClickPro\core\" >nul
xcopy /e /i /y /q "ui"     "%TMPDIR%\AutoClickPro\ui\" >nul
if exist "assets" xcopy /e /i /y /q "assets" "%TMPDIR%\AutoClickPro\assets\" >nul

REM Copiar arquivos soltos
copy /y "AutoClickPro.py"        "%TMPDIR%\AutoClickPro\" >nul
copy /y "requirements.txt"       "%TMPDIR%\AutoClickPro\" >nul
copy /y "instalar.bat"           "%TMPDIR%\AutoClickPro\" >nul
copy /y "install_python.ps1"     "%TMPDIR%\AutoClickPro\" >nul
copy /y "install_tesseract.ps1"  "%TMPDIR%\AutoClickPro\" >nul
copy /y "README.txt"             "%TMPDIR%\AutoClickPro\" >nul

REM Remover __pycache__ recursivamente (regenerado em runtime)
for /d /r "%TMPDIR%\AutoClickPro" %%D in (__pycache__) do (
    if exist "%%D" rmdir /s /q "%%D"
)

REM Gerar zip via PowerShell (Compress-Archive)
if exist "AutoClickPro.zip" del /f /q "AutoClickPro.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%TMPDIR%\AutoClickPro' -DestinationPath '%~dp0AutoClickPro.zip' -CompressionLevel Optimal -Force"

REM Limpar pasta temporaria
rmdir /s /q "%TMPDIR%" 2>nul

echo.
if exist "AutoClickPro.zip" (
    echo  OK! AutoClickPro.zip gerado.
    echo  Envie este .zip para outros usuarios.
) else (
    echo  ERRO: nao foi possivel gerar AutoClickPro.zip
)
echo.
pause
endlocal
