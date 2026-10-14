# -*- coding: utf-8 -*-
"""
layout_probe.py -- layout probe for a composite plate (must be run first).

Output:
  1. size and a sampled grayscale histogram (to confirm the ink threshold fits);
  2. whole-figure row separation bands (several tolerances k), plus ASCII bar charts of the
     row/column ink curves;
  3. inside the [--y0,--y1] row band, find column separation bands step by step with --xtol;
  4. the letter candidates for a given [--box x0 y0 x1 y1].

Usage examples:
  python layout_probe.py --img source_fig1.png
  python layout_probe.py --img source_fig1.png --y0 0 --y1 1489 --xtol 0 30 60
  python layout_probe.py --img source_fig1.png --box 0 0 400 400 --letters
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panelkit as pk  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True, help="source plate path")
    ap.add_argument("--thresh", type=int, default=pk.INK_THRESH)
    ap.add_argument("--minlen", type=int, default=3)
    ap.add_argument("--ytol", type=int, nargs="*", default=[0, 15, 40],
                    help="maximum ink pixels allowed in a row separation band")
    ap.add_argument("--xtol", type=int, nargs="*", default=[0, 30],
                    help="maximum ink pixels allowed in a column separation band")
    ap.add_argument("--y0", type=int); ap.add_argument("--y1", type=int)
    ap.add_argument("--bar", action="store_true", help="print the ASCII ink bar chart")
    ap.add_argument("--box", type=int, nargs=4, help="letter-candidate search region x0 y0 x1 y1")
    ap.add_argument("--letters", action="store_true")
    a = ap.parse_args()

    gray = pk.load_gray(a.img)
    m = pk.ink(gray, a.thresh)
    H, W = gray.shape
    print("== %s  %dx%d (WxH)  ink=%d (%.1f%%)  threshold<%d" %
          (os.path.basename(a.img), W, H, int(m.sum()), 100.0 * m.mean(), a.thresh))

    y0 = 0 if a.y0 is None else a.y0
    y1 = H if a.y1 is None else a.y1

    for k in a.ytol:
        seps = pk.row_seps(m, y0, y1, maxink=k, min_len=a.minlen)
        print("\n-- row separation bands y=[%d,%d) maxink<=%d:" % (y0, y1, k))
        for (s, e) in seps:
            print("     y %5d - %5d  len %4d" % (s, e, e - s + 1))
        if not seps:
            print("     (none -- meaning this row band has no blank running across the full width, so split into column blocks first)")

    for k in a.xtol:
        seps = pk.col_seps(m, 0, W, y0=y0, y1=y1, maxink=k, min_len=a.minlen)
        print("\n-- column separation bands y=[%d,%d) maxink<=%d:" % (y0, y1, k))
        for (s, e) in seps:
            print("     x %5d - %5d  len %4d" % (s, e, e - s + 1))
        if not seps:
            print("     (none -- the x window must be narrowed and searched separately)")

    if a.bar:
        print("\n-- row ink curve --")
        print(pk.bar_chart(m[y0:y1, :].sum(axis=1), base=y0))
        print("\n-- column ink curve --")
        print(pk.bar_chart(m[y0:y1, :].sum(axis=0), base=0))

    if a.letters and a.box:
        x0, y0b, x1, y1b = a.box
        print("\n-- letter candidates box=(%d,%d,%d,%d) --" % (x0, y0b, x1, y1b))
        for c in pk.letter_candidates(gray, region=(x0, y0b, x1, y1b), wrange=(4, 35)):
            print("     y %5d-%5d x %5d-%5d  h%2d w%2d n%4d dens%.2f" %
                  (c['y0'], c['y1'], c['x0'], c['x1'], c['h'], c['w'], c['n'], c['dens']))


if __name__ == "__main__":
    main()
