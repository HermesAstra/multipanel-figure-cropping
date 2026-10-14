# -*- coding: utf-8 -*-
"""
audit_crops.py -- automated first-pass audit of crop results (**does not replace looking at every image**).

For every image in _rects.json it reports:
  1. colour  -- whether the finished product is grayscale while the source plate is colour
                (the most common fatal error);
  2. letter  -- 'panel letter' candidates (small bold glyphs) in the top-left region of the
                crop, to confirm the letter is inside the box;
  3. edge    -- the amount of ink in the 8px band **outside** each of the four edges. A large
                amount of ink outside = either you cut off your own content, or a neighbouring
                panel sits right there; when the value is large it must be explained in the
                report (usually a trade-off of a staggered layout);
  4. cleanup -- the white-out records made for this image (coordinates / how much ink was
                removed / whether the force switch was triggered). An image with a white-out
                must map item by item into the report, otherwise it counts as 'silently
                changing pixels'.
  5. merged  -- whether the image came from the union of several panels (a union image must
                state its components in the report).

Usage: python audit_crops.py --src <source plate dir> --out <crop dir> [--edge 8] [--edge-warn 50]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panelkit as pk  # noqa: E402


def audit(src_dir, out_dir, edge=8, band=0.30, edge_warn=50):
    recs = json.load(open(os.path.join(out_dir, "_rects.json"), encoding="utf-8"))
    cache = {}
    bad = 0
    cleaned_total = 0
    forced = 0
    flagged = []            # [(panel name, max outside ink, [sides over the threshold])]
    print("%-14s %-22s %-6s %-30s %s" %
          ("panel", "rect(x0,y0,x1,y1)", "colour", "letter candidates", "outside ink (L/T/R/B)"))
    print("-" * 112)
    for name, r in recs.items():
        src = os.path.join(src_dir, r['source'])
        if src not in cache:
            cache[src] = (pk.load_gray(src), pk.load_rgb(src))
        gray, rgb = cache[src]
        x0, y0, x1, y1 = r['rect']
        arr = rgb[y0:y1, x0:x1]
        gray_ok = "colour" if not pk.is_grayscale(arr) else (
            "gray(plate gray)" if pk.is_grayscale(rgb) else "!!GRAY!!")
        if gray_ok == "!!GRAY!!":
            bad += 1
        h, w = gray.shape
        reg = (x0, y0, x0 + max(40, int((x1 - x0) * band)), y0 + max(40, int((y1 - y0) * band)))
        cand = pk.letter_candidates(gray, region=reg, wrange=(4, 35))
        letters = ",".join("%s@(%d,%d)" % (("w%d h%d" % (c['w'], c['h'])), c['x0'], c['y0'])
                           for c in cand[:4]) or "-"
        m = pk.ink(gray)
        left = int(m[y0:y1, max(0, x0 - edge):x0].sum())
        right = int(m[y0:y1, x1:min(w, x1 + edge)].sum())
        top = int(m[max(0, y0 - edge):y0, x0:x1].sum())
        bot = int(m[y1:min(h, y1 + edge), x0:x1].sum())
        tag = ""
        if r.get('merged_from'):
            tag += " [UNION:%s]" % "+".join(r['merged_from'])
        cl = r.get('cleaned') or []
        if cl:
            cleaned_total += len(cl)
        warn = ""
        if edge_warn > 0:
            sides = [s for s, v in (("L", left), ("T", top), ("R", right), ("B", bot))
                     if v >= edge_warn]
            if sides:
                warn = "  << re-check the inside"
                flagged.append((name, max(left, top, right, bot), sides))
        print("%-14s (%4d,%4d,%4d,%4d)  %-6s %-30s %5d/%5d/%5d/%5d%s%s" %
              (name, x0, y0, x1, y1, gray_ok, letters, left, top, right, bot, tag, warn))
        for c in cl:
            forced += 1 if c.get('forced') else 0
            print("               +- white-out %-26s ink removed %6d px  density %.4f%s"
                  % (str(c['box']), c['ink_removed'], c['density'],
                     "  <- forced (density over limit)" if c.get('forced') else ""))
    print("-" * 112)
    print("grayscale products: %d (should be 0)" % bad)
    print("white-out records: %d (%d of them forced) -- every one must have its coordinates and reason stated in the crop report" %
          (cleaned_total, forced))
    if edge_warn > 0:
        if flagged:
            print("WARN re-check the inside: %d edge(s) have outside ink >= %d px -- ink outside means "
                  "'the neighbour's stuff crossed the boundary you drew', and it often **also reaches "
                  "inside the box** (an isolated letter in a corner, half an axis label, the tail of a "
                  "legend):"
                  % (len(flagged), edge_warn))
            for nm, outer, sides in sorted(flagged, key=lambda t: -t[1]):
                print("     %-14s %s max outside %d px" % (nm, "/".join(sides), outer))
        else:
            print("re-check the inside: 0 edge(s) (outside ink < %d px on every edge)" % edge_warn)
    print('Hint 1: outside ink >0 is not necessarily wrong, but for every edge marked << re-check the inside, '
          'you must first look at the **inside** of that same edge for neighbouring-figure fragments that '
          'seeped in, and only then write the explanation.')
    print('Hint 2: this script can only check "is there ink outside the box"; it cannot tell whether that ink '
          'is a neighbouring-figure stray fragment or your own label being cut off. Looking at every image '
          'remains a mandatory step.')
    print('Hint 3: the threshold --edge-warn (default 50 px, set 0 to disable); the larger the value the more '
          'suspicious, and even a few tens of px deserves a look.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--edge", type=int, default=8)
    ap.add_argument("--edge-warn", type=int, default=50,
                    help="once the ink in the 8px band outside an edge reaches this value the edge is marked re-check the inside; set 0 to disable (default 50 px)")
    a = ap.parse_args()
    audit(a.src, a.out, edge=a.edge, edge_warn=a.edge_warn)


if __name__ == "__main__":
    main()
