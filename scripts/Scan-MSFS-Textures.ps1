# SkinMyBird — scan real MSFS package texture stems on Eugen's PC
$ErrorActionPreference = 'Continue'
$outDir = Join-Path $env:USERPROFILE 'Desktop\SkinMyBird\scan'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$report = Join-Path $outDir 'texture_scan.json'

$roots = @(
  'D:\MSFS2020\Community\hpg-airbus-h135',
  'D:\MSFS2020\Community\hpg-hotair-balloon',
  'D:\MSFS2020\Community\flybywire-aircraft-a320-neo',
  'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Official\Steam\pmdg-aircraft-736',
  'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Official\Steam\asobo-aircraft-b7478i',
  'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Official\Steam'
)

$steam = 'C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Official\Steam'
$extra = @()
if (Test-Path $steam) {
  $extra = Get-ChildItem $steam -Directory | Where-Object {
    $_.Name -match 'b787|787|newlight|lvfr-airbus-a321|lvfr-a330|asobo-aircraft-b787|asobo-boeing'
  } | ForEach-Object { $_.FullName }
}
$targets = @($roots[0..4] + $extra + $roots[5]) | Select-Object -Unique

function Get-AlbedoStems($texDir) {
  Get-ChildItem $texDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '\.(PNG\.DDS|png\.dds|DDS)$' -and $_.Name -notmatch '_COMP|_NORM|_METAL|_ID|_NML|_CORM|_MSKS|_LIN_' } |
    ForEach-Object {
      $n = $_.Name
      $n -replace '\.PNG\.DDS$','', -replace '\.png\.dds$','' -replace '\.DDS$','' -replace '\.dds$',''
    } | Sort-Object -Unique
}

$results = @()
foreach ($root in $targets) {
  if (-not (Test-Path $root)) {
    $results += [pscustomobject]@{ path=$root; exists=$false }
    continue
  }
  $sim = Get-ChildItem (Join-Path $root 'SimObjects') -Directory -ErrorAction SilentlyContinue
  $airplanes = @()
  foreach ($st in $sim) {
    foreach ($ac in (Get-ChildItem $st.FullName -Directory -ErrorAction SilentlyContinue)) {
      $cfg = Join-Path $ac.FullName 'aircraft.cfg'
      $base = $null
      if (Test-Path $cfg) {
        $m = Select-String -Path $cfg -Pattern 'base_container\s*=\s*"([^"]+)"' | Select-Object -First 1
        if ($m) { $base = $m.Matches[0].Groups[1].Value }
      }
      $texFolders = Get-ChildItem $ac.FullName -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'texture*' }
      $texInfo = @()
      foreach ($tf in $texFolders) {
        $stems = @(Get-AlbedoStems $tf.FullName)
        $fallback = $null
        $tc = Join-Path $tf.FullName 'texture.cfg'
        if (-not (Test-Path $tc)) { $tc = Join-Path $tf.FullName 'texture.CFG' }
        if (Test-Path $tc) { $fallback = Get-Content $tc -Raw }
        $texInfo += [pscustomobject]@{
          folder = $tf.Name
          albedo_stems = $stems
          texture_cfg = $fallback
          sample_files = @(Get-ChildItem $tf.FullName -File | Select-Object -First 40 -ExpandProperty Name)
        }
      }
      $airplanes += [pscustomobject]@{
        simObjectType = $st.Name
        airplane_folder = $ac.Name
        base_container = $base
        textures = $texInfo
      }
    }
  }
  $results += [pscustomobject]@{
    path = $root
    exists = $true
    package = Split-Path $root -Leaf
    aircraft = $airplanes
  }
}

$results | ConvertTo-Json -Depth 8 | Set-Content -Path $report -Encoding UTF8
Write-Host "WROTE $report"
Get-Content $report | Select-Object -First 5
