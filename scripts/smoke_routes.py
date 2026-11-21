"""Route smoke test: every public, app and onboarding page renders text without a JS error.

Usage: backend/.venv/bin/python scripts/smoke_routes.py [BASE_URL]   (default http://localhost:8000)
Never opens /live and never sends a chat message (no real Gemini calls).
"""

from __future__ import annotations

import sys

from playwright.sync_api import Page, sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PUBLIC = ["/", "/pricing", "/login", "/register"]
APP = [
    "/dashboard",
    "/chat",
    "/forecast",
    "/calendar",
    "/knowledge",
    "/sources",
    "/onboarding/business",
    "/onboarding/connect",
    "/onboarding/analyzing",
]
EMAIL, PASSWORD = "demo@demo.uz", "demo12345"


def check(page: Page, path: str, errors: list[str]) -> bool:
    errors.clear()
    try:
        page.goto(BASE + path, wait_until="domcontentloaded", timeout=15_000)
        page.wait_for_function(
            "document.body && document.body.innerText.trim().length > 0", timeout=10_000
        )
        page.wait_for_timeout(800)  # let lazy chunks and first queries settle
        text = page.inner_text("body").strip()
    except Exception as exc:  # noqa: BLE001 - report every failure as one line
        print(f"FAIL {path}: {type(exc).__name__}: {str(exc).splitlines()[0]}")
        return False
    landed = page.url.removeprefix(BASE)
    if errors:
        print(f"FAIL {path} -> {landed}: pageerror: {errors[0]}")
        return False
    if not text:
        print(f"FAIL {path} -> {landed}: no visible text")
        return False
    print(f"ok   {path} -> {landed}")
    return True


def main() -> int:
    ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        for path in PUBLIC:
            ok = check(page, path, errors) and ok

        page.goto(BASE + "/login", wait_until="domcontentloaded")
        page.fill("#email", EMAIL)
        page.fill("#pw", PASSWORD)
        page.click("button[type=submit]")
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)
            print(f"ok   login -> {page.url.removeprefix(BASE)}")
        except Exception:  # noqa: BLE001
            print("FAIL login: still on /login")
            ok = False

        for path in APP:
            ok = check(page, path, errors) and ok

        browser.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
