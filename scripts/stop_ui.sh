#!/usr/bin/env bash
# Hentikan server Dikte yang dijalankan oleh launcher.
set -uo pipefail
pkill -f "scripts/server.py" && echo "server dihentikan" || echo "tidak ada server berjalan"
