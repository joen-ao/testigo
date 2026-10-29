"""Capture and the pixel channel: the two inputs the decision engine compares.

The engine never talks to a browser or a model directly. It takes a `Capture`
(what the page code says + a screenshot) and a `PixelChannel` (what the pixels
show, via SAM + Spark). Both are interfaces, so the same decision logic runs
against:

  - real captures from Playwright + real SAM 3.1 / Spark   (SamSparkChannel)
  - deterministic fixtures, for tests and the offline demo (FixtureChannel)

This separation is also the honesty of the design: the pixel channel is
independent of the DOM, so text the page hides or paints can never reach the
engine pre-labelled as safe.

REQUIRED_REGIONS and CONFIDENCE_MIN are the knobs behind the cannot_verify
rule: if SAM cannot find amount, recipient and the pay button with at least
CONFIDENCE_MIN, the engine blocks.
"""

import hashlib

REQUIRED_REGIONS = ("amount", "recipient", "pay button")
CONFIDENCE_MIN = 0.50


def sha_crop(data):
    """sha256 over the crop bytes — the same hash used in approval and receipt."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def short(h):
    return "%s…%s" % (h[:4], h[-2:])


class Capture:
    """One frame: the screenshot plus the text the page code carries.

    code_lines   every text line present in the page code, rendered or not
                 (so A1's hidden instruction is here).
    rendered_lines  every text line actually painted to the screen, including
                 text painted inside images (so A2's banner line is here) and
                 NOT including anything the page hides.
    crops        label -> bytes of the cropped PNG for that region, used for
                 hashing the approved and executed evidence.
    """

    def __init__(self, frame, code_lines, rendered_lines, crops, screenshot=b"", ts=None):
        self.frame = frame
        self.code_lines = [_norm(x) for x in code_lines]
        self.rendered_lines = [_norm(x) for x in rendered_lines]
        self.crops = crops or {}
        self.screenshot = screenshot
        self.ts = ts

    def sha(self):
        return sha_crop(self.screenshot or ("frame-%s" % self.frame))


def _norm(s):
    return " ".join(str(s).split()).strip()


class PixelChannel:
    """Reads a screenshot and returns labelled regions with text + confidence.

    Returns a list of dicts: {"label", "box", "text", "confidence"}. Must cover
    REQUIRED_REGIONS when they are present and readable; a region it cannot find
    with confidence is either omitted or returned with a low confidence, and the
    engine turns that into cannot_verify.
    """

    def read_regions(self, capture):  # pragma: no cover - interface
        raise NotImplementedError


class FixtureChannel(PixelChannel):
    """A pixel channel backed by regions baked into the fixture.

    The fixture author states exactly what SAM would return for each scenario,
    so the demo and tests are deterministic and need no model.
    """

    def __init__(self):
        self._by_frame = {}

    def set_regions(self, frame, regions):
        self._by_frame[frame] = regions

    def read_regions(self, capture):
        return list(self._by_frame.get(capture.frame, []))


class SamSparkChannel(PixelChannel):
    """Real pixel channel: SAM 3.1 for regions, Spark 1.3 to read each crop.

    Not wired to live endpoints here (no network in this build). The shape is
    fixed so plugging the APIs in later does not touch the engine. Any failure
    — no endpoint, low score, unreadable crop — must come back as a low
    confidence so the engine blocks with cannot_verify rather than guessing.
    """

    def __init__(self, sam=None, spark=None, confidence_min=CONFIDENCE_MIN):
        self.sam = sam        # callable(screenshot) -> [{"label","box","score"}]
        self.spark = spark    # callable(crop_bytes) -> str
        self.confidence_min = confidence_min

    def read_regions(self, capture):
        if self.sam is None or self.spark is None:
            # No model available: refuse to vouch for anything.
            return []
        out = []
        try:
            boxes = self.sam(capture.screenshot)
        except Exception:
            return []
        for b in boxes:
            try:
                text = self.spark(_crop(capture.screenshot, b["box"]))
            except Exception:
                text, b_score = "", 0.0
                out.append({"label": b.get("label", "?"), "box": b.get("box", [0, 0, 0, 0]),
                            "text": text, "confidence": 0.0})
                continue
            out.append({"label": b.get("label", "?"), "box": b.get("box", [0, 0, 0, 0]),
                        "text": text, "confidence": float(b.get("score", 0.0))})
        return out


def _crop(screenshot, box):  # pragma: no cover - placeholder for the real crop
    """Where a real build would crop the PNG to `box` and return PNG bytes."""
    return screenshot
