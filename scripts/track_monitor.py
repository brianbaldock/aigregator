#!/usr/bin/env python3
"""Track the monitor corners across every frame of bedroom-ambient.mp4.

Reads the 4 corner percentages from monitor-corners.json (picked manually
via /scene/?pick), converts to pixels at frame 0, then uses Lucas-Kanade
optical flow to track those points frame-by-frame. For each frame, fits
an affine transform from the frame-0 corners to the current corners and
emits a JSON timeline that the BBS app reads at runtime.

The CSS overlay applies (base 4-point matrix3d warp) composed with
(per-frame affine delta) so the overlay tracks the monitor as it drifts.

Usage:
    python scripts/track_monitor.py \\
        --video docs/scene/video/bedroom-ambient.mp4 \\
        --corners docs/bbs/data/monitor-corners.json \\
        --out docs/bbs/monitor-track.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def load_corners_pct(path: Path) -> np.ndarray:
    """Load 4 corner percentages, return (4,2) float array in TL,TR,BR,BL order."""
    data = json.loads(path.read_text())
    return np.array(
        [data["tl"], data["tr"], data["br"], data["bl"]],
        dtype=np.float32,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--corners", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--mode", choices=["affine", "homography"], default="affine")
    args = ap.parse_args()

    if not args.video.exists():
        print(f"ERROR: video not found: {args.video}", file=sys.stderr)
        return 1

    corners_pct = load_corners_pct(args.corners)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        print(f"ERROR: cannot open video: {args.video}", file=sys.stderr)
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 16.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"video: {width}x{height} @ {fps:.2f} fps, {frame_count} frames")

    # Convert corner percentages to pixel coords
    corners_px = corners_pct.copy()
    corners_px[:, 0] *= width / 100.0
    corners_px[:, 1] *= height / 100.0
    corners_0 = corners_px.reshape(-1, 1, 2).astype(np.float32)

    print(f"frame-0 corners (px):\n{corners_px}")

    # Read frame 0
    ok, frame0 = cap.read()
    if not ok:
        print("ERROR: cannot read frame 0", file=sys.stderr)
        return 1
    gray_prev = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)
    pts_prev = corners_0.copy()

    # Output: per-frame transform parameters.
    # CSS matrix() takes 6 values: a,b,c,d,e,f  →  [[a,c,e],[b,d,f],[0,0,1]]
    # For mode=affine we emit those 6 directly.
    # For mode=homography we emit 9 values (matrix3d-ready).
    frames_out = []

    # Frame 0 is identity (the "base" position).
    if args.mode == "affine":
        frames_out.append({"t": 0.0, "m": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]})
    else:
        frames_out.append({"t": 0.0, "m": [1, 0, 0, 0, 1, 0, 0, 0, 1]})

    lk_params = dict(
        winSize=(31, 31),
        maxLevel=4,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    frame_idx = 1
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        pts_cur, status, _ = cv2.calcOpticalFlowPyrLK(
            gray_prev, gray, pts_prev, None, **lk_params
        )
        # Defensive: if any point is lost, snap to prev (motion is tiny,
        # so this is safe).
        if pts_cur is None or status is None or status.sum() < 4:
            pts_cur = pts_prev

        # Solve transform from corners_0 → pts_cur. We want the transform
        # that maps the base corners (frame 0) to the current corners.
        src = corners_0.reshape(-1, 2)
        dst = pts_cur.reshape(-1, 2)

        if args.mode == "affine":
            m, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
            if m is None:
                m = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
            # CSS matrix(a,b,c,d,e,f) where
            # x' = a*x + c*y + e
            # y' = b*x + d*y + f
            # cv2 affine matrix is [[a c e][b d f]]
            a, c, e = m[0]
            b, d, f = m[1]
            frames_out.append(
                {
                    "t": frame_idx / fps,
                    "m": [
                        float(a),
                        float(b),
                        float(c),
                        float(d),
                        float(e),
                        float(f),
                    ],
                }
            )
        else:
            h, _ = cv2.findHomography(src, dst, cv2.RANSAC)
            if h is None:
                h = np.eye(3)
            frames_out.append(
                {
                    "t": frame_idx / fps,
                    "m": [float(v) for v in h.flatten().tolist()],
                }
            )

        gray_prev = gray
        pts_prev = pts_cur
        frame_idx += 1

    cap.release()

    payload = {
        "video": str(args.video),
        "fps": float(fps),
        "frame_count": frame_idx,
        "width": width,
        "height": height,
        "mode": args.mode,
        "base_corners_pct": {
            "tl": corners_pct[0].tolist(),
            "tr": corners_pct[1].tolist(),
            "br": corners_pct[2].tolist(),
            "bl": corners_pct[3].tolist(),
        },
        "frames": frames_out,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {args.out} ({frame_idx} frames, mode={args.mode})")

    # Sanity check: print a sample mid-frame
    sample = frames_out[len(frames_out) // 2]
    print(f"sample frame t={sample['t']:.3f}: m={sample['m']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
