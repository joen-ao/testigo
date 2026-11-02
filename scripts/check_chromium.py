"""Can Playwright start Chromium here? Run by `make setup` before the tests.

Exits 1 with what to do when it cannot, so setup stops with a clear message
instead of a wall of failing tests. Never asks for a password.
"""

from app.common import preflight


def main():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:  # noqa: BLE001
        print("\n" + (preflight.chromium_problem(e) or "Chromium could not start: %s" % e))
        return 1
    print("chromium starts: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
