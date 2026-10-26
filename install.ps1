# VigIA installer — Windows 11 (PowerShell 5+).
# Creates %LOCALAPPDATA%\vigia with a private venv, PySide6 and a launcher.

$ErrorActionPreference = "Stop"
$Root = Join-Path $env:LOCALAPPDATA "vigia"
$Src = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "VigIA -> $Root"

# Python 3.11+ is required (tomllib)
$python = $null
foreach ($candidate in @("python", "py")) {
    try {
        $version = & $candidate -c "import sys; print(sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -match "\((3, 1[1-9])\)") { $python = $candidate; break }
    } catch { }
}
if (-not $python) {
    throw "Python 3.11+ nao encontrado. Instale em https://python.org (marque 'Add python.exe to PATH')."
}

New-Item -ItemType Directory -Force -Path $Root | Out-Null
Copy-Item -Force "$Src\vigia", "$Src\vigia_qt.py", "$Src\vigia_core.py" $Root
Copy-Item -Recurse -Force "$Src\icons" (Join-Path $Root "icons")
Copy-Item -Recurse -Force "$Src\assets" (Join-Path $Root "assets")

$venv = Join-Path $Root "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "Criando ambiente Python..."
    & $python -m venv $venv
}

$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando PySide6 (~82 MB de download; ~245 MB instalado)..."
    & $venvPython -m pip install --upgrade pip | Out-Null
    & $venvPython -m pip install PySide6-Essentials psutil
}

# Launcher in the repo root so the autostart command stays stable
$launcher = Join-Path $Root "vigia.cmd"
@"
@echo off
"%~dp0venv\Scripts\python.exe" "%~dp0vigia" %*
"@ | Set-Content -Encoding ASCII $launcher

# Start Menu shortcut (no console window)
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $startMenu "VigIA.lnk"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + (Join-Path $Root "vigia") + '"'
$shortcut.WorkingDirectory = $Root
$shortcut.Description = "AI usage and system metrics at a glance"
$shortcut.Save()

Write-Host ""
Write-Host "VigIA instalado."
Write-Host "Abra pelo menu Iniciar (VigIA) ou rode: $launcher"
Write-Host "Sem dados? Instale o CLI ai-usagebar: https://github.com/akitaonrails/ai-usagebar"
