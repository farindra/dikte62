#!/usr/bin/env bash
# Setup runtime Dikte62 tanpa Homebrew / sudo.
#
# Yang dilakukan:
#   1. unduh CPython 3.12 portabel ke .runtime/
#   2. buat virtualenv .venv/
#   3. pasang dependensi dari requirements.txt
#   4. sediakan ffmpeg statis (lewat imageio-ffmpeg) di .venv/bin/ffmpeg
#
# Semua artefak ditulis di dalam folder proyek agar tidak menyentuh sistem.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export XDG_CACHE_HOME="$ROOT/.cache"
export PIP_CACHE_DIR="$ROOT/.cache/pip"
export HF_HOME="$ROOT/.cache/huggingface"

PY_VERSION="3.12.16"
PY_TAG="20261110"
PYURL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_TAG}/cpython-${PY_VERSION}+${PY_TAG}-aarch64-apple-darwin-install_only.tar.gz"

echo "== [1/5] runtime python ${PY_VERSION} =="
mkdir -p .runtime
if [ ! -x .runtime/python/bin/python3 ]; then
  if [ "$(uname -m)" != "arm64" ]; then
    echo "Catatan: skrip ini mengunduh build arm64. Di Intel, ganti URL ke x86_64-apple-darwin."
  fi
  curl -sSL -o .runtime/py.tar.gz "$PYURL"
  tar xzf .runtime/py.tar.gz -C .runtime
  rm -f .runtime/py.tar.gz
fi
.runtime/python/bin/python3 --version

echo "== [2/5] virtualenv =="
if [ ! -x .venv/bin/python ]; then
  .runtime/python/bin/python3 -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip wheel setuptools

echo "== [3/5] dependensi runtime =="
.venv/bin/pip install -q -r requirements.txt

echo "== [4/5] ffmpeg statis =="
FF="$(.venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
ln -sf "$FF" .venv/bin/ffmpeg
export PATH="$ROOT/.venv/bin:$PATH"
ffmpeg -version | head -1

echo "== [5/5] verifikasi =="
.venv/bin/python - <<'PY'
import faster_whisper, ctranslate2, sklearn, speechbrain, docx, av
print("faster-whisper", faster_whisper.__version__, "| ctranslate2", ctranslate2.__version__)
print("torch/sklearn/speechbrain ok | av", av.__version__)
PY

cat <<'MSG'

Selesai.

  Jalankan aplikasi : bash scripts/run_ui.sh          (http://127.0.0.1:8777)
  Atau buat .app    : python scripts/build_app.py     → Dikte62.app
  API key LLM       : isi lewat ikon ⚙ di UI (disimpan di .data/config.json)
MSG
