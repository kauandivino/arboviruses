# Prepara o projeto em um computador novo (Windows).
#   .\instalar.ps1
#   .\instalar.ps1 -Pacote C:\Downloads\originais_insubstituiveis_20261027.zip
# Depois: .venv\Scripts\python.exe -m pipeline --coletar
param([string]$Pacote)
# Comandos externos (uv, npm) escrevem avisos na saída de erro; no PowerShell 5.1 isso não pode
# interromper o script. Cada etapa confere o código de saída e os cmdlets usam -ErrorAction Stop.
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot
$versaoNode = 'v22.14.0'
$pastaNode = ".tools/node/node-$versaoNode-win-x64"

function Etapa($texto) { Write-Host "`n== $texto" -ForegroundColor Cyan }

Etapa 'Verificando pré-requisitos'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'O uv não está instalado. Instale com: winget install --id=astral-sh.uv -e  (ou veja https://docs.astral.sh/uv/) e rode este script de novo.'
}
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ }
if (-not $edge) { Write-Warning 'Microsoft Edge não encontrado: a coleta dos informes e os testes de navegador precisam dele.' }

Etapa 'Ambiente Python 3.13 (.venv)'
# Python 3.13: o conversor .dbc do SINAN não tem pacote para 3.14 no Windows.
if (-not (Test-Path .venv/Scripts/python.exe)) {
    uv venv --python 3.13 .venv 2>&1 | Out-Host
    if ($LASTEXITCODE) { throw 'Falha ao criar o .venv.' }
}
uv pip install --python .venv/Scripts/python.exe -r requirements.txt 2>&1 | Out-Host
if ($LASTEXITCODE) { throw 'Falha ao instalar as dependências Python.' }

Etapa "Node.js portátil $versaoNode"
if (-not (Test-Path "$pastaNode/node.exe")) {
    New-Item -ItemType Directory -Force .tools/node -ErrorAction Stop | Out-Null
    $zip = ".tools/node/node-$versaoNode-win-x64.zip"
    $base = "https://nodejs.org/dist/$versaoNode"
    Invoke-WebRequest "$base/node-$versaoNode-win-x64.zip" -OutFile $zip -UseBasicParsing -ErrorAction Stop
    $esperado = ((Invoke-WebRequest "$base/SHASUMS256.txt" -UseBasicParsing -ErrorAction Stop).Content -split "`n" | Where-Object { $_ -match "node-$versaoNode-win-x64.zip" }).Split(' ')[0]
    $obtido = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($obtido -ne $esperado) { Remove-Item $zip; throw 'SHA-256 do Node.js não confere com SHASUMS256.txt oficial.' }
    Expand-Archive $zip -DestinationPath .tools/node -ErrorAction Stop
    Remove-Item $zip
}
$env:PATH = "$PSScriptRoot/$pastaNode;$env:PATH"

Etapa 'Dependências do painel da equipe e do site público'
foreach ($app in 'painel', 'site') {
    npm ci --prefix $app --no-audit --no-fund 2>&1 | Out-Host
    if ($LASTEXITCODE) { throw "Falha no npm ci de $app." }
}

if ($Pacote) {
    Etapa 'Restaurando os originais insubstituíveis'
    & .venv/Scripts/python.exe -m pipeline.comum.pacote_originais restaurar $Pacote 2>&1 | Out-Host
    if ($LASTEXITCODE) { throw 'Falha ao restaurar o pacote de originais.' }
}

Etapa 'Pronto'
Write-Host 'Próximos passos:'
if (-not $Pacote) { Write-Host '  1. Baixe o pacote de originais da release do GitHub e rode: .\instalar.ps1 -Pacote <arquivo.zip>' }
Write-Host '  2. Baixe e processe as fontes oficiais (demora, ~3 GB): .venv\Scripts\python.exe -m pipeline --coletar'
Write-Host '  3. Abra o site e o painel: .\abrir_painel.ps1'
