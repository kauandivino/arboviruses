# Cria (ou remove, com -Remover) a tarefa semanal no Agendador de Tarefas do Windows.
#   .\agendar_atualizacao.ps1                      segunda-feira às 07:00
#   .\agendar_atualizacao.ps1 -Dia Friday -Hora 20:30
#   .\agendar_atualizacao.ps1 -Remover
param(
    [ValidateSet('Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')][string]$Dia = 'Monday',
    [string]$Hora = '07:00',
    [switch]$Remover
)
$ErrorActionPreference = 'Stop'
$nome = 'SaudeNoTerritorio-AtualizacaoSemanal'
if ($Remover) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false
    Write-Host "Tarefa '$nome' removida."
    return
}
$script = Join-Path $PSScriptRoot 'atualizar_semanal.ps1'
$acao = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $PSScriptRoot
$gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Dia -At $Hora
# Se o computador estiver desligado no horário, roda assim que possível; só com internet; no máximo 3 horas.
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Settings $config `
    -Description 'Saúde no Território: baixa SINAN e INMET, reprocessa, verifica e recompila o painel.' -Force | Out-Null
Write-Host "Tarefa '$nome' agendada: toda $Dia às $Hora (usuário atual, só quando conectado)."
Write-Host "Logs em $(Join-Path $PSScriptRoot 'logs')."
