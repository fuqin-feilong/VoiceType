# Build VoiceType installer + portable package.
# Usage: powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
$pyinstaller = Join-Path $root '.venv\Scripts\pyinstaller.exe'
$iscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'

$verLine = Select-String -Path (Join-Path $root 'src\voicetype\__init__.py') -Pattern '__version__ = "(.+)"'
$ver = $verLine.Matches[0].Groups[1].Value
Write-Host "Building VoiceType $ver"

# 1. icon
& $python (Join-Path $root 'packaging\make_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'icon generation failed' }

# 2. onedir build
& $pyinstaller --noconfirm --clean --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build\pyi') (Join-Path $root 'packaging\voicetype.spec')
if ($LASTEXITCODE -ne 0) { throw 'pyinstaller failed' }

# 3. drop duplicated nvidia folder (the app uses _internal\cuda)
Remove-Item (Join-Path $root 'dist\VoiceType\_internal\nvidia') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $root 'dist\VoiceType\data') -Recurse -Force -ErrorAction SilentlyContinue

# 4. installer (compile BEFORE portable.txt is added)
& $iscc "/DMyAppVersion=$ver" (Join-Path $root 'packaging\installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'inno setup failed' }

# 5. portable package
$portableDir = Join-Path $root 'dist\VoiceType'
Remove-Item (Join-Path $portableDir 'data') -Recurse -Force -ErrorAction SilentlyContinue
Set-Content -Path (Join-Path $portableDir 'portable.txt') -Value 'VoiceType portable mode' -Encoding utf8
$zip = Join-Path $root ("dist\VoiceType-{0}-portable.zip" -f $ver)
if (Test-Path $zip) { Remove-Item $zip -Force }
& tar.exe -a -c -f $zip -C (Join-Path $root 'dist') VoiceType
if ($LASTEXITCODE -ne 0) { throw 'portable zip failed' }

Write-Host ''
Write-Host 'Build finished:'
Get-ChildItem (Join-Path $root 'dist') -Filter 'VoiceType*' | Select-Object Name, @{n='MB'; e={[math]::Round($_.Length/1MB,1)}}
