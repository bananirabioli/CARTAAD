"""Image helpers for manual captures."""

import io

from PIL import Image, ImageFilter


def blur_names(data: bytes, band_ratio: float = 0.16) -> bytes:
    """Blur the header band of a social-media screenshot, where page and commenter names usually appear,
    plus the left avatar/name column of the lower half (comment area)."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    regions = [(0, 0, w, max(1, int(h * band_ratio))), (0, int(h * 0.62), max(1, int(w * 0.38)), h)]
    for box in regions:
        crop = img.crop(box).filter(ImageFilter.GaussianBlur(radius=max(8, w // 60)))
        img.paste(crop, box)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def normalize_image(data: bytes, max_side: int = 1600) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue(), "image/png"
