# SkinMyBird — PowerShell launcher (Windows)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not $env:SKINMYBIRD_COMMUNITY) {
  $env:SKINMYBIRD_COMMUNITY = 'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community'
}
if (-not $env:SKINMYBIRD_TEXCONV) {
  $env:SKINMYBIRD_TEXCONV = 'C:\Users\eugen\Downloads\texconv.exe'
}

$py = if (Test-Path '.\.venv\Scripts\python.exe') { '.\.venv\Scripts\python.exe' } else { 'python' }

Write-Host "SkinMyBird v0.3 → http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "Community: $env:SKINMYBIRD_COMMUNITY"
Write-Host "texconv:   $env:SKINMYBIRD_TEXCONV"

Start-Process 'http://127.0.0.1:5173'
& $py server.py
