# SkinMyBird — PowerShell launcher (Windows) — Commercial edition
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$env:SKINMYBIRD_EDITION = if ($env:SKINMYBIRD_EDITION) { $env:SKINMYBIRD_EDITION } else { 'commercial' }
$env:SKINMYBIRD_PORT = if ($env:SKINMYBIRD_PORT) { $env:SKINMYBIRD_PORT } else { '5173' }

if (-not $env:SKINMYBIRD_COMMUNITY) {
  $env:SKINMYBIRD_COMMUNITY = 'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community'
}
if (-not $env:SKINMYBIRD_TEXCONV) {
  $env:SKINMYBIRD_TEXCONV = 'C:\Users\eugen\Downloads\texconv.exe'
}

$py = if (Test-Path '.\.venv\Scripts\python.exe') { '.\.venv\Scripts\python.exe' } else { 'python' }

Write-Host "SkinMyBird v0.5.8 [$($env:SKINMYBIRD_EDITION)] → http://127.0.0.1:$($env:SKINMYBIRD_PORT)" -ForegroundColor Cyan
Write-Host "Community: $env:SKINMYBIRD_COMMUNITY"
Write-Host "texconv:   $env:SKINMYBIRD_TEXCONV"

Start-Process "http://127.0.0.1:$($env:SKINMYBIRD_PORT)/?v=0.5.8"
& $py server.py
