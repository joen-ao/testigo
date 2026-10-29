"""Print versions and check that a portal capture is exactly 1280x800.

Also says which variables are set (names only, never values).
"""

import importlib.metadata as md
import io
import platform
import sys
import threading
from http.server import ThreadingHTTPServer

from common import config

VIEWPORT = {"width": 1280, "height": 800}


def browser_context_options():
    """The shared, measurable browser setup (F0 §9)."""
    return dict(viewport=VIEWPORT, device_scale_factor=1, reduced_motion="reduce",
                locale="en-US", timezone_id="America/Bogota")


def main():
    ok = True
    print("python      ", sys.version.split()[0], platform.platform())
    for pkg in ("openai", "playwright", "fastapi", "uvicorn", "cryptography", "pillow", "pytest"):
        try:
            print("%-12s %s" % (pkg, md.version(pkg)))
        except md.PackageNotFoundError:
            print("%-12s MISSING" % pkg)
            ok = False

    print("\nenv (set / empty):")
    for name, is_set in config.configured(config.MODEL_VARS + ("SCORER_TOKEN",)).items():
        print("  %-18s %s" % (name, "set" if is_set else "empty"))

    from portal import server as portal_server
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), portal_server.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        from playwright.sync_api import sync_playwright
        from PIL import Image
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            print("\nchromium    ", browser.version)
            ctx = browser.new_context(**browser_context_options())
            page = ctx.new_page()
            page.goto("http://127.0.0.1:%d/orders/new?scenario=clean" % port)
            png = page.screenshot()
            browser.close()
        size = Image.open(io.BytesIO(png)).size
        good = size == (VIEWPORT["width"], VIEWPORT["height"])
        print("capture      %dx%d %s" % (size[0], size[1], "OK" if good else "WRONG (want 1280x800)"))
        ok = ok and good
    except Exception as e:  # noqa: BLE001
        print("\nbrowser check failed: %s: %s" % (type(e).__name__, e))
        ok = False
    finally:
        httpd.shutdown()

    print("\ndoctor:", "OK" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
