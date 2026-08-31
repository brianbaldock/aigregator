#!/usr/bin/env python3
"""Numerically verify the baked OG card actually rendered.

My model cannot view images, and "the file exists and has the right dimensions"
is exactly the false-green this whole fix is about. A card whose fonts silently
failed to load would still be 1200x630 and still be ~97KB of scanlines.

So: assert there are real bright-phosphor text pixels, that they sit in the
left/mid bands where the wordmark is drawn, and that the amber URL line exists.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "docs" / "assets" / "og-cover.jpg"


def main() -> int:
    if not CARD.exists():
        print(f"FAIL: {CARD} does not exist")
        return 1

    im = Image.open(CARD).convert("RGB")
    W, H = im.size
    px = im.load()
    step = 3
    sampled = len(range(0, H, step)) * len(range(0, W, step))

    bright = amber = 0
    bands = {"left": 0, "mid": 0, "right": 0}
    for y in range(0, H, step):
        for x in range(0, W, step):
            r, g, b = px[x, y]
            if g > 150 and r < 120:
                bright += 1
                if x < 400:
                    bands["left"] += 1
                elif x < 800:
                    bands["mid"] += 1
                else:
                    bands["right"] += 1
            if r > 180 and 120 < g < 210 and b < 80:
                amber += 1

    print(f"card {im.size}  sampled {sampled} px")
    print(f"  bright green : {bright} ({100 * bright / sampled:.2f}%)")
    print(f"  amber        : {amber} ({100 * amber / sampled:.2f}%)")
    for k, v in bands.items():
        print(f"  band {k:<6}: {v}")

    problems = []
    if bright < 500:
        problems.append("card looks blank - fonts likely failed to load")
    if bands["left"] < 100:
        problems.append("no text in the left band where the wordmark is drawn")
    if amber < 20:
        problems.append("amber URL line missing")

    if problems:
        for p in problems:
            print(f"FAIL: {p}")
        return 1

    print("OK: card has real rendered content")
    return 0


if __name__ == "__main__":
    sys.exit(main())
