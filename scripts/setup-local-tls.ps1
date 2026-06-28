# Setup local TLS certificates for development using mkcert
# Usage: .\scripts\setup-local-tls.ps1
# Requirements: mkcert (choco install mkcert or from GitHub releases)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TlsDir = Join-Path $ProjectRoot "tls"

Write-Host "=== Local TLS Certificate Setup ===" -ForegroundColor Cyan

# Check if mkcert is installed
$mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
if (-not $mkcert) {
    Write-Host "mkcert not found. Please install it:" -ForegroundColor Yellow
    Write-Host "  choco install mkcert" -ForegroundColor Yellow
    Write-Host "  Or download from: https://github.com/FiloSottile/mkcert/releases" -ForegroundColor Yellow
    exit 1
}

# Create TLS directory
New-Item -ItemType Directory -Force -Path $TlsDir | Out-Null
Set-Location $TlsDir

# Install local CA
Write-Host "Installing local CA..." -ForegroundColor Green
mkcert -install

# Generate certificates
Write-Host "Generating certificates..." -ForegroundColor Green
mkcert -cert-file localhost.pem -key-file localhost-key.pem `
    localhost 127.0.0.1 ::1 `
    *.local `
    opcua-sim mqtt-sim modbus-sim `
    172.17.0.1 172.18.0.1

Write-Host ""
Write-Host "=== Certificates created ===" -ForegroundColor Green
Write-Host "  Certificate: $TlsDir\localhost.pem"
Write-Host "  Private key: $TlsDir\localhost-key.pem"
Write-Host "  Root CA:     $(mkcert -CAROOT)\rootCA.pem"
Write-Host ""
Write-Host "=== To use in services ===" -ForegroundColor Cyan
Write-Host "  FastAPI:    ssl_keyfile='tls/localhost-key.pem', ssl_certfile='tls/localhost.pem'"
Write-Host "  MQTT:       Add to mosquitto.conf: cafile, certfile, keyfile"
Write-Host "  OPC UA:     Load certificate in server config"
Write-Host ""
Write-Host "=== Trust the CA in browsers ===" -ForegroundColor Cyan
Write-Host "  The CA is already installed system-wide by mkcert."
Write-Host "  If needed, import $(mkcert -CAROOT)\rootCA.pem into browsers."

Set-Location $ProjectRoot
