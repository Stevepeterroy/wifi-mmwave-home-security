#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export HAVEN_DEVICE_BIND=0.0.0.0
export HAVEN_DEVICE_TLS_CERT=data/device-tls/server.crt
export HAVEN_DEVICE_TLS_KEY=data/device-tls/server.key
if [ ! -f data/device-tls/host.env ]; then
  echo 'Run .venv/bin/python tools/configure_wifi_host.py --host YOUR_LAPTOP_LAN_IP first.' >&2
  exit 1
fi
set -a
. ./data/device-tls/host.env
set +a
exec .venv/bin/python server.py
