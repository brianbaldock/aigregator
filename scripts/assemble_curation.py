#!/usr/bin/env python3
"""
assemble_curation.py — deterministic, no-LLM merge of batched curation fragments
into the single /tmp/aig/curation.json that curate.py --validate and write_digest.py
expect.

WHY THIS EXISTS
The curation step is the only large model-authored artifact in the pipeline: a
per-URL overlay for ~80-90 items, totaling ~85KB of JSON. Writing that in ONE
streamed model response repeatedly timed out at the provider (e.g. the 2026-06-16
run: three consecutive stream-exhausted errors on the single big curation write,
killing the digest before publish). The fix is to have the agent emit the curation
in small batches, each its own modest write_file, and assemble them here
deterministically. No single model response is large enough to time out.

INPUT (all under --indir, default /tmp/aig):
  curation_head.json        required. {"subtitle": str, "tldr_order": [url,...],
                            "tldr_blurbs": {url: str, ...}}
  curation_items_*.json     one or more. Each a flat dict {url: {title, summary,
                            themes, section}}. Globbed and merged in sorted order.
                            Later files do NOT silently clobber an earlier url;
                            a duplicate url is a warning and keeps the first.

OUTPUT:
  curation.json             {subtitle, tldr_order, tldr_blurbs, items} — exactly
                            the shape curate.py validate() and write_digest.py read.

Run AFTER writing the head + all item batches, BEFORE curate.py --validate:
  python scripts/assemble_curation.py
  python scripts/curate.py --validate --in /tmp/aig/curation.json --items /tmp/aig/digest_items.json
"""
from __future__ import annotations
import argparse, glob, json, os, sys


def assemble(indir: str) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    head_path = os.path.join(indir, "curation_head.json")
    if not os.path.exists(head_path):
        print(f"[assemble] FAIL: head file not found: {head_path}", file=sys.stderr)
        sys.exit(2)
    try:
        head = json.load(open(head_path))
    except json.JSONDecodeError as e:
        print(f"[assemble] FAIL: head file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    subtitle = head.get("subtitle") or ""
    tldr_order = head.get("tldr_order") or []
    tldr_blurbs = head.get("tldr_blurbs") or {}
    if not subtitle.strip():
        warnings.append("head has empty subtitle")
    if not tldr_order:
        warnings.append("head has empty tldr_order")

    frag_paths = sorted(glob.glob(os.path.join(indir, "curation_items_*.json")))
    if not frag_paths:
        print(f"[assemble] FAIL: no curation_items_*.json fragments in {indir}",
              file=sys.stderr)
        sys.exit(2)

    items: dict = {}
    for fp in frag_paths:
        try:
            frag = json.load(open(fp))
        except json.JSONDecodeError as e:
            print(f"[assemble] FAIL: fragment {os.path.basename(fp)} is not valid JSON: {e}",
                  file=sys.stderr)
            sys.exit(2)
        if not isinstance(frag, dict):
            warnings.append(f"fragment {os.path.basename(fp)} is not a dict, skipped")
            continue
        n_new = 0
        for url, overlay in frag.items():
            if url in items:
                warnings.append(f"duplicate url across fragments (kept first): {url[:70]}")
                continue
            items[url] = overlay
            n_new += 1
        print(f"[assemble] {os.path.basename(fp)}: +{n_new} item(s)", file=sys.stderr)

    curation = {
        "subtitle": subtitle,
        "tldr_order": tldr_order,
        "tldr_blurbs": tldr_blurbs,
        "items": items,
    }
    return curation, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="/tmp/aig")
    ap.add_argument("--out", default=None,
                    help="Output path (default: <indir>/curation.json)")
    args = ap.parse_args()

    curation, warnings = assemble(args.indir)
    out_path = args.out or os.path.join(args.indir, "curation.json")
    with open(out_path, "w") as f:
        json.dump(curation, f, ensure_ascii=False, indent=2)

    for w in warnings:
        print(f"[assemble] warn: {w}", file=sys.stderr)
    print(f"[assemble] OK: wrote {out_path} — subtitle {'ok' if curation['subtitle'].strip() else 'EMPTY'}, "
          f"{len(curation['tldr_order'])} tldr, {len(curation['items'])} item overlays "
          f"from {len(sorted(glob.glob(os.path.join(args.indir, 'curation_items_*.json'))))} fragment(s)")


if __name__ == "__main__":
    main()
