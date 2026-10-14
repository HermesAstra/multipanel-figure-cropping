# -*- coding: utf-8 -*-
"""
crop_panels.py -- crop panels out of a source plate according to a JSON spec (colour output).

Spec file regions.json:
{
  "source_fig1.png": {
      "fig1a":      [0, 0, 1176, 356],
      "fig1e_rna":  [0, 1510, 898, 2130]
  },
  "source_fig2.png": { "...": [x0, y0, x1, y1] }
}

Every [x0, y0, x1, y1] is a 'loose region'; the script takes the tight bbox of the actual
ink inside the region and crops that.

Two optional post-processing steps:

1) **White-out cleanup** `--cleanup cleanup.json`
   {"fig1c": [[1140, 0, 1206, 216]], ...}   the coordinates are **absolute source-plate pixels**
   Used only to white out stray fragments already confirmed to belong to a neighbouring
   panel. The script applies a safety gate first:
     - it reports, one by one, 'the number of ink pixels removed inside this rectangle' and
       the 'ink density';
     - when the density > --cleanup-max-density (default 0.12) it **refuses to run** (that
       means you are erasing content rather than a stray fragment); if you really mean to
       erase it, add --force-cleanup;
     - the record is written into the cleaned field of _rects.json, and is traced item by
       item in the report.

2) **Union crop** `--merge "fig4cd=fig4c+fig4d"` (repeatable, `+` joins the component panels)
   For when the layout needs one image 'containing two or three adjacent panels': take the
   **union of the tight bboxes** of the component panels and crop that union from the colour
   source plate. White-out of a union image also goes through --cleanup (using the union
   image name as the key).

Usage:
  python crop_panels.py --src <source plate dir> --out <output dir> --spec regions.json
                        [--cleanup cleanup.json] [--merge a=b+c ...]
                        [--pad 0] [--no-tight] [--cleanup-max-density 0.12]
                        [--force-cleanup]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panelkit as pk  # noqa: E402


def _apply_cleanup(arr, ax0, ay0, ax1, ay1, entry, mask, name, soft, hard, force, ack):
    """White out on arr (an already-cropped colour block); returns the trace list.

    entry has two forms:
      [ [x0,y0,x1,y1], ... ]                        hand-written rectangles -> goes through the density gate
      {"rects": [...], "vetted_by": "...", "reason": "..."}   tool output (already verified) -> gate waived, but the origin is recorded
    The narrow bands that the automatic tool auto_edge_cleanup.py computes with the 'guard
    band' criterion sit tight against ink and are naturally very dense, so they must go
    through the vetted channel; only hand-written rectangles need the density gate as a
    backstop.

    Two-level gate (to avoid erasing 'content' as a 'stray fragment', and to avoid silently
    changing pixels):
      density <= soft            -> white out directly, with a trace
      soft < density <= hard     -> a --cleanup-ack 'reason' is required, otherwise refuse
      density > hard             -> almost certainly a content block, refuse (unless --force-cleanup)
    Note: the ink density of a text stray-fragment area is naturally 5%-20%, so the soft
    threshold must not be set too low (default 0.30).
    """
    boxes = entry.get("rects", []) if isinstance(entry, dict) else (entry or [])
    vetted = entry.get("vetted_by") if isinstance(entry, dict) else None
    vetted_reason = entry.get("reason") if isinstance(entry, dict) else None
    cleaned = []
    for cbox in boxes:
        bx0, by0, bx1, by1 = [int(v) for v in cbox]
        sx0, sy0 = max(bx0, ax0) - ax0, max(by0, ay0) - ay0
        sx1, sy1 = min(bx1, ax1) - ax0, min(by1, ay1) - ay0
        if sx0 >= sx1 or sy0 >= sy1:
            print("   [cleanup] %s %s falls entirely outside the crop box, ignored" % (name, cbox))
            continue
        sub_mask = mask[ay0 + sy0:ay0 + sy1, ax0 + sx0:ax0 + sx1]
        removed = int(sub_mask.sum())
        density = float(sub_mask.mean()) if sub_mask.size else 0.0
        if vetted:
            pass                      # already verified by the tool (guard-band criterion), no density gate applied again
        elif density > hard and not force:
            raise RuntimeError(
                "cleanup rectangle %s has ink density %.3f above the hard limit %.2f: it is almost "
                "certainly a **content block** rather than a neighbouring-figure stray fragment.\n"
                "  Please confirm first; if you really mean to erase it, add --force-cleanup "
                "(and state the reason in the report)."
                % (cbox, density, hard))
        elif density > soft and not (force or ack):
            raise RuntimeError(
                "cleanup rectangle %s has ink density %.3f above the soft threshold %.2f: text stray "
                "fragments are usually 0.05-0.20, and anything above that needs human confirmation.\n"
                "  Once you have confirmed the region holds only neighbouring-figure stray fragments, "
                "re-run with --cleanup-ack '<reason>' (or --force-cleanup)." % (cbox, density, soft))
        arr[sy0:sy1, sx0:sx1] = 255
        rec = {"box": [bx0, by0, bx1, by1], "ink_removed": removed,
               "density": round(density, 4)}
        if vetted:
            rec["vetted_by"] = vetted
            if vetted_reason:
                rec["reason"] = vetted_reason
        elif density > soft:
            rec["ack"] = ack or ("forced" if force else None)
        cleaned.append(rec)
        tag = ("  <- %s verified%s" % (vetted, (": " + vetted_reason) if vetted_reason else "")) if vetted else (
            ("  <- confirmed: %s" % rec["ack"]) if rec.get("ack") else "")
        print("   [cleanup] %-12s white-out %-26s ink removed %6d px, density %.4f%s"
              % (name, str(cbox), removed, density, tag))
    return cleaned


def run(src_dir, out_dir, spec, pad=0, cleanup=None, merges=None,
        use_tight=True, soft_density=0.30, hard_density=0.60,
        force_cleanup=False, cleanup_ack=None, verbose=True):
    os.makedirs(out_dir, exist_ok=True)
    cleanup = cleanup or {}
    merges = merges or {}
    result = {}
    masks = {}
    for fname, panels in spec.items():
        path = os.path.join(src_dir, fname)
        gray = pk.load_gray(path)
        rgb = pk.load_rgb(path)
        m = pk.ink(gray)
        masks[fname] = m
        H, W = gray.shape
        if verbose:
            print("== %s  %dx%d" % (fname, W, H))
        for name, box in panels.items():
            x0, y0, x1, y1 = [int(v) for v in box]
            if use_tight:
                r = pk.tight_bbox(m, x0, y0, x1, y1, pad=pad)
                if r is None:
                    print("   [WARN] %s: no ink inside the region, skipped" % name)
                    continue
            else:
                r = (x0, y0, x1, y1)
            ax0, ay0, ax1, ay1 = r
            arr = rgb[ay0:ay1, ax0:ax1].copy()          # <<< colour, the only legitimate source
            cleaned = _apply_cleanup(arr, ax0, ay0, ax1, ay1, cleanup.get(name, []),
                                     m, name, soft_density, hard_density, force_cleanup, cleanup_ack)
            im = Image.fromarray(arr)
            im.save(os.path.join(out_dir, name + ".png"))
            if pk.is_grayscale(arr) and not pk.is_grayscale(rgb):
                raise RuntimeError(
                    "%s was written to disk as grayscale, but the source plate is colour -- "
                    "the output of load_gray() must have been saved" % name)
            result[name] = {
                'source': fname, 'rect': [ax0, ay0, ax1, ay1],
                'w': ax1 - ax0, 'h': ay1 - ay0,
                'norm': [round(ax0 / W, 4), round(ay0 / H, 4),
                         round(ax1 / W, 4), round(ay1 / H, 4)],
                'region': [x0, y0, x1, y1], 'cleaned': cleaned,
            }
            if verbose:
                print("   %-14s region %-24s -> rect (%4d,%4d,%4d,%4d)  %dx%d" %
                      (name, str([x0, y0, x1, y1]), ax0, ay0, ax1, ay1, ax1 - ax0, ay1 - ay0))

    # ---- Union crop: take the union of the component panels' tight rectangles, crop it from the colour source plate ----
    for out_name, parts in merges.items():
        missing = [p for p in parts if p not in result]
        if missing:
            print("   [WARN] merge %s skipped: missing component panel(s) %s" % (out_name, missing))
            continue
        fname = result[parts[0]]['source']
        rgb = pk.load_rgb(os.path.join(src_dir, fname))
        m = masks[fname]
        H, W = rgb.shape[:2]
        xs0 = min(result[p]['rect'][0] for p in parts)
        ys0 = min(result[p]['rect'][1] for p in parts)
        xs1 = max(result[p]['rect'][2] for p in parts)
        ys1 = max(result[p]['rect'][3] for p in parts)
        arr = rgb[ys0:ys1, xs0:xs1].copy()
        cleaned = _apply_cleanup(arr, xs0, ys0, xs1, ys1, cleanup.get(out_name, []),
                                 m, out_name, soft_density, hard_density, force_cleanup, cleanup_ack)
        Image.fromarray(arr).save(os.path.join(out_dir, out_name + ".png"))
        if pk.is_grayscale(arr) and not pk.is_grayscale(rgb):
            raise RuntimeError("%s was written to disk as grayscale, but the source plate is colour" % out_name)
        result[out_name] = {
            'source': fname, 'rect': [xs0, ys0, xs1, ys1],
            'w': xs1 - xs0, 'h': ys1 - ys0,
            'norm': [round(xs0 / W, 4), round(ys0 / H, 4), round(xs1 / W, 4), round(ys1 / H, 4)],
            'region': [xs0, ys0, xs1, ys1], 'cleaned': cleaned,
            'merged_from': parts,
        }
        if verbose:
            print("   %-14s MERGE %-20s -> rect (%4d,%4d,%4d,%4d)  %dx%d" %
                  (out_name, "+".join(parts), xs0, ys0, xs1, ys1, xs1 - xs0, ys1 - ys0))

    with open(os.path.join(out_dir, "_rects.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    n_clean = sum(len(v['cleaned']) for v in result.values())
    if verbose:
        print("\n%d image(s) in total (%d union image(s)) -> %s; %d white-out(s) (each recorded in _rects.json)"
              % (len(result), len(merges), out_dir, n_clean))
    return result


def parse_merges(items):
    out = {}
    for it in items or []:
        if "=" not in it or "+" not in it:
            raise SystemExit("--merge format must be out=a+b[+c], got: %s" % it)
        out_name, rhs = it.split("=", 1)
        out[out_name.strip()] = [p.strip() for p in rhs.split("+") if p.strip()]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="source plate directory")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--spec", required=True, help="regions.json")
    ap.add_argument("--cleanup", help="cleanup.json (optional, white-out cleanup)")
    ap.add_argument("--merge", action="append", default=[],
                    help='union crop, repeatable: --merge "fig4cd=fig4c+fig4d"')
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--no-tight", action="store_true", help="use the given region directly, do not shrink to the tight bbox")
    ap.add_argument("--cleanup-soft-density", type=float, default=0.30,
                    help="soft ink-density threshold for a white-out region: above it --cleanup-ack must state a reason (default 0.30)")
    ap.add_argument("--cleanup-hard-density", type=float, default=0.60,
                    help="hard ink-density limit: above it the run is refused outright, it is almost certainly content (default 0.60)")
    ap.add_argument("--cleanup-ack", default=None,
                    help="reason confirming the white-out (required when the density exceeds the soft threshold; recorded in _rects.json)")
    ap.add_argument("--force-cleanup", action="store_true",
                    help="white out even though the density exceeds the limit (the reason must already be stated in the report)")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    cleanup = json.load(open(a.cleanup, encoding="utf-8")) if a.cleanup else {}
    run(a.src, a.out, spec, pad=a.pad, cleanup=cleanup, merges=parse_merges(a.merge),
        use_tight=not a.no_tight, soft_density=a.cleanup_soft_density,
        hard_density=a.cleanup_hard_density, force_cleanup=a.force_cleanup,
        cleanup_ack=a.cleanup_ack)


if __name__ == "__main__":
    main()
