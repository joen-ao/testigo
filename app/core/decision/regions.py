"""What the decision needs read from the screen, and how sure (spec 09: core
owns these; the pixel channel in app/adapters/meta fills them).

REQUIRED_REGIONS and CONFIDENCE_MIN are the knobs behind the cannot_verify
rule: if the amount, the address and the confirm button are not all read with
at least CONFIDENCE_MIN, the engine blocks.
"""

REQUIRED_REGIONS = ("amount", "address", "confirm button")
CONFIDENCE_MIN = 0.50
