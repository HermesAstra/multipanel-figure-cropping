# -*- coding: utf-8 -*-
"""
auto_edge_cleanup.py -- automatically compute which rows of the left (right) edge of a
'union image / widened crop' should be whited out.

Why it is needed: a union crop also brings in the seam between two panels, and the seam
often holds **the tail characters of a neighbouring panel's text**.
Simply 'whiting out the whole edge on every row that has ink' would also shave off **this
panel's own vertical label** (measured: the rotated y-axis label of panel h in fig5 starts
at x~1304, sharing a column with the tail characters of panel g's legend text).

Criterion (decided row by row, conservative first):

    a row has ink inside [edge, edge+w) but has **no** ink inside [edge+w, edge+w+gap)
    -> the ink of that row stops at column w, so it is an **isolated stray fragment of the
       neighbouring panel** -> white out
    otherwise (ink continues immediately to the right) -> most likely a continuous stroke of
    this panel / a vertical label -> **leave it alone**

The direction is set by --side: with left, edge = the left border of the source plate and the
right side is inside the panel; with right it is the opposite.

Usage:
  python auto_edge_cleanup.py --img <source plate> --side left --edge 1304 --y0 640 --y1 1251 \
      --w 8 --gap 8 [--out cleanup_edge.json --key fig5hi]
"""
from __future__ import annotations

import argparse
import json
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panelkit as pk  # noqa: E402


def edge_bands(mask, side, edge, y0, y1, w=8, gap=8, min_h=2):
    """Return the list of [x0, y_a, x1, y_b] rectangles to white out."""
    H, W = mask.shape
    if side == "left":
        xa, xb = max(0, edge), min(W, edge + w)
        ga, gb = min(W, edge + w), min(W, edge + w + gap)
    else:
        xa, xb = max(0, edge - w), min(W, edge)
        ga, gb = max(0, edge - w - gap), max(0, edge - w)
    strip = mask[y0:y1, xa:xb]
    guard = mask[y0:y1, ga:gb] if gb > ga else np.zeros_like(strip)
    rows = strip.any(axis=1) & (~guard.any(axis=1))
    ys = np.nonzero(rows)[0]
    if ys.size == 0:
        return []
    out, start, prev = [], ys[0], ys[0]
    for y in ys[1:]:
        if y - prev > 10:
            out.append((start, prev)); start = y
        prev = y
    out.append((start, prev))
    rects = []
    for s, e in out:
        if e - s + 1 < min_h:
            continue
        rects.append([int(xa), int(y0 + s - 2), int(xb), int(y0 + e + 3)])
    return rects


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True, help="source plate path")
    ap.add_argument("--side", choices=["left", "right"], default="left")
    ap.add_argument("--edge", type=int, required=True, help="x coordinate of the edge (left = left border, right = right border)")
    ap.add_argument("--y0", type=int, required=True)
    ap.add_argument("--y1", type=int, required=True)
    ap.add_argument("--w", type=int, default=8, help="edge band width")
    ap.add_argument("--gap", type=int, default=8, help="guard band width (this panel's strokes show up here)")
    ap.add_argument("--key", help="key name in the output JSON (panel name / union image name)")
    ap.add_argument("--out", help="output JSON path; when omitted, only print")
    a = ap.parse_args()

    mask = pk.ink(pk.load_gray(a.img))
    rects = edge_bands(mask, a.side, a.edge, a.y0, a.y1, a.w, a.gap)
    # report the removed ink amount item by item, for traceability
    for r in rects:
        x0, y0, x1, y1 = r
        n = int(mask[y0:y1, x0:x1].sum())
        print("  white-out %-24s ink %5d px (%dx%d)" % (str(r), n, x1 - x0, y1 - y0))
    print("%d segment(s) in total" % len(rects))
    if a.out:
        key = a.key or os.path.basename(a.img)
        data = {}
        if os.path.exists(a.out):
            data = json.load(open(a.out, encoding="utf-8"))
        data[key] = rects
        json.dump(data, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("written to %s (key %s)" % (a.out, key))


if __name__ == "__main__":
    main()
