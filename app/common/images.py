"""Pure image helpers shared by the core and the adapters (spec 10): cutting a
region out of a screenshot, deterministically, so its sha256 is stable."""

import io


def clamp(box, w, h):
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, x2 = sorted((max(0, min(w, x1)), max(0, min(w, x2))))
    y1, y2 = sorted((max(0, min(h, y1)), max(0, min(h, y2))))
    return [x1, y1, x2, y2]


def crop(png, box, pad=4):
    """The PNG cut to `box` (plus `pad` pixels), as PNG bytes (R7).

    Deterministic: the same pixels give the same bytes, so the sha256 of a crop
    is stable and two captures of an unchanged region hash the same (F8, F9)."""
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        w, h = im.size
        x1, y1, x2, y2 = clamp(box, w, h)
        region = im.convert("RGB").crop((max(0, x1 - pad), max(0, y1 - pad),
                                         min(w, x2 + pad), min(h, y2 + pad)))
        buf = io.BytesIO()
        region.save(buf, format="PNG", optimize=False)
        return buf.getvalue()
