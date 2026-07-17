[CmdletBinding()]
param(
    [string]$Bundles = "nsis,msi",
    [string]$OutputDir = "dist/operator-installer"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$operatorRoot = Join-Path $repoRoot "operator-shell"
$bundleRoot = Join-Path $operatorRoot "src-tauri/target/release/bundle"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20+ is required" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm is required" }
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw "Rust/Cargo is required" }

if (Test-Path $bundleRoot) { Remove-Item $bundleRoot -Recurse -Force }

Push-Location $operatorRoot
try {
    npm ci
    npm run tauri -- build --bundles $Bundles --ci
} finally {
    Pop-Location
}

if (-not (Test-Path $bundleRoot)) { throw "Tauri did not produce bundle output: $bundleRoot" }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Get-ChildItem $bundleRoot -Recurse -File |
    Where-Object { $_.Extension -in ".exe", ".msi", ".dmg", ".appimage", ".deb", ".rpm" } |
    ForEach-Object { Copy-Item $_.FullName -Destination $OutputDir -Force }
Write-Host "Operator installers copied to $OutputDir"
