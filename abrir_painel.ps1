param([int]$Porta = 4173)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'painel/dist/index.html')) {
    throw 'Painel ainda não compilado. Execute: .venv/Scripts/python.exe -m pipeline'
}
Write-Host "Painel em http://127.0.0.1:$Porta/ — Ctrl+C encerra o servidor."
& '.venv/Scripts/python.exe' -m http.server $Porta --bind 127.0.0.1 --directory painel/dist
