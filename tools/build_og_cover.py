#!/usr/bin/env python3
"""Bake docs/assets/og-cover.jpg: a 1200x630 social card in the site's palette.

Why this exists: og:image was the 1024x1024 square logo at 1.5MB. Platforms
crop or letterbox a square card, and 1.5MB is a slow fetch for a preview. The
recurring defect this fixes is "existence is not correctness" -- a gate that
only checks the file exists reports green on a card that previews badly
everywhere.

Output contract (enforced by scripts/verify_seo.py):
  1200x630 (1.91:1), progressive JPEG, well under 200KB.

Rendered in the site's own terminal palette (phosphor green on black) so the
preview looks native rather than like a generic logo drop.
"""

from __future__ import annotations

import pathlib
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - environment problem, must be loud
    sys.exit("FAIL: Pillow is required to build the OG card (pip install Pillow)")

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Straight from docs/assets/base.css :root
BG = (0, 0, 0)
GREEN = (0, 255, 65)
GREEN_DIM = (0, 143, 23)
AMBER = (255, 176, 0)

W, H = 1200, 630

MONO_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]
MONO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def pick(candidates: list[str], size: int):
    for c in candidates:
        if pathlib.Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _draw_card(
    d: "ImageDraw.ImageDraw",
    prompt: str,
    wordmark: str,
    headline: str,
    subline: str,
) -> None:
    """Render the shared card furniture onto a prepared canvas."""
    # Faint scanlines: the site's terminal texture, cheap to encode.
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 18, 4), width=1)

    # Border, inset, matching --border.
    d.rectangle([28, 28, W - 29, H - 29], outline=GREEN_DIM, width=2)

    x = 80
    d.text((x, 120), prompt, font=pick(MONO, 34), fill=GREEN_DIM)
    d.text((x, 200), wordmark, font=pick(MONO_BOLD, 96), fill=GREEN)
    d.line([(x, 330), (W - 80, 330)], fill=GREEN_DIM, width=2)
    d.text((x, 366), headline, font=pick(MONO_BOLD, 46), fill=GREEN)
    d.text((x, 430), subline, font=pick(MONO, 34), fill=GREEN_DIM)
    d.text((x, 505), "aigregator.news", font=pick(MONO, 30), fill=AMBER)

    # Blinking-cursor block, bottom right. Purely decorative.
    d.rectangle([W - 118, 505, W - 92, 537], fill=GREEN)


CARDS = {
    "og-cover.jpg": {
        "prompt": "$ aigregator --today",
        "wordmark": "AIGREGATOR",
        "headline": "Daily AI news digest",
        "subline": "scored, clustered and cited",
    },
    "og-cover-weekly.jpg": {
        "prompt": "$ aigregator --weekly",
        "wordmark": "AIGREGATOR",
        "headline": "Weekly AI roundup",
        "subline": "the week's through line, every Sunday",
    },
}


def main() -> int:
    failures = []
    for filename, spec in CARDS.items():
        card = Image.new("RGB", (W, H), BG)
        _draw_card(ImageDraw.Draw(card), **spec)

        out = DOCS / "assets" / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        card.save(out, "JPEG", quality=86, optimize=True, progressive=True)

        size = out.stat().st_size
        print(f"wrote {out.relative_to(ROOT)} {card.size} {size:,} bytes")
        if size > 200_000:
            failures.append(f"{filename} exceeds the 200KB budget ({size:,}B)")

    for f in failures:
        print(f"FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
