# install_tesseract.ps1
# Baixa e instala o Tesseract OCR (UB-Mannheim build oficial).
# Chamado por instalar.bat quando Tesseract não está presente.
#
# Exit codes:
#   0 = sucesso (Tesseract instalado)
#   1 = falha de download
#   2 = usuário negou UAC ou falha de instalação

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"  # Invoke-WebRequest ~3x mais rápido sem progress bar

# URL pinada (versão conhecida estável). Se ela quebrar no futuro, fazemos
# fallback pra última release via API do GitHub.
$PINNED_VERSION = "5.4.0.20240606"
$PINNED_URL     = "https://github.com/UB-Mannheim/tesseract/releases/download/v$PINNED_VERSION/tesseract-ocr-w64-setup-$PINNED_VERSION.exe"
$OUT            = Join-Path $env:TEMP "tesseract-installer.exe"

function Get-LatestUrl {
    # Consulta API do GitHub e retorna URL do último w64-setup .exe (ou $null)
    try {
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" `
                                  -UseBasicParsing -TimeoutSec 20
        foreach ($a in $rel.assets) {
            if ($a.name -match "w64.*setup.*\.exe$") {
                return $a.browser_download_url
            }
        }
    } catch {
        return $null
    }
    return $null
}

$URL = $PINNED_URL
Write-Host "         Baixando Tesseract OCR v$PINNED_VERSION (~48MB)..."

try {
    Invoke-WebRequest -Uri $URL -OutFile $OUT -UseBasicParsing -TimeoutSec 300
} catch {
    # URL pinada quebrou — buscar último release dinamicamente
    Write-Host "         URL pinada indisponivel. Consultando ultima release..."
    $URL = Get-LatestUrl
    if ($URL) {
        Write-Host "         Encontrada: $URL"
        try {
            Invoke-WebRequest -Uri $URL -OutFile $OUT -UseBasicParsing -TimeoutSec 300
        } catch {
            Write-Host "         ERRO de download (fallback): $($_.Exception.Message)"
            exit 1
        }
    } else {
        Write-Host "         ERRO: nao foi possivel obter URL alternativa via API."
        exit 1
    }
}

if (-not (Test-Path $OUT)) {
    Write-Host "         ERRO: arquivo baixado nao encontrado"
    exit 1
}

Write-Host "         Download OK. Iniciando instalacao silenciosa..."
Write-Host "         (Windows pedira confirmacao de administrador - clique Sim)"

try {
    # /S = silent NSIS install. -Verb RunAs força elevação UAC.
    $proc = Start-Process -FilePath $OUT -ArgumentList "/S" -Verb RunAs -Wait -PassThru
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

# Verifica se realmente instalou
$expected = "C:\Program Files\Tesseract-OCR\tesseract.exe"
if (Test-Path $expected) {
    Write-Host "         Tesseract instalado em $expected"
    exit 0
} else {
    Write-Host "         AVISO: instalador concluiu mas tesseract.exe nao foi encontrado"
    exit 2
}
