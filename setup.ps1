$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "MISSING: $cmd. $hint" -ForegroundColor Red; exit 1 } }
Need python "Install Python 3.10+ from python.org (tick 'Add to PATH')."
Need node   "Install Node.js 18+ from nodejs.org."
Need npm    "Reinstall Node.js."
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env; Write-Host "Created backend\.env - set SECRET_KEY." -ForegroundColor Yellow }
if (-not (Test-Path frontend\.env)) { Copy-Item frontend\.env.example frontend\.env }
New-Item -ItemType Directory -Force backend\storage\evidence, backend\storage\reports, backend\storage\frames | Out-Null
Push-Location frontend; npm install; Pop-Location
Push-Location backend; & ..\.venv\Scripts\python.exe -c "from app.main import app; print('Database initialised')"; Pop-Location
Write-Host "Setup complete. Optional AI extras: .\.venv\Scripts\pip install ultralytics faster-whisper" -ForegroundColor Green
