"""Bangun bundle macOS `Dikte.app` (launcher untuk server lokal + browser).

Hasil: Dikte.app di root proyek. Klik dua kali → server jalan (bila belum) → browser terbuka.
Bundle harus tetap di dalam folder proyek karena memakai runtime di .venv.
"""

import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import platform_support  # noqa: E402,F401  (stdout UTF-8 + cache default)

import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP = os.path.join(ROOT, "Dikte62.app")
PORT = 8777

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Dikte62</string>
  <key>CFBundleDisplayName</key><string>Dikte62</string>
  <key>CFBundleIdentifier</key><string>com.farindra.dikte62</string>
  <key>CFBundleVersion</key><string>0.4.0</string>
  <key>CFBundleShortVersionString</key><string>0.4.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Dikte62</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
</dict>
</plist>
"""

LAUNCHER = """#!/bin/bash
# Launcher Dikte62 — menyalakan server lokal (bila perlu) lalu membuka browser.
set -uo pipefail

APP_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  APP_DIR="__ROOT__"
fi
cd "$APP_DIR" || exit 1

PORT=__PORT__
LOG="$APP_DIR/.data/dikte.log"
mkdir -p "$APP_DIR/.data"

if ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/api/meetings"; then
  nohup "$APP_DIR/.venv/bin/python" scripts/server.py --port "$PORT" >>"$LOG" 2>&1 &
  for _ in $(seq 1 60); do
    sleep 0.25
    curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/" && break
  done
fi

open "http://127.0.0.1:$PORT"
"""


def make_icon(path: str) -> None:
    size = 1024
    img = Image.new("RGB", (size, size), "#2563eb")
    d = ImageDraw.Draw(img)
    for y in range(size):  # gradasi vertikal
        t = y / size
        d.line([(0, y), (size, y)], fill=(int(37 + 20 * t), int(99 - 40 * t), int(235 - 40 * t)))
    # kartu putih
    m = 150
    d.rounded_rectangle([m, m, size - m, size - m], radius=90, fill="#ffffff")
    # waveform
    bars = [0.30, 0.55, 0.85, 0.55, 0.30]
    bw, gap = 46, 26
    total = len(bars) * bw + (len(bars) - 1) * gap
    x = (size - total) // 2
    for h in bars:
        bh = int(330 * h)
        d.rounded_rectangle([x, size // 2 - bh // 2, x + bw, size // 2 + bh // 2], radius=23,
                            fill="#2563eb")
        x += bw + gap
    try:
        font = ImageFont.truetype("/System/Library/Fonts/SFNSRounded.ttf", 104)
        d.text((size // 2, 800), "Dikte62", font=font, fill="#667085", anchor="mm")
    except Exception:  # noqa: BLE001
        pass
    img.save(path, "PNG")


def main() -> None:
    if os.path.isdir(APP):
        shutil.rmtree(APP)
    for sub in ("Contents/MacOS", "Contents/Resources"):
        os.makedirs(os.path.join(APP, sub), exist_ok=True)

    with open(os.path.join(APP, "Contents/Info.plist"), "w", encoding="utf-8") as f:
        f.write(INFO_PLIST)

    exe = os.path.join(APP, "Contents/MacOS/Dikte62")
    with open(exe, "w", encoding="utf-8") as f:
        f.write(LAUNCHER.replace("__ROOT__", ROOT).replace("__PORT__", str(PORT)))
    os.chmod(exe, 0o755)

    # ikon: pakai assets/AppIcon.icns bila ada, kalau tidak render dari kode lama
    icns_src = os.path.join(ROOT, "assets", "AppIcon.icns")
    icns_dst = os.path.join(APP, "Contents/Resources/AppIcon.icns")
    if os.path.exists(icns_src):
        shutil.copy(icns_src, icns_dst)
        print("[ok] ikon dari assets/AppIcon.icns")
    else:
        iconset = os.path.join(APP, "Contents/Resources/Dikte.iconset")
        os.makedirs(iconset, exist_ok=True)
        base = os.path.join(iconset, "base.png")
        make_icon(base)
        src = Image.open(base)
        for s_ in (16, 32, 64, 128, 256, 512, 1024):
            src.resize((s_, s_), Image.LANCZOS).save(os.path.join(iconset, f"icon_{s_}x{s_}.png"))
            if s_ <= 512:
                src.resize((s_ * 2, s_ * 2), Image.LANCZOS).save(
                    os.path.join(iconset, f"icon_{s_}x{s_}@2x.png"))
        os.remove(base)
        try:
            subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_dst], check=True)
            shutil.rmtree(iconset)
            print("[ok] ikon .icns dibuat")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] iconutil gagal: {e}")

    print(f"[ok] {APP}")
    print(f"     executable: {os.path.relpath(exe, ROOT)}")


if __name__ == "__main__":
    main()
