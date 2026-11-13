param(
    [string]$Python = "python",
    [string]$ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    [string]$KindleGen = "",
    [string]$DistPath = "",
    [string]$WorkPath = ""
)
$ErrorActionPreference = 'Stop'
$LumeRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
function Resolve-LumeBuildDirectory([string]$Requested, [string]$DefaultName) {
    if (-not $Requested) { $Requested = Join-Path $LumeRoot $DefaultName }
    $Resolved = [IO.Path]::GetFullPath($Requested)
    if (-not $Resolved.StartsWith($LumeRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build output must remain inside the LumeReader project.'
    }
    $Current = $Resolved
    while ($Current -and $Current -ne $LumeRoot) {
        if (Test-Path -LiteralPath $Current) {
            $Item = Get-Item -LiteralPath $Current -Force
            if (-not $Item.PSIsContainer -or ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw "Build output must use normal project directories: $Current"
            }
        }
        $Current = Split-Path -Parent $Current
    }
    return $Resolved
}
$DistPath = Resolve-LumeBuildDirectory $DistPath 'dist'
$WorkPath = Resolve-LumeBuildDirectory $WorkPath 'build'
if ($DistPath -eq $WorkPath) { throw 'Build and distribution directories must differ.' }
if (-not (Test-Path -LiteralPath $ISCC -PathType Leaf)) { throw 'Inno Setup compiler not found; pass -ISCC.' }
$VersionSource = Get-Content -LiteralPath (Join-Path $LumeRoot 'lume\__init__.py') -Raw
$LumeVersion = [regex]::Match($VersionSource, "__version__\s*=\s*'([^']+)'" ).Groups[1].Value
if (-not $LumeVersion) { throw 'Application version not found.' }
$OutputBase = "LumeReader-$LumeVersion-Setup-x64"
$PreviousBundle = $env:LUME_BUNDLE_KINDLEGEN
try {
    $env:LUME_BUNDLE_KINDLEGEN = $null
    if (-not $KindleGen) { $KindleGen = Join-Path $LumeRoot 'tools\kindlegen.exe' }
    if (-not (Test-Path -LiteralPath $KindleGen -PathType Leaf)) { throw 'KindleGen is required for the installer; pass -KindleGen or place it in tools.' }
    $Compiler = Get-Item -LiteralPath $KindleGen
    if ($Compiler.Name -ne 'kindlegen.exe') { throw 'Pass the kindlegen.exe file.' }
    $env:LUME_BUNDLE_KINDLEGEN = $Compiler.FullName
    & $Python -m PyInstaller --noconfirm --distpath $DistPath --workpath $WorkPath (Join-Path $PSScriptRoot 'LumeReader.spec')
    if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
    & $ISCC "/DAppVersion=$LumeVersion" "/DSourceDir=$(Join-Path $DistPath 'LumeReader')" "/DOutputBaseName=$OutputBase" (Join-Path $PSScriptRoot 'LumeReader.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $LumeRoot "release\$OutputBase.exe")
} finally {
    $env:LUME_BUNDLE_KINDLEGEN = $PreviousBundle
}
