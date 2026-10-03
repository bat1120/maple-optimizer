# 로컬 실행: 웹을 빌드하고 FastAPI(uvicorn)로 http://127.0.0.1:8000 에 띄운다.
#   -Check : 서버를 띄워 /api/health 200을 확인하고 바로 종료한다 (VERIFY G8용, 종료코드로 판정)
param([switch]$Check, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path "web/dist/index.html")) {
    & npm --prefix web run build | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Output "웹 빌드 실패"; exit 1 }
}

if (-not $Check) {
    & uv run uvicorn server.app:default_app --factory --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

$proc = Start-Process -FilePath "uv" -ArgumentList @("run", "uvicorn", "server.app:default_app", "--factory", "--host", "127.0.0.1", "--port", "$Port") -PassThru -WindowStyle Hidden
try {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch { }
    }
    if ($ok) {
        $root = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2
        Write-Output "health 200, / $($root.StatusCode)"
        exit 0
    }
    Write-Output "health check 실패 (30초 안에 200 없음)"
    exit 1
} finally {
    if ($proc -and -not $proc.HasExited) {
        & taskkill /PID $proc.Id /T /F | Out-Null
    }
}
