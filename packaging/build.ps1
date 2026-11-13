param(
    [string]$Python = "python",
    [string]$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
$ErrorActionPreference = 'Stop'
$LumeRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $ISCC)) { throw 'Inno Setup compiler not found; pass -ISCC.' }
& $Python (Join-Path $PSScriptRoot 'make_icon.py')
if ($LASTEXITCODE -ne 0) { throw 'Icon build failed.' }
& $Python -m PyInstaller --noconfirm --distpath (Join-Path $LumeRoot 'dist') --workpath (Join-Path $LumeRoot 'build') (Join-Path $PSScriptRoot 'LumeReader.spec')
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
& $ISCC (Join-Path $PSScriptRoot 'LumeReader.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $LumeRoot 'release\LumeReader-1.1.0-Setup-x64.exe')
