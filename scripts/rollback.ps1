# 되돌리기: 커밋되지 않은 변경을 stash로 치운다 (삭제하지 않음 — `git stash list`로 복구 가능).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
& git stash push -u -m "goal-rollback $stamp" | Write-Output
Write-Output "ROLLBACK: 미커밋 변경을 stash에 보관 (goal-rollback $stamp)"
exit 0
