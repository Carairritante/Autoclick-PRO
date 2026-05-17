# install_python.ps1
# Baixa e instala o Python 3.13.13 (per-user, sem admin).
# Chamado por instalar.bat quando Python não está presente.
#
# Exit codes:
#   0 = sucesso (python.exe encontrado no caminho esperado)
#   1 = falha de download
#   2 = instalador falhou ou python.exe não apareceu

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

# Versão pinada — atualize aqui pra uma mais nova quando quiser
$VERSION = "3.13.13"
$URL     = "https://www.python.org/ftp/python/$VERSION/python-$VERSION-amd64.exe"
$OUT     = Join-Path $env:TEMP "python-installer.exe"

# Caminho onde o instalador per-user vai colocar o python.exe
$EXPECTED = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"

# Se já existe no caminho esperado, não baixa de novo
if (Test-Path $EXPECTED) {
    Write-Host "         Python ja instalado em $EXPECTED"
    exit 0
}

Write-Host "         Baixando Python $VERSION (~30MB)..."

try {
    Invoke-WebRequest -Uri $URL -OutFile $OUT -UseBasicParsing -TimeoutSec 300
} catch {
    Write-Host "         ERRO de download: $($_.Exception.Message)"
    exit 1
}

if (-not (Test-Path $OUT)) {
    Write-Host "         ERRO: arquivo baixado nao encontrado"
    exit 1
}

Write-Host "         Download OK. Instalando silenciosamente (sem UAC)..."
Write-Host "         (pode levar 1-2 minutos, sem feedback visual)"

# Args do installer Python (per-user, silent, com pip + PATH):
#   /quiet              → sem UI
#   InstallAllUsers=0   → per-user (sem admin)
#   PrependPath=1       → adiciona ao PATH
#   Include_test=0      → não inclui suite de testes
#   Include_pip=1       → inclui pip
$args = @(
    "/quiet",
    "InstallAllUsers=0",
    "PrependPath=1",
    "Include_test=0",
    "Include_pip=1"
)

try {
    $proc = Start-Process -FilePath $OUT -ArgumentList $args -Wait -PassThru
    Remove-Item $OUT -Force -ErrorAction SilentlyContinue

    if ($proc.ExitCode -ne 0) {
        Write-Host "         ERRO: instalador retornou codigo $($proc.ExitCode)"
        exit 2
    }
} catch {
    Write-Host "         ERRO ao executar instalador: $($_.Exception.Message)"
    Remove-Item $OUT -Force -ErrorAction SilentlyContinue
    exit 2
}

# Verifica que o binário apareceu onde deveria
if (Test-Path $EXPECTED) {
    Write-Host "         Python instalado em $EXPECTED"
    exit 0
} else {
    Write-Host "         AVISO: instalador finalizou mas python.exe nao encontrado em $EXPECTED"
    exit 2
}
