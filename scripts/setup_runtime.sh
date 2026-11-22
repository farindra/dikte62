#!/usr/bin/env bash
# Pintasan: setup lintas platform ada di scripts/setup.py
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/setup.py "$@"
