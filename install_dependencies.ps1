param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw 'Python not found; supply -Python with the interpreter path.' }
$LumeTarget = Join-Path $PSScriptRoot '.runtime\packages'
& $Python -m pip install --isolated --no-cache-dir --disable-pip-version-check --index-url https://pypi.org/simple --target $LumeTarget -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Python (Join-Path $PSScriptRoot 'run.py') --self-check
