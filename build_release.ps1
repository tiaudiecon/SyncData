# Gera o executável do SyncData em dist/SyncData/
$ErrorActionPreference = "Stop"
if (-not (Test-Path ".\venv")) { python -m venv venv }
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\pyinstaller.exe --noconfirm SyncData.spec
Write-Host "Pronto: dist\SyncData\SyncData.exe"
