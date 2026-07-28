from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

BLUE = (20, 90, 255)
BLUE_2 = (59, 130, 246)
INK = (2, 5, 32)
WHITE = (255, 255, 255)
SOFT = (240, 244, 254)


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def rounded_rect(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def make_base(size: int, maskable: bool = False) -> Image.Image:
    scale = size / 512
    img = Image.new("RGBA", (size, size), SOFT)

    # Soft diagonal brand gradient.
    px = img.load()
    assert px is not None
    for y in range(size):
        for x in range(size):
            t = (x + y) / (size * 2)
            r = int(252 * (1 - t) + 232 * t)
            g = int(252 * (1 - t) + 239 * t)
            b = int(252 * (1 - t) + 255 * t)
            px[x, y] = (r, g, b, 255)

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Background blue glow.
    glow_margin = int(44 * scale) if maskable else int(24 * scale)
    d.ellipse(
        (glow_margin, int(30 * scale), size - glow_margin, size - int(42 * scale)),
        fill=(20, 90, 255, 38),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(int(28 * scale)))
    img.alpha_composite(layer)

    d = ImageDraw.Draw(img)

    # Main app tile. Maskable icon keeps content safely inside center ~70%.
    margin = int(104 * scale) if maskable else int(62 * scale)
    tile = (margin, margin, size - margin, size - margin)
    radius = int((76 if maskable else 86) * scale)

    # Shadow.
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (tile[0], tile[1] + int(18 * scale), tile[2], tile[3] + int(18 * scale)),
        radius=radius,
        fill=(3, 14, 50, 52),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(20 * scale)))
    img.alpha_composite(shadow)

    # Tile gradient.
    tile_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(tile, radius=radius, fill=255)
    tile_px = tile_img.load()
    assert tile_px is not None
    for y in range(tile[1], tile[3]):
        for x in range(tile[0], tile[2]):
            t = (y - tile[1]) / max(1, (tile[3] - tile[1]))
            r = int(BLUE_2[0] * (1 - t) + BLUE[0] * t)
            g = int(BLUE_2[1] * (1 - t) + BLUE[1] * t)
            b = int(BLUE_2[2] * (1 - t) + BLUE[2] * t)
            tile_px[x, y] = (r, g, b, 255)
    tile_img.putalpha(mask)
    img.alpha_composite(tile_img)

    # CRM chat bubble motif.
    bubble_w = int(188 * scale) if maskable else int(230 * scale)
    bubble_h = int(132 * scale) if maskable else int(160 * scale)
    bx = size // 2 - bubble_w // 2
    by = size // 2 - bubble_h // 2 - int(8 * scale)
    rounded_rect(d, (bx, by, bx + bubble_w, by + bubble_h), int(38 * scale), WHITE)

    # Chat tail.
    tail = [
        (bx + int(62 * scale), by + bubble_h - int(6 * scale)),
        (bx + int(42 * scale), by + bubble_h + int(42 * scale)),
        (bx + int(100 * scale), by + bubble_h - int(12 * scale)),
    ]
    d.polygon(tail, fill=WHITE)

    # AI text.
    font = load_font(int((86 if maskable else 104) * scale), bold=True)
    text = "AI"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((size // 2 - tw // 2, by + bubble_h // 2 - th // 2 - int(5 * scale)), text, font=font, fill=BLUE)

    # Small CRM dots.
    dot_y = by + bubble_h + int(56 * scale)
    dot_r = int(9 * scale)
    for dx, alpha in [(-34, 220), (0, 255), (34, 220)]:
        cx = size // 2 + int(dx * scale)
        d.ellipse((cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r), fill=(255, 255, 255, alpha))

    return img


def save_png(path: Path, size: int, maskable: bool = False) -> None:
    img = make_base(size, maskable=maskable)
    img.save(path, "PNG", optimize=True)


save_png(PUBLIC / "pwa-192x192.png", 192)
save_png(PUBLIC / "pwa-512x512.png", 512)
save_png(PUBLIC / "pwa-maskable-512x512.png", 512, maskable=True)
save_png(PUBLIC / "apple-touch-icon.png", 180)

# Multi-size favicon.ico for browsers.
favicon_sizes = [16, 32, 48]
favicon_images = [make_base(size).convert("RGBA") for size in favicon_sizes]
favicon_images[0].save(PUBLIC / "favicon.ico", sizes=[(s, s) for s in favicon_sizes], append_images=favicon_images[1:])

for file in [
    "pwa-192x192.png",
    "pwa-512x512.png",
    "pwa-maskable-512x512.png",
    "apple-touch-icon.png",
    "favicon.ico",
]:
    print(PUBLIC / file)
