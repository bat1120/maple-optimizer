# VERIFY 게이트: 목표별 판정. skip·누락·0개 실행은 미달이다.
param([Parameter(Mandatory = $true)][string]$Goal)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$id = $Goal.ToLower()
$test = "tests/goals/test_$id.py"
if (-not (Test-Path $test)) { Write-Output "VERIFY FAIL: 판정 테스트 없음 ($test)"; exit 1 }

$out = & uv run pytest $test -q -rs -p no:cacheprovider 2>&1 | Out-String
$code = $LASTEXITCODE
Write-Output $out
if ($code -ne 0) { Write-Output "VERIFY FAIL (pytest exit $code)"; exit 1 }
if ($out -match "skipped") { Write-Output "VERIFY FAIL: skip 발생 (skip은 통과가 아니다)"; exit 1 }
if ($out -notmatch "\d+ passed") { Write-Output "VERIFY FAIL: 실행된 테스트 없음"; exit 1 }

if ($id -eq "g4") {
    $env:NO_COLOR = "1"; $env:FORCE_COLOR = "0"
    & npm --prefix web run build 2>&1 | Out-String | Write-Output
    if ($LASTEXITCODE -ne 0) { Write-Output "VERIFY FAIL: web build"; exit 1 }
    $web = & npm --prefix web test 2>&1 | Out-String
    Write-Output $web
    if ($LASTEXITCODE -ne 0) { Write-Output "VERIFY FAIL: web test"; exit 1 }
    if ($web -match "Tests\s+(\d+) passed") { if ([int]$Matches[1] -lt 8) { Write-Output "VERIFY FAIL: vitest $($Matches[1]) < 8"; exit 1 } }
    else { Write-Output "VERIFY FAIL: vitest 결과를 읽을 수 없음"; exit 1 }
}

if ($id -eq "g8") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run-local.ps1 -Check
    if ($LASTEXITCODE -ne 0) { Write-Output "VERIFY FAIL: run-local health check"; exit 1 }
}

Write-Output "VERIFY OK ($Goal)"
exit 0
