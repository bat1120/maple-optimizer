# VALIDATE 게이트: 전체 회귀 스위트. 종료코드 0이 아니면 다음 단계로 가지 않는다.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$out = & uv run pytest -q -rs -p no:cacheprovider 2>&1 | Out-String
$code = $LASTEXITCODE
$summary = ($out -split "`n" | Where-Object { $_ -match "passed|failed|error|no tests ran" } | Select-Object -Last 1)
Write-Output "pytest: $summary"
if ($code -ne 0) { Write-Output $out; Write-Output "VALIDATE FAIL (pytest exit $code)"; exit 1 }

if (Test-Path "web/package.json") {
    $web = & npm --prefix web test --silent 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { Write-Output $web; Write-Output "VALIDATE FAIL (web test)"; exit 1 }
    Write-Output "web test: ok"
}
Write-Output "VALIDATE OK"
exit 0
