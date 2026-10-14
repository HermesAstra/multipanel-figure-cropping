# -*- coding: utf-8 -*-
"""
panelkit -- panel localisation and cropping toolkit for multi-panel composite
figures (journal figures).

Depends only on numpy + PIL (no scipy / OpenCV / scikit-image).

Design points (every one of them bought with a mistake):
  * **Geometry measurement runs on grayscale, but the finished product written to
    disk must be colour.** `load_gray()` is only for projection / bbox / letter
    localisation; `load_rgb()` is the only data source allowed to be written to a
    file. Confusing the two hands over a whole set of grayscale images.
  * A composite plate is usually 'staggered', so **there is no blank band running
    through the whole figure**, and the work must therefore be layered:
    whole-figure row bands -> column blocks inside a row band -> row bands inside a
    column block -> take the tight bbox of each block.
  * A separation band is often not 'zero ink' but '<= a certain number of ink
    pixels'. Use the `maxink` tolerance instead of a hard equality with 0.
  * The panel letter is the strongest criterion, but **i / j / l are narrow
    glyphs**, so an area threshold misses them and minpix must be relaxed.
"""
from __future__ import annotations

import os
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None

INK_THRESH = 246          # grayscale < INK_THRESH counts as ink (measured to fit Nature composite plates)
LEV = " .:-=+*#%@"


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_gray(path) -> np.ndarray:
    """Grayscale array: **only for geometry measurement**."""
    return np.asarray(Image.open(path).convert("L"), dtype=np.uint8)


