"""Screenshot UI (desktop + mobile) untuk verifikasi visual. Hanya alat bantu pengembangan."""

import asyncio
import os
import sys

from playwright.async_api import async_playwright

OUT = os.path.join(os.path.dirname(__file__), "..", ".data", "shots")
URL = "http://127.0.0.1:8777"


async def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # desktop
        page = await browser.new_page(viewport={"width": 1280, "height": 820})
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_selector(".seg", timeout=15000)
        await page.wait_for_timeout(600)
        await page.screenshot(path=os.path.join(OUT, "desktop.png"))

        # mobile
        m = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                   is_mobile=True, has_touch=True)
        await m.goto(URL, wait_until="networkidle")
        await m.wait_for_selector(".seg", timeout=15000)
        await m.wait_for_timeout(600)
        await m.screenshot(path=os.path.join(OUT, "mobile.png"))

        # drawer terbuka
        await m.click("#drawerBtn")
        await m.wait_for_timeout(400)
        await m.screenshot(path=os.path.join(OUT, "mobile-drawer.png"))

        # tab dokumen di mobile
        await m.evaluate("closeDrawer()")
        await m.wait_for_timeout(300)
        await m.click('.tab[data-tab="epics"]')
        await m.wait_for_timeout(400)
        await m.screenshot(path=os.path.join(OUT, "mobile-epics.png"))

        # ukur apakah panel kanan benar-benar terlihat
        info = await m.evaluate("""() => {
            const el = document.querySelector('#artifactPane');
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            return {top: Math.round(r.top), height: Math.round(r.height),
                    width: Math.round(r.width), display: cs.display, overflow: cs.overflowY,
                    viewportH: window.innerHeight};
        }""")
        print("artifactPane:", info)

        sizes = await m.evaluate("""() => {
            const q = (s) => { const e = document.querySelector(s); if (!e) return null;
                const r = e.getBoundingClientRect(); return {t: Math.round(r.top), h: Math.round(r.height)}; };
            return {mbar: q('.mbar'), topbar: q('.topbar'), split: q('.split'),
                    transcript: q('.pane.transcript'), artifact: q('#artifactPane')};
        }""")
        print("layout:", sizes)

        await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
