# Builds the client (if needed) and starts Osmora on http://127.0.0.1:8000
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path "frontend\dist\index.html")) {
    Push-Location frontend
    if (-not (Test-Path "node_modules")) { npm install }
    npm run build
    Pop-Location
}
Set-Location backend
python scripts\init_db.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
