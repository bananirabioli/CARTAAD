"""Code-drawn placeholder images for the demo image bank (stand-ins for real archive photos)."""

import io
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 1200, 800


def _sky(draw: ImageDraw.ImageDraw, top: tuple[int, int, int], bottom: tuple[int, int, int], height: int) -> None:
    for y in range(height):
        k = y / max(1, height - 1)
        draw.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))


def _road(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    draw.polygon([(W * 0.42, H * 0.45), (W * 0.58, H * 0.45), (W, H), (0, H)], fill=color)


def _buildings(draw: ImageDraw.ImageDraw, rnd: random.Random) -> None:
    x = 0
    while x < W:
        w = rnd.randint(90, 180)
        h = rnd.randint(120, 260)
        shade = rnd.randint(150, 200)
        draw.rectangle([x, H * 0.45 - h, x + w, H * 0.45], fill=(shade, shade - 10, shade - 25))
        for wy in range(int(H * 0.45 - h + 15), int(H * 0.45 - 20), 40):
            for wx in range(x + 12, x + w - 20, 34):
                draw.rectangle([wx, wy, wx + 16, wy + 22], fill=(90, 110, 130))
        x += w + rnd.randint(4, 20)


def _finish(img: Image.Image, label: str) -> bytes:
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, H - 34, W, H], fill=(20, 20, 20))
    draw.text((14, H - 26), f"PLACEHOLDER DE DEMO · {label}", fill=(235, 235, 235))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def street(kind: str, seed: int, label: str) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _sky(draw, (150, 185, 215), (215, 228, 238), int(H * 0.45))
    _buildings(draw, rnd)
    _road(draw, (78, 78, 82) if kind == "after" else (105, 100, 95))
    if kind == "before":
        for _ in range(26):
            cx, cy = rnd.randint(150, W - 150), rnd.randint(int(H * 0.55), H - 60)
            r = rnd.randint(14, 46)
            draw.ellipse([cx - r * 1.6, cy - r * 0.6, cx + r * 1.6, cy + r * 0.6], fill=(55, 50, 45))
        for _ in range(30):
            x1, y1 = rnd.randint(100, W - 100), rnd.randint(int(H * 0.5), H - 40)
            draw.line([(x1, y1), (x1 + rnd.randint(-80, 80), y1 + rnd.randint(-30, 30))], fill=(60, 58, 55), width=3)
    else:
        for y in range(int(H * 0.5), H, 60):
            k = (y - H * 0.45) / (H * 0.55)
            draw.rectangle([W / 2 - 4 - 6 * k, y, W / 2 + 4 + 6 * k, y + 28 * k + 8], fill=(240, 220, 120))
    if kind == "crew":
        for i in range(3):
            x = 380 + i * 170
            draw.rectangle([x, 470, x + 60, 600], fill=(240, 120, 30))
            draw.ellipse([x + 10, 420, x + 50, 460], fill=(230, 190, 150))
    return _finish(img, label)


def scene(kind: str, seed: int, label: str) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    if kind == "patrol":
        _sky(draw, (120, 140, 170), (200, 210, 225), int(H * 0.5))
        _buildings(draw, rnd)
        _road(draw, (85, 85, 90))
        draw.rounded_rectangle([380, 470, 820, 620], 30, fill=(245, 245, 245))
        draw.rectangle([450, 420, 740, 480], fill=(40, 60, 120))
        draw.rectangle([560, 405, 640, 422], fill=(200, 40, 40))
        for x in (460, 740):
            draw.ellipse([x - 40, 590, x + 40, 670], fill=(30, 30, 30))
    elif kind == "lights":
        _sky(draw, (20, 30, 60), (60, 70, 110), H)
        _road(draw, (55, 55, 60))
        for i in range(6):
            x = 120 + i * 190
            draw.rectangle([x, 260, x + 10, 620], fill=(150, 150, 150))
            draw.ellipse([x - 30, 230, x + 40, 280], fill=(255, 245, 200))
            draw.polygon([(x - 60, 620), (x + 70, 620), (x + 5, 280)], fill=(90, 90, 70))
    elif kind == "pipe":
        _sky(draw, (170, 190, 205), (220, 225, 230), int(H * 0.4))
        draw.rectangle([0, H * 0.4, W, H], fill=(140, 110, 80))
        draw.rectangle([0, 470, W, 560], fill=(70, 110, 170))
        for _ in range(14):
            x, y = rnd.randint(500, 700), rnd.randint(380, 470)
            draw.ellipse([x, y, x + 18, y + 30], fill=(120, 180, 230))
        draw.rectangle([520, 440, 680, 590], outline=(240, 120, 30), width=10)
    elif kind == "bridge":
        _sky(draw, (150, 190, 225), (225, 235, 240), int(H * 0.6))
        draw.rectangle([0, H * 0.6, W, H], fill=(110, 140, 110))
        draw.rectangle([0, 380, W * 0.76, 430], fill=(170, 170, 170))
        for x in range(60, int(W * 0.76), 160):
            draw.rectangle([x, 430, x + 36, H * 0.75], fill=(150, 150, 150))
        draw.line([(W * 0.76, 380), (W * 0.9, 300)], fill=(240, 180, 40), width=10)
        draw.rectangle([W * 0.88, 250, W * 0.9, 600], fill=(240, 180, 40))
    elif kind == "park":
        _sky(draw, (150, 200, 235), (220, 235, 245), int(H * 0.5))
        draw.rectangle([0, H * 0.5, W, H], fill=(110, 170, 90))
        for _ in range(9):
            x, y = rnd.randint(40, W - 80), rnd.randint(int(H * 0.45), int(H * 0.7))
            draw.rectangle([x + 24, y + 60, x + 40, y + 140], fill=(110, 80, 50))
            draw.ellipse([x - 20, y - 20, x + 84, y + 80], fill=(60, 130 + rnd.randint(0, 40), 60))
        draw.rectangle([480, 600, 720, 640], fill=(160, 110, 70))
    return _finish(img, label)


def illustration(kind: str, seed: int, label: str) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", (W, H), (244, 239, 230))
    draw = ImageDraw.Draw(img)
    palette = [(52, 76, 120), (226, 150, 80), (120, 170, 150), (210, 90, 90), (240, 200, 90)]
    if kind == "street":
        draw.rectangle([0, 500, W, H], fill=(90, 95, 110))
        for x in range(0, W, 140):
            draw.rectangle([x + 40, 640, x + 110, 660], fill=(240, 230, 200))
        for i in range(5):
            x = 80 + i * 230
            h = rnd.randint(200, 330)
            draw.rectangle([x, 500 - h, x + 170, 500], fill=palette[i % 5])
    else:
        for i in range(5):
            x = 120 + i * 210
            color = palette[i % 5]
            draw.ellipse([x, 260, x + 110, 370], fill=(230, 195, 160))
            draw.rounded_rectangle([x - 20, 380, x + 130, 640], 50, fill=color)
    return _finish(img, label)
