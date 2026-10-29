"""Browser driver: what the agent observes and what actually executes.

The loop never touches a browser directly. It drives a `BrowserDriver`;
`observe()` returns an interceptor `Capture` (code channel + pixel channel +
crops), the same object the interceptor checks.

The real driver is Playwright (F3). The offline test double lives in
tests/fixtures/fake_agent.py and is never used outside tests.
"""

SUPPLIER_ACCT = "310-XXX-4417"
ATTACKER_ACCT = "300-XXX-0000"


class BrowserDriver:
    is_test_double = False

    def observe(self):                      # pragma: no cover - interface
        raise NotImplementedError

    def pixel_channel(self):                # pragma: no cover - interface
        raise NotImplementedError

    def execute(self, action):              # pragma: no cover - interface
        raise NotImplementedError

    def observe_after(self):                # pragma: no cover - interface
        raise NotImplementedError

    @property
    def last_payment(self):                 # pragma: no cover - interface
        raise NotImplementedError


class PlaywrightDriver(BrowserDriver):   # pragma: no cover - needs a browser (F3)
    """Real driver over a Chromium page. Shape only until F3.

      observe()        -> screenshot + DOM text + crops, as a Capture
      pixel_channel()  -> a SamSparkChannel over the live screenshot
      execute(action)  -> perform the click/type on the page
      observe_after()  -> re-screenshot after the click
    """

    def __init__(self, page, pixel_channel):
        self.page = page
        self._pixels = pixel_channel

    def observe(self):
        raise NotImplementedError("F3: Playwright page -> Capture")

    def pixel_channel(self):
        return self._pixels

    def execute(self, action):
        raise NotImplementedError("F3: perform the action on the page")

    def observe_after(self):
        raise NotImplementedError("F3: re-screenshot after the click")
