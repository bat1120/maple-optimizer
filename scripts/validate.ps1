# VALIDATE 게이트: 회귀 스위트(tests/, 목표 판정 tests/goals 제외 — 판정은 verify.ps1). 종료코드 0이 아니면 다음 단계로 가지 않는다.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$ErrorActionPreference = "Continue"  # uv가 stderr에 알림을 써도 종료코드로만 판정한다
$out = & uv run pytest -q -rs -p no:cacheprovider --ignore=tests/goals 2>&1 | Out-String
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
$summary = ($out -split "`n" | Where-Object { $_ -match "passed|failed|error|no tests ran" } | Select-Object -Last 1)
Write-Output "pytest: $summary"
if ($code -ne 0) { Write-Output $out; Write-Output "VALIDATE FAIL (pytest exit $code)"; exit 1 }

if (Test-Path "web/package.json") {
    # npm/node가 stderr에 경고만 써도 Stop 설정에서는 예외로 끝난다(2026-10-06 간헐 실패) — 종료코드로만 판정한다
    $ErrorActionPreference = "Continue"
    $web = & npm --prefix web test --silent 2>&1 | Out-String
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { Write-Output $web; Write-Output "VALIDATE FAIL (web test)"; exit 1 }
    Write-Output "web test: ok"
}
Write-Output "VALIDATE OK"
exit 0
