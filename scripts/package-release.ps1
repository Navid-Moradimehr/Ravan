param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "package-release.py"

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($Python) {
    & $Python.Source $ScriptPath @Args
    exit $LASTEXITCODE
}

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($PyLauncher) {
    & $PyLauncher.Source -3 $ScriptPath @Args
    exit $LASTEXITCODE
}

throw "python or py -3 is required to run package-release.ps1"
