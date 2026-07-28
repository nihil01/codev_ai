from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

CREAM = (255, 254, 252, 255)
KEYLIME = (225, 244, 223, 255)
SAGE = (177, 219, 184, 255)
SLATE = (182, 206, 213, 255)
FOREST = (15, 62, 23, 255)


def make_base(size: int, maskable: bool = False) -> Image.Image:
    scale = size / 512
    image = Image.new("RGBA", (size, size), CREAM)
    draw = ImageDraw.Draw(image)

    outer_margin = int((56 if maskable else 34) * scale)
    outer_radius = int(92 * scale)
    draw.rounded_rectangle(
        (outer_margin, outer_margin, size - outer_margin, size - outer_margin),
        radius=outer_radius,
        fill=KEYLIME,
    )

    line_width = max(2, int(20 * scale))
    center_x = size // 2
    draw.line(
        (center_x, int(390 * scale), center_x, int(205 * scale)),
        fill=FOREST,
        width=line_width,
    )

    left_leaf = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    left_draw = ImageDraw.Draw(left_leaf)
    left_draw.ellipse(
        (int(125 * scale), int(105 * scale), int(280 * scale), int(255 * scale)),
        fill=SAGE,
        outline=FOREST,
        width=line_width,
    )
    left_leaf = left_leaf.rotate(-28, center=(center_x, center_x), resample=Image.Resampling.BICUBIC)
    image.alpha_composite(left_leaf)

    right_leaf = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    right_draw = ImageDraw.Draw(right_leaf)
    right_draw.ellipse(
        (int(235 * scale), int(155 * scale), int(390 * scale), int(305 * scale)),
        fill=SLATE,
        outline=FOREST,
        width=line_width,
    )
    right_leaf = right_leaf.rotate(28, center=(center_x, center_x), resample=Image.Resampling.BICUBIC)
    image.alpha_composite(right_leaf)

    draw = ImageDraw.Draw(image)
    draw.line(
        (int(190 * scale), int(405 * scale), int(322 * scale), int(405 * scale)),
        fill=FOREST,
        width=line_width,
    )
    return image


def save_png(path: Path, size: int, maskable: bool = False) -> None:
    make_base(size, maskable=maskable).save(path, "PNG", optimize=True)


save_png(PUBLIC / "pwa-192x192.png", 192)
save_png(PUBLIC / "pwa-512x512.png", 512)
save_png(PUBLIC / "pwa-maskable-512x512.png", 512, maskable=True)
save_png(PUBLIC / "apple-touch-icon.png", 180)

favicon_sizes = [16, 32, 48]
favicon_images = [make_base(size) for size in favicon_sizes]
favicon_images[0].save(
    PUBLIC / "favicon.ico",
    sizes=[(size, size) for size in favicon_sizes],
    append_images=favicon_images[1:],
)

for filename in (
    "pwa-192x192.png",
    "pwa-512x512.png",
    "pwa-maskable-512x512.png",
    "apple-touch-icon.png",
    "favicon.ico",
):
    print(PUBLIC / filename)
