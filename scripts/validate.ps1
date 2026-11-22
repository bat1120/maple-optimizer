# VALIDATE 게이트: 회귀 스위트(tests/, 목표 판정 tests/goals 제외 — 판정은 verify.ps1). 종료코드 0이 아니면 다음 단계로 가지 않는다.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$ErrorActionPreference = "Continue"  # uv가 stderr에 알림을 써도 종료코드로만 판정한다
$lint = & uv run ruff check . --output-format concise 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { Write-Output $lint; Write-Output "VALIDATE FAIL (ruff)"; exit 1 }
Write-Output "ruff: ok"
$out = & uv run pytest -q -rs -p no:cacheprovider --ignore=tests/goals -n 8 2>&1 | Out-String  # 병렬(pytest-xdist): 약 9분 → 3분(2026-10-17)
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
# AI 상담 평가(실제 모델): AI 상담에 닿는 파일이 마지막 통과 뒤로 바뀌었을 때만 돈다. 키가 없는 곳(클라우드)에서는 건너뛴다.
$ErrorActionPreference = "Continue"
$ai = & uv run python tools/agent_eval/run.py --if-changed 2>&1 | Out-String
$aiCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($aiCode -eq 2) { Write-Output "ai eval: 건너뜀(OPENAI_API_KEY 없음)" }
elseif ($aiCode -ne 0) { Write-Output $ai; Write-Output "VALIDATE FAIL (ai eval)"; exit 1 }
else { Write-Output ("ai eval: " + (($ai -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 1).Trim())) }
Write-Output "VALIDATE OK"
exit 0
