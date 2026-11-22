#!/usr/bin/env python3
"""Bootstrap Dikte62 di macOS, Windows, atau Linux — tanpa sudo, tanpa Homebrew.

Yang dilakukan:
  1. unduh CPython 3.12 portabel (python-build-standalone) ke .runtime/
  2. buat virtualenv .venv/
  3. pasang dependensi dari requirements.txt
  4. sediakan binary ffmpeg di dalam venv (dari paket imageio-ffmpeg)

Contoh:
  python scripts/setup.py
  python scripts/setup.py --dry-run          # lihat URL yang akan diunduh
  python scripts/setup.py --python /usr/bin/python3.12   # pakai python yang sudah ada
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TAG = "20261110"
VERSION = "3.12.16"
BASE = "https://github.com/astral-sh/python-build-standalone/releases/download"


def target() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if system == "Darwin":
        return f"{arch}-apple-darwin"
    if system == "Windows":
        return f"{arch}-pc-windows-msvc"
    if system == "Linux":
        return f"{arch}-unknown-linux-gnu"
    raise SystemExit(f"Platform belum didukung: {system} {machine}")


def asset_url(triple: str) -> str:
    return f"{BASE}/{TAG}/cpython-{VERSION}+{TAG}-{triple}-install_only.tar.gz"


def python_exe(runtime: str) -> str:
    for rel in ("python/bin/python3", "python/python.exe"):
        p = os.path.join(runtime, *rel.split("/"))
        if os.path.exists(p):
            return p
    raise SystemExit(f"Python portabel tidak ditemukan di {runtime}")


def run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def download(url: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    print(f"  mengunduh {url}", flush=True)
    tmp = dst + ".part"
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(tmp, dst)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--python", default="", help="pakai interpreter Python yang sudah ada")
    p.add_argument("--skip-python", action="store_true", help="jangan unduh Python portabel")
    a = p.parse_args()

    triple = target()
    url = asset_url(triple)
    print(f"[dikte62] platform {platform.system()} {platform.machine()} → {triple}")
    print(f"[dikte62] python portabel {VERSION}")
    if a.dry_run:
        print(f"[dry-run] {url}")
        return

    os.environ.setdefault("XDG_CACHE_HOME", os.path.join(ROOT, ".cache"))
    os.environ.setdefault("PIP_CACHE_DIR", os.path.join(ROOT, ".cache", "pip"))
    os.environ.setdefault("HF_HOME", os.path.join(ROOT, ".cache", "huggingface"))

    runtime = os.path.join(ROOT, ".runtime")
    if a.python:
        base_python = a.python
        print(f"[1/4] memakai Python yang ada: {base_python}")
    elif a.skip_python:
        base_python = sys.executable
        print(f"[1/4] memakai Python saat ini: {base_python}")
    else:
        print("[1/4] python portabel")
        archive = os.path.join(runtime, "py.tar.gz")
        py = python_exe(runtime) if os.path.isdir(runtime) else ""
        if not py:
            download(url, archive)
            with tarfile.open(archive) as t:
                try:
                    t.extractall(runtime, filter="data")
                except TypeError:  # python < 3.12
                    t.extractall(runtime)
            os.remove(archive)
        base_python = python_exe(runtime)
    run([base_python, "--version"])

    print("[2/4] virtualenv .venv")
    venv = os.path.join(ROOT, ".venv")
    vpy = os.path.join(venv, "Scripts" if os.name == "nt" else "bin",
                       "python.exe" if os.name == "nt" else "python")
    if not os.path.exists(vpy):
        run([base_python, "-m", "venv", venv])
    run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip", "wheel", "setuptools"])

    print("[3/4] dependensi (requirements.txt)")
    run([vpy, "-m", "pip", "install", "-q", "-r", os.path.join("requirements.txt")])

    print("[4/4] ffmpeg")
    ff = subprocess.run(
        [vpy, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    bindir = os.path.dirname(vpy)
    if os.name == "nt":
        shutil.copy(ff, os.path.join(bindir, "ffmpeg.exe"))
        print(f"  ffmpeg.exe ← {ff}")
    else:
        link = os.path.join(bindir, "ffmpeg")
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink(ff, link)
        print(f"  ffmpeg ← {ff}")

    print("\nSelesai.")
    if os.name == "nt":
        print("  Jalankan  : run_ui.bat")
    else:
        print("  Jalankan  : bash scripts/run_ui.sh")
    print("  Aplikasi  : buka http://127.0.0.1:8777")
    print("  API key   : isi lewat ikon ⚙ di UI (disimpan di .data/config.json)")


if __name__ == "__main__":
    main()
