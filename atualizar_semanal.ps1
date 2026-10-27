# Atualização semanal: baixa SINAN e INMET, reprocessa, verifica e recompila o painel.
# Executado pelo Agendador de Tarefas (ver agendar_atualizacao.ps1) ou manualmente.
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force logs | Out-Null
$log = "logs\atualizacao_$(Get-Date -Format 'yyyy-MM-dd_HHmm').log"
$env:PYTHONIOENCODING = 'utf-8'
# O cmd grava saída e erros direto no log: no PowerShell 5.1, texto em stderr (como o resumo
# dos testes) viraria erro do próprio script.
cmd /c ".venv\Scripts\python.exe -m pipeline --semanal > `"$log`" 2>&1"
$codigo = $LASTEXITCODE
Get-Content -LiteralPath $log -Encoding UTF8 -Tail 3
# Mantém só os 20 logs mais recentes.
Get-ChildItem logs -Filter 'atualizacao_*.log' | Sort-Object Name -Descending | Select-Object -Skip 20 | Remove-Item
exit $codigo
