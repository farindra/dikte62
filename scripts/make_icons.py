"""Hasilkan favicon + ikon aplikasi dari assets/icon.svg.

Keluaran:
  ui/favicon.svg, ui/favicon-16.png, ui/favicon-32.png, ui/apple-touch-icon.png
  assets/icon-1024.png, assets/AppIcon.icns

Render SVG memakai Playwright bila tersedia (dev-only); kalau tidak, memakai
assets/icon-1024.png yang sudah ter-commit.
"""

import os
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SVG = os.path.join(ROOT, "assets", "icon.svg")
PNG1024 = os.path.join(ROOT, "assets", "icon-1024.png")
UI = os.path.join(ROOT, "ui")
ICONSET = os.path.join(ROOT, "assets", "AppIcon.iconset")
ICNS = os.path.join(ROOT, "assets", "AppIcon.icns")


def render_svg() -> Image.Image:
    try:
        import asyncio

        from playwright.async_api import async_playwright
    except ImportError:
        print("[info] playwright tidak ada → memakai assets/icon-1024.png")
        return Image.open(PNG1024).convert("RGBA")

    async def shot():
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1024, "height": 1024},
                                          device_scale_factor=1)
            await page.goto("file://" + SVG)
            await page.wait_for_timeout(300)
            await page.screenshot(path=PNG1024, omit_background=True)
            await browser.close()

    asyncio.run(shot())
    print(f"[ok] render {os.path.relpath(PNG1024, ROOT)}")
    return Image.open(PNG1024).convert("RGBA")


def save(im: Image.Image, path: str, size: int) -> None:
    im.resize((size, size), Image.LANCZOS).save(path, optimize=True)
    print(f"[ok] {os.path.relpath(path, ROOT)} ({size}px)")


def build_icns(im: Image.Image) -> None:
    if os.path.isdir(ICONSET):
        shutil.rmtree(ICONSET)
    os.makedirs(ICONSET)
    for s in (16, 32, 64, 128, 256, 512):
        im.resize((s, s), Image.LANCZOS).save(os.path.join(ICONSET, f"icon_{s}x{s}.png"))
        im.resize((s * 2, s * 2), Image.LANCZOS).save(
            os.path.join(ICONSET, f"icon_{s}x{s}@2x.png"))
    try:
        subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", ICNS], check=True)
        shutil.rmtree(ICONSET)
        print(f"[ok] {os.path.relpath(ICNS, ROOT)}")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] iconutil gagal (bukan macOS?): {e}")


def main() -> None:
    im = render_svg()
    save(im, PNG1024, 1024)
    save(im, os.path.join(UI, "favicon-16.png"), 16)
    save(im, os.path.join(UI, "favicon-32.png"), 32)
    save(im, os.path.join(UI, "apple-touch-icon.png"), 180)
    shutil.copy(SVG, os.path.join(UI, "favicon.svg"))
    print("[ok] ui/favicon.svg")
    build_icns(im)


if __name__ == "__main__":
    sys.exit(main())
