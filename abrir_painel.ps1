param([int]$Porta = 4173)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.venv/Scripts/python.exe' -m pipeline.servidor --porta $Porta
