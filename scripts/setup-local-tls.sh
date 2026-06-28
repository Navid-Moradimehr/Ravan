#!/bin/bash
"""Setup local TLS certificates for development using mkcert.

Usage:
    bash scripts/setup-local-tls.sh

Requirements:
    - mkcert installed (https://github.com/FiloSottile/mkcert)
    - certutil (for browser trust) - optional

This script creates:
    - tls/localhost.pem (certificate)
    - tls/localhost-key.pem (private key)
    - tls/rootCA.pem (root CA for trust)
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TLS_DIR="$PROJECT_ROOT/tls"

echo "=== Local TLS Certificate Setup ==="

# Check if mkcert is installed
if ! command -v mkcert &> /dev/null; then
    echo "mkcert not found. Installing..."
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y libnss3-tools
        curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
        chmod +x mkcert-v*-linux-amd64
        sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install mkcert
        brew install nss
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        echo "Please install mkcert manually on Windows:"
        echo "  choco install mkcert"
        echo "Or download from: https://github.com/FiloSottile/mkcert/releases"
        exit 1
    fi
fi

# Create TLS directory
mkdir -p "$TLS_DIR"
cd "$TLS_DIR"

# Install local CA
mkcert -install

# Generate certificates for localhost and common dev names
mkcert -cert-file localhost.pem -key-file localhost-key.pem \
    localhost 127.0.0.1 ::1 \
    *.local \
    opcua-sim mqtt-sim modbus-sim \
    172.17.0.1 172.18.0.1

echo ""
echo "=== Certificates created ==="
echo "  Certificate: $TLS_DIR/localhost.pem"
echo "  Private key: $TLS_DIR/localhost-key.pem"
echo "  Root CA:     $(mkcert -CAROOT)/rootCA.pem"
echo ""
echo "=== To use in services ==="
echo "  FastAPI:    ssl_keyfile='tls/localhost-key.pem', ssl_certfile='tls/localhost.pem'"
echo "  MQTT:       Add to mosquitto.conf: cafile, certfile, keyfile"
echo "  OPC UA:     Load certificate in server config"
echo ""
echo "=== Trust the CA in browsers ==="
echo "  The CA is already installed system-wide by mkcert."
echo "  If needed, import $(mkcert -CAROOT)/rootCA.pem into browsers."