def load_rgb(path) -> np.ndarray:
    """Colour array: **the only legitimate source for a crop written to disk**."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


def ink(a: np.ndarray, thresh: int = INK_THRESH) -> np.ndarray:
    """Boolean ink mask."""
    return a < thresh


def is_grayscale(arr: np.ndarray) -> bool:
    """Test whether an image has R==G==B (i.e. 'looks like a grayscale image')."""
    a = np.asarray(arr).astype(np.int16)
    return bool((a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all())


# --------------------------------------------------------------------------- #
# 1-D projection
# --------------------------------------------------------------------------- #
def bands(mask_1d: np.ndarray, min_len: int = 1):
    """Runs of consecutive True -> [(start, end_exclusive), ...]."""
    out, i, n = [], 0, len(mask_1d)
    while i < n:
        if mask_1d[i]:
            j = i
            while j < n and mask_1d[j]:
                j += 1
            if j - i >= min_len:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out


def row_seps(m, y0, y1, x0=None, x1=None, maxink=0, min_len=3):
    """'Nearly blank' row bands inside a region (absolute coordinates)."""
    x0 = 0 if x0 is None else x0
    x1 = m.shape[1] if x1 is None else x1
    cnt = m[y0:y1, x0:x1].sum(axis=1)
    return [(y0 + a, y0 + b - 1) for a, b in bands(cnt <= maxink, min_len)]


def col_seps(m, x0, x1, y0=None, y1=None, maxink=0, min_len=3):
    """'Nearly blank' column bands inside a region (absolute coordinates)."""
    y0 = 0 if y0 is None else y0
    y1 = m.shape[0] if y1 is None else y1
    cnt = m[y0:y1, x0:x1].sum(axis=0)
    return [(x0 + a, x0 + b - 1) for a, b in bands(cnt <= maxink, min_len)]


def content_spans(n, seps):
    """Derive the content spans [(start, end_exclusive), ...] from a separation-band list."""
    out, cur = [], 0
    for (s, e) in seps:
        if s > cur:
            out.append((cur, s))
        cur = max(cur, e + 1)
    if cur < n:
        out.append((cur, n))
    return out


# --------------------------------------------------------------------------- #
# Tight bounding box
# --------------------------------------------------------------------------- #
def tight_bbox(m, x0, y0, x1, y1, pad=0):
    """Tight bounding box of the actual ink inside a region (absolute coordinates, y1/x1 exclusive). Returns None for an empty region."""
    sub = m[y0:y1, x0:x1]
    rows = np.where(sub.any(axis=1))[0]
    cols = np.where(sub.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    ax0, ax1 = x0 + int(cols[0]), x0 + int(cols[-1]) + 1
    ay0, ay1 = y0 + int(rows[0]), y0 + int(rows[-1]) + 1
    ax0 = max(0, ax0 - pad); ay0 = max(0, ay0 - pad)
    ax1 = min(m.shape[1], ax1 + pad); ay1 = min(m.shape[0], ay1 + pad)
    return (int(ax0), int(ay0), int(ax1), int(ay1))


def best_x(m, y0, y1, xa, xb, halfw=3, weight=None):
    """Find a vertical split line inside [xa, xb]: the one with the least ink in a half-width window. Returns (x, ink).

    weight: optional boolean/weight vector of length H, used to count only the rows of
    interest (e.g. to exclude figure-level connector lines).
    """
    seg = m[y0:y1]
    best = None
    for x in range(xa, xb + 1):
        sl = seg[:, max(0, x - halfw):x + halfw + 1]
        v = int(sl.sum()) if weight is None else int((sl * weight[:, None]).sum())
        if best is None or v < best[1]:
            best = (x, v)
    return best


def best_y(m, x0, x1, ya, yb, halfw=3):
    """Find a horizontal split line inside [ya, yb]. Returns (y, ink)."""
    seg = m[:, x0:x1]
    best = None
    for y in range(ya, yb + 1):
        v = int(seg[max(0, y - halfw):y + halfw + 1, :].sum())
        if best is None or v < best[1]:
            best = (y, v)
    return best


# --------------------------------------------------------------------------- #
# Panel letter detection (a bold lowercase letter is an isolated, dense, dark connected component)
# --------------------------------------------------------------------------- #
def components(mask: np.ndarray, minpix=60, maxpix=4000):
    """8-neighbour connected components (pure numpy/queue implementation, to avoid scipy)."""
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    comps = []
    for (y, x) in np.argwhere(mask):
        if seen[y, x]:
            continue
        q = deque([(int(y), int(x))])
        seen[y, x] = True
        pts = []
        while q:
            cy, cx = q.popleft()
            pts.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
        if minpix <= len(pts) <= maxpix:
            ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
            comps.append({'y0': min(ys), 'y1': max(ys) + 1, 'x0': min(xs), 'x1': max(xs) + 1,
                          'n': len(pts)})
    return comps


def letter_candidates(gray: np.ndarray, th=110, hrange=(18, 50), wrange=(4, 35),
                      dens_min=0.40, minpix=60, maxpix=2500, region=None):
    """Candidate panel letters. **The lower bound of wrange must be lowered to 4~6**, otherwise i / j / l are missed.

    region=(x0,y0,x1,y1) can restrict the search range (usually a corner of the plate).
    """
    mask = gray < th
    if region:
        x0, y0, x1, y1 = region
        sub = np.zeros_like(mask)
        sub[y0:y1, x0:x1] = mask[y0:y1, x0:x1]
        mask = sub
    out = []
    for c in components(mask, minpix, maxpix):
        h = c['y1'] - c['y0']; w = c['x1'] - c['x0']
        d = c['n'] / float(h * w)
        if hrange[0] <= h <= hrange[1] and wrange[0] <= w <= wrange[1] and d >= dens_min:
            c['h'], c['w'], c['dens'] = h, w, round(d, 2)
            out.append(c)
    out.sort(key=lambda c: (c['y0'], c['x0']))
    return out


# --------------------------------------------------------------------------- #
# Visualization / diagnostics
# --------------------------------------------------------------------------- #
def bar_chart(cnt: np.ndarray, base: int = 0, width: int = 200, out=None):
    """Compress a 1-D ink curve into an ASCII bar chart; the most direct way to locate separation bands by eye."""
    lines = []
    mx = max(1, int(cnt.max()))
    for start in range(0, len(cnt), width):
        seg = cnt[start:start + width]
        s = ""
        for v in seg:
            if v == 0:
                s += " "
            else:
                s += LEV[max(1, min(9, int(round(9 * (v / mx) ** 0.25))))]
        lines.append("%6d|%s|" % (base + start, s))
    txt = "\n".join(lines)
    if out:
        open(out, "w", encoding="utf-8").write(txt)
    return txt


def grid_overlay(gray_or_rgb: np.ndarray, x0, y0, x1, y1, step=50, scale=1.0,
                 label_every=2, color=False):
    """Overlay an absolute-coordinate grid on a region, so coordinates can be read straight off a viewed image. Returns a PIL.Image."""
    im = Image.fromarray(gray_or_rgb[y0:y1, x0:x1])
    if not color:
        im = im.convert("RGB")
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.NEAREST)
    d = ImageDraw.Draw(im)
    w, h = im.size
    sx, sy = w / (x1 - x0), h / (y1 - y0)
    xs = ((x0 // step) + 1) * step
    while xs < x1:
        px = (xs - x0) * sx
        major = (xs % (step * label_every) == 0)
        d.line([(px, 0), (px, h)], fill=(255, 0, 0) if major else (255, 190, 190), width=1)
        if major:
            d.text((px + 2, 2), str(xs), fill=(255, 0, 0))
        xs += step
    ys = ((y0 // step) + 1) * step
    while ys < y1:
        py = (ys - y0) * sy
        major = (ys % (step * label_every) == 0)
        d.line([(0, py), (w, py)], fill=(0, 0, 255) if major else (190, 190, 255), width=1)
        if major:
            d.text((2, py + 2), str(ys), fill=(0, 0, 255))
        ys += step
    return im
