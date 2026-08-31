#!/usr/bin/env python3
"""Sabotage harness for the og:image + JSON-LD checks in verify_seo.py.

A green gate proves nothing until it has been watched failing. This injects each
defect class the new checks are supposed to catch, asserts the gate FAILS, and
restores the tree byte-identically.

Critically it also asserts the CLEAN tree passes first, and treats a no-op
injection (sabotage that changed no bytes) as HARNESS BROKEN rather than as a
catch -- otherwise a typo'd pattern silently "passes" every case.

Run from the repo root:  ./.venv/bin/python tools/sabotage_seo_gate.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
GATE = ROOT / "scripts" / "verify_seo.py"
PY = ROOT / ".venv" / "bin" / "python"

INDEX = DOCS / "index.html"
CARD = DOCS / "assets" / "og-cover.jpg"


def run_gate() -> tuple[int, str]:
    p = subprocess.run(
        [str(PY), str(GATE)], capture_output=True, text=True, cwd=ROOT
    )
    return p.returncode, (p.stdout + p.stderr)


def case(name: str, mutate, restore) -> bool:
    """Apply a mutation, assert the gate fails, restore. True if the gate caught it."""
    before = INDEX.read_bytes(), CARD.read_bytes()
    changed = mutate()
    after = INDEX.read_bytes(), CARD.read_bytes()

    if before == after and changed is not False:
        print(f"  HARNESS BROKEN: {name!r} changed nothing -- pattern did not match")
        restore()
        return False

    code, out = run_gate()
    restore()

    if code == 0:
        print(f"  MISSED: {name} -- gate still passed")
        return False
    print(f"  caught: {name}")
    return True


def main() -> int:
    if not PY.exists():
        return print(f"FAIL: {PY} not found") or 1

    backup = pathlib.Path(tempfile.mkdtemp(prefix="seo-sabotage-"))
    shutil.copy2(INDEX, backup / "index.html")
    shutil.copy2(CARD, backup / "og-cover.jpg")

    def restore():
        shutil.copy2(backup / "index.html", INDEX)
        shutil.copy2(backup / "og-cover.jpg", CARD)

    try:
        code, out = run_gate()
        if code != 0:
            print("FAIL: clean tree does not pass -- fix that before sabotaging")
            print(out[-1500:])
            return 1
        print("clean tree passes\n")

        results = []

        def drop(pattern: str):
            def m():
                t = INDEX.read_text(encoding="utf-8")
                if pattern not in t:
                    return False
                INDEX.write_text(t.replace(pattern, "", 1), encoding="utf-8")
            return m

        results.append(case(
            "og:image:width removed",
            drop('<meta property="og:image:width" content="1200">'), restore))

        results.append(case(
            "og:image:alt removed",
            drop('<meta property="og:image:alt"'), restore))

        def wrong_dims():
            t = INDEX.read_text(encoding="utf-8")
            INDEX.write_text(
                t.replace('og:image:height" content="630"',
                          'og:image:height" content="9999"', 1),
                encoding="utf-8")
        results.append(case("declared height != real height", wrong_dims, restore))

        def square_card():
            from PIL import Image
            Image.new("RGB", (1200, 1200), (0, 0, 0)).save(
                CARD, "JPEG", quality=80)
        results.append(case("card swapped for a 1:1 square", square_card, restore))

        def fat_card():
            from PIL import Image
            import random
            im = Image.new("RGB", (1200, 630))
            px = im.load()
            random.seed(1)
            for y in range(630):
                for x in range(1200):
                    px[x, y] = (random.randint(0, 255),) * 3
            im.save(CARD, "JPEG", quality=100)
        results.append(case("card inflated past the byte budget", fat_card, restore))

        def strip_ld():
            t = INDEX.read_text(encoding="utf-8")
            import re
            new = re.sub(
                r'<script type="application/ld\+json">.*?</script>', "", t,
                flags=re.S)
            if new == t:
                return False
            INDEX.write_text(new, encoding="utf-8")
        results.append(case("all JSON-LD stripped from index", strip_ld, restore))

        def break_ld():
            t = INDEX.read_text(encoding="utf-8")
            i = t.index('<script type="application/ld+json">')
            INDEX.write_text(t[:i + 34] + "{not json," + t[i + 34:], encoding="utf-8")
        results.append(case("malformed JSON-LD", break_ld, restore))

        def twitter_drift():
            t = INDEX.read_text(encoding="utf-8")
            INDEX.write_text(
                t.replace('name="twitter:image" content="https://aigregator.news/assets/og-cover.jpg"',
                          'name="twitter:image" content="https://aigregator.news/assets/stale.png"', 1),
                encoding="utf-8")
        results.append(case("twitter:image drifted from og:image", twitter_drift, restore))

        code, _ = run_gate()
        print(f"\nclean tree passes again after restore: {code == 0}")

        caught = sum(results)
        print(f"\n{caught}/{len(results)} defect classes caught")
        return 0 if (caught == len(results) and code == 0) else 1
    finally:
        restore()
        shutil.rmtree(backup, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
