"""Generate the application icon (assets/icon.png and assets/icon.ico).

Usage:  python assets/make_icon.py        (needs only Pillow: pip install pillow)

The design: a dark rounded square, a coral heart, and a slash cutting through it.
It is drawn at 1024 px and scaled down, which keeps the edges smooth at every size.
"""

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SIZE = 1024
OUT_DIR = Path(__file__).resolve().parent

BACKGROUND_TOP = (62, 48, 150)  # deep indigo
BACKGROUND_BOTTOM = (16, 16, 40)  # near black
HEART_TOP = (255, 143, 163)  # soft coral
HEART_BOTTOM = (255, 45, 90)  # vivid red-pink
SLASH_COLOR = (255, 255, 255)

SLASH_START = (772, 226)
SLASH_END = (252, 812)
SLASH_WIDTH = 44
GAP_WIDTH = 104  # the heart is cut a bit wider than the slash, leaving a clean gap


def vertical_gradient(top, bottom, y_start=0, y_end=SIZE):
    """A SIZE x SIZE image going from ``top`` at y_start to ``bottom`` at y_end."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    mask.paste(255, (0, y_end, SIZE, SIZE))
    ramp = Image.linear_gradient("L").resize((SIZE, y_end - y_start))
    mask.paste(ramp, (0, y_start))
    return Image.composite(
        Image.new("RGB", (SIZE, SIZE), bottom), Image.new("RGB", (SIZE, SIZE), top), mask
    )


def heart_points(cx, cy, width, steps=360):
    """Outline of a heart (classic parametric curve) centred on (cx, cy)."""
    k = width / 32.0
    points = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        points.append((cx + k * x, cy - k * (y + 2.5)))
    return points


def thick_line_mask(start, end, width):
    """A mask with a straight line that has rounded ends."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw.line([start, end], fill=255, width=width)
    radius = width / 2
    for x, y in (start, end):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=255)
    return mask


def build_icon() -> Image.Image:
    # Rounded square background with a soft highlight in the top-left corner
    background = vertical_gradient(BACKGROUND_TOP, BACKGROUND_BOTTOM).convert("RGBA")
    shape = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(shape).rounded_rectangle([40, 40, SIZE - 40, SIZE - 40], radius=230, fill=255)

    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse([-200, -260, 700, 460], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    background = Image.composite(
        Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255)), background, glow
    )

    # Heart: soft shadow, gradient fill, then the slash cut out of it
    heart_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(heart_mask).polygon(heart_points(512, 520, 600), fill=255)

    shadow = heart_mask.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.45))
    shadow = ImageChops.offset(shadow, 0, 26)
    background = Image.composite(Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255)), background, shadow)

    gap = thick_line_mask(SLASH_START, SLASH_END, GAP_WIDTH)
    heart_visible = ImageChops.subtract(heart_mask, gap)
    heart_fill = vertical_gradient(HEART_TOP, HEART_BOTTOM, 250, 790).convert("RGBA")
    background = Image.composite(heart_fill, background, heart_visible)

    slash = thick_line_mask(SLASH_START, SLASH_END, SLASH_WIDTH)
    background = Image.composite(Image.new("RGBA", (SIZE, SIZE), SLASH_COLOR + (255,)), background, slash)

    background.putalpha(shape)
    return background


def main() -> None:
    icon = build_icon()
    icon.resize((256, 256), Image.LANCZOS).save(OUT_DIR / "icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(OUT_DIR / "icon.ico", sizes=sizes)
    print("Wrote", OUT_DIR / "icon.png", "and", OUT_DIR / "icon.ico")


if __name__ == "__main__":
    main()
