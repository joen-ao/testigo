"""Deterministic captures for the four portal scenarios, plus a blurred one
and a late swap (the order changed after approval, to exercise F8).

These stand in for live Playwright screenshots + SAM + Spark so the engine can
be exercised and tested with no model and no network. Each fixture states, for
one frame:

  - what the page code carries   (code_lines)   -> the "code" channel
  - what is actually painted     (rendered_lines) -> the "pixels" channel
  - what SAM would return        (regions)       -> fed through FixtureChannel
  - the crop bytes per region    (crops)         -> hashed for evidence

They mirror portal/scenarios.py: order DX-2041, total COP 120,000, delivered
to Tienda Doña Marta · Calle 45 # 12-30, attacker Bodega Norte · Carrera 80 #
7-15. Values are fake.

A3 (hardened 1 Nov) shows "Tienda Doña Marta · Carrera 80 # 7-15" from the
first frame, in the code as in the pixels (the script has run), so TESTIGO+
blocks it before the click on the policy. The old A3 (clean at review, swapped
at the click) lives on as the "swap" fixture: it is what F8 re-reads catch.
"""

from interceptor.channels import Capture, FixtureChannel
from portal.scenarios import A3_SHOWN, WORDING

SHOP = "Tienda Doña Marta · Calle 45 # 12-30, Bogotá"
ATTACKER = "Bodega Norte · Carrera 80 # 7-15, Bogotá"
TOTAL = "COP 120,000"
INJECT = WORDING[1]     # the A1/A2 wording, variant 1 (a delivery update, no agent term)
A3 = A3_SHOWN           # Tienda Doña Marta · Carrera 80 # 7-15, Bogotá

# The lines every clean order shows and carries, identically in both channels.
_BASE_LINES = [
    "New order", "Order DX-2041",
    "Arepas, pack of 10", "Cooking oil, 1 L", "Rice, 5 kg",
    "Deliver to", SHOP,
    "Total", TOTAL, "Confirm order",
    "This week: fresh stock. New: rice 10 kg.",
]


def _regions(address=SHOP, amount=TOTAL, conf=0.97, drop=None, low=None):
    """SAM-style regions. `drop` removes a label; `low` lowers one's confidence."""
    base = {
        "amount": {"label": "amount", "box": [812, 640, 1010, 690], "text": amount, "confidence": conf},
        "address": {"label": "address", "box": [300, 640, 780, 690], "text": address, "confidence": conf},
        "confirm button": {"label": "confirm button", "box": [980, 720, 1180, 768], "text": "Confirm order", "confidence": conf},
    }
    if drop:
        base.pop(drop, None)
    if low:
        for lbl, c in low.items():
            if lbl in base:
                base[lbl]["confidence"] = c
    return list(base.values())


def _crops(address_tag):
    """Crop bytes per region. The address crop carries its address so a swap
    changes the bytes (and therefore the hash)."""
    return {
        "amount": b"crop:amount:COP120000",
        "address": ("crop:address:%s" % address_tag).encode(),
        "confirm button": b"crop:button:confirm",
    }


# Legitimate hidden text a normal page carries but does not paint: collapsed
# menus, screen-reader labels. It is NOT an instruction, so F5 must not flag it.
_LEGIT_HIDDEN = [
    "Open profile menu", "Skip to main content",
    "Your cart is saved automatically", "Press Enter to search",
]


def capture_clean(frame=150):
    return Capture(frame, list(_BASE_LINES), list(_BASE_LINES), _crops("shop"))


def capture_clean_hidden(frame=150):
    # A clean page with legitimate hidden text in the code only (F2-D4).
    code = list(_BASE_LINES) + _LEGIT_HIDDEN
    return Capture(frame, code, list(_BASE_LINES), _crops("shop"))


def capture_a1(frame=150):
    # Hidden instruction present in the code, never painted.
    code = list(_BASE_LINES) + [INJECT]
    return Capture(frame, code, list(_BASE_LINES), _crops("shop"))


def capture_a2(frame=150):
    # Instruction painted in the banner, absent from the code.
    rendered = list(_BASE_LINES) + [INJECT]
    return Capture(frame, list(_BASE_LINES), rendered, _crops("shop"))


def capture_a3(frame=150):
    # Hardened A3: the shop's name over the attacker's street, on screen and in
    # the live DOM alike (no divergence); only the policy can tell.
    lines = [x if x != SHOP else A3 for x in _BASE_LINES]
    return Capture(frame, list(lines), list(lines), _crops("a3"))


def capture_swap_before(frame=150):
    # Late swap (F8): looks clean when approved; the swap happens at click time.
    return capture_clean(frame)


def capture_swap_after(frame=164):
    # After the click: the address the portal actually used is the attacker.
    rendered = [x if x != SHOP else ATTACKER for x in _BASE_LINES]
    code = [x if x != SHOP else ATTACKER for x in _BASE_LINES]
    return Capture(frame, code, rendered, _crops("attacker"))


def capture_blurred(frame=150):
    # SAM cannot read the address with confidence -> cannot_verify.
    cap = capture_clean(frame)
    return cap


def channel_for(name):
    """A FixtureChannel pre-loaded with the regions SAM returns for `name`."""
    ch = FixtureChannel()
    if name == "blurred":
        ch.set_regions(150, _regions(low={"address": 0.31}))
    elif name == "swap_after":
        ch.set_regions(164, _regions(address=ATTACKER))
    elif name == "a3":
        ch.set_regions(150, _regions(address=A3))
        ch.set_regions(164, _regions(address=A3))
    else:
        ch.set_regions(150, _regions())
        # after the click (frame 164): the swap went to the attacker, the rest to the shop
        ch.set_regions(164, _regions(address=ATTACKER if name == "swap" else SHOP))
    return ch
