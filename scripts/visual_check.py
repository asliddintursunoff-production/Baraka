"""Dev tool: screenshot app pages and the matching design/ pages at 1440 px and 390 px.

Usage (app must be running, e.g. `make up` or uvicorn on another port):
    backend/.venv/bin/python scripts/visual_check.py [BASE_URL] [page ...]
Screenshots go to visual_out/ (gitignored). Uses the system Google Chrome (no download).
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "visual_out"
PAGES = {"main": ("/", "Main.html"), "forecast": ("/forecast", "Forecast.html"),
         "calendar": ("/calendar", "Calendar.html"), "chat": ("/chat", "Chat.html"),
         "live": ("/live", "Live.html"), "knowledge": ("/knowledge", "Knowledge.html"),
         "sources": ("/sources", "Sources.html"), "connect": ("/onboarding/connect", "Connect.html")}
WIDTHS = (1440, 390)


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    wanted = sys.argv[2:] or ["main", "forecast", "calendar"]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(f"{base}/login")
            page.fill("input[type=email]", "demo@demo.uz")
            page.fill("input[type=password]", "demo12345")
            page.click("button[type=submit]")
            page.wait_for_url(f"{base}/")
            for name in wanted:
                path, design = PAGES[name]
                page.goto(f"{base}{path}")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(600)
                page.screenshot(path=str(OUT / f"{name}-app-{width}.png"), full_page=True)
                # horizontal overflow check (spec §7: nothing breaks at 390 px)
                overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                print(f"{name:<10} {width}px  page-overflow={overflow}px")
                dpage = ctx.new_page()
                dpage.goto((ROOT / "design" / "pages" / design).as_uri())
                dpage.wait_for_timeout(800)
                dpage.screenshot(path=str(OUT / f"{name}-design-{width}.png"), full_page=True)
                dpage.close()
            ctx.close()
        browser.close()
    print(f"screenshots in {OUT}")


if __name__ == "__main__":
    main()
