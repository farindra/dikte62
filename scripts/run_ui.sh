#!/usr/bin/env bash
# Jalankan UI review lokal.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python scripts/server.py "$@"
