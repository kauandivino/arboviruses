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
# Só publica o site se todo o pipeline (incluindo os testes) passou.
if ($codigo -eq 0) {
    cmd /c ".venv\Scripts\python.exe -m pipeline.publicar_site >> `"$log`" 2>&1"
    $codigo = $LASTEXITCODE
}
# O registro prospectivo vai para o GitHub a cada semana: a data pública do commit comprova
# que cada previsão foi feita antes do resultado. Só esses dois arquivos entram no commit.
if ($codigo -eq 0) {
    $registro = 'dados/modelagem/registro_prospectivo.csv', 'dados/modelagem/registro_prospectivo_resumo.json'
    $existentes = $registro | Where-Object { Test-Path $_ }
    git add -- $existentes 2>&1 | Out-Null
    git diff --cached --quiet -- $existentes
    if ($LASTEXITCODE -ne 0) {
        git -c user.name='Atualização automática' commit -m "Registro prospectivo: semana de $(Get-Date -Format 'yyyy-MM-dd')" -- $existentes >> $log 2>&1
        git push origin HEAD >> $log 2>&1
        if ($LASTEXITCODE) { Add-Content $log 'Aviso: o envio do registro prospectivo ao GitHub falhou; será tentado na próxima semana.' }
    }
}
Get-Content -LiteralPath $log -Encoding UTF8 -Tail 3
# Mantém só os 20 logs mais recentes.
Get-ChildItem logs -Filter 'atualizacao_*.log' | Sort-Object Name -Descending | Select-Object -Skip 20 | Remove-Item
exit $codigo
