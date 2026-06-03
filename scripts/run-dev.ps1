$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
$PythonCandidates = @(
    (Join-Path $ProjectRoot ".venv-win\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
)

$Python = $PythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    throw "Python venv not found. Run: py -3.11 -m venv .venv-win"
}

if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created .env from .env.example. Set JWT_SECRET to match college_server before using real college tokens."
}

Push-Location $ProjectRoot
try {
    & $Python -m app.db.migrations upgrade head
    & $Python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
}
finally {
    Pop-Location
}
