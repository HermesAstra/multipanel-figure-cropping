# examples — worked example measured on 2026-10-06 (directly reproducible)

Source: the Fig.1–Fig.5 composite plates of *Nature Communications* 17:6975 (2026) (CC BY);
the source plates are `source_fig1.png` … `source_fig5.png` (the official versions downloaded
from Springer Nature MediaObjects).

| File | Contents |
|---|---|
| `regions_fig1-5.json` | Loose regions for 54 panels (`tight_bbox` tightens them automatically) |
| `cleanup_fig1-5.json` | The white-outs actually performed: 4 single-panel corners + 7 narrow bands on the left edge of fig5hi |
| `run_example.sh` | Reproduce every crop with a single command (including the 3 union crops) |
| `regions_nature2025_9573.json` | Second real-world set: the **16 panels** of Nature 2025 (`41586_2025_9573`) Fig.1/2/6 (WebP source plates, staggered layout) |
| `cleanup_nature2025_9573.json` | The 5 white-outs of that set (density 0.05–0.26, none forced) |

## Reproduction

```bash
python ../scripts/crop_panels.py \
  --src <source plate directory> --out <output directory> \
  --spec regions_fig1-5.json \
  --cleanup cleanup_fig1-5.json \
  --merge "fig4cd=fig4c+fig4d" --merge "fig4jk=fig4j+fig4k" --merge "fig5hi=fig5h+fig5i+fig5j"
python ../scripts/audit_crops.py --src <source plate directory> --out <output directory>
```

## How these white-outs were decided (important)

1. **Stray fragments in a single panel's corner** (fig1c / fig1d / fig2i): the rectangle was already
   correct, but the top-left corner had picked up rotated text fragments from the neighbouring panel.
   Measured: apart from the fragment, that corner holds no ink of this panel → safe to white out.
   **2026-10-08 reproduction-verification correction**: for fig1c the right bound of the white-out was
   pulled in from 1206 to **1198** — the letter `c` starts at x1198, and the old value over-cut by 8
   columns, shaving 41% of the ink off its own letter (292→173 px); for fig2i the left bound of the
   white-out was pulled in from 405 to **420** — the letter `i` sits at x411–417, and the old value
   erased the upper half of its own letter (210→105 px), while the fragments in that band that
   **actually belong to the neighbouring figure amount to only 69 px**. Lesson: **a white-out
   rectangle must first be compared once against the bbox of the panel letter inside it; any
   intersection is an error** — the density gate does not react to this kind of mistake at all (the
   densities here are only 0.049 / 0.011).
2. **Widen first, white out second** (fig3i): to avoid cutting off its own "Mesenchymal", the right
   boundary had to be relaxed from 953 to 985, and doing so pulls the neighbouring panel's letter `j`
   into the box → so that letter is then whited out. The order and the reason must be written into the
   report.
   **2026-10-08 reproduction-verification correction**: the glyph of letter `j` extends all the way to
   y≈721 (hook included), so the white-out box was changed from `[948,679,985,716]` to
   `[948,676,985,726]`; otherwise 47 px of the hook's residual stroke stays inside the box. A
   white-out box must **keep a 3–5 px margin around the measured bbox of the object being erased**; do
   not guess it from the row-band boundary.
3. **Union-crop edges** (fig4cd / fig4jk / fig5hi): the union crop also swallows the seam between the
   two panels. Do **not** "white out the whole edge by inked rows" — measured, the ink on the left
   edge of fig4cd/fig4jk continues to the right and is their own rotated axis label, so whiting it out
   would wrongly delete their own content (fig4cd would wrongly delete 114 px, fig4jk 35 px). Use the
   **guard-band criterion** of `auto_edge_cleanup.py`: only when [edge, edge+w) holds ink while
   [edge+w, edge+w+gap) holds none does it count as a neighbouring-figure stray fragment. On that
   basis fig4cd/fig4jk should be 0 segments, and fig5hi needs only 7 narrow bands (266 px in total)
   rather than 8 segments along the whole edge (about 876 px).

## Partitioning and boundaries (added during 2026-10-08 reproduction verification)

**A boundary must never cut through the middle of a line of text.** The `No` / `Yes` axis label of
fig5h spans y893–925 vertically, while the old spec placed the h/i boundary at y918/919: as a result h
lost the lower half of the label and the **top** of i pulled that half-cut text in. Measured on the
source plate, h's label ends at y922 and i's panel letter starts at y924 — placing the boundary at
**923** leaves both sides complete (in `regions_fig1-5.json` the lower edge of fig5h and the upper edge
of fig5i have been changed to 923 accordingly). The **density gate cannot detect this kind of error
either** (the residual text density is extremely low); the criterion is "print the per-row inked
intervals near the boundary and check whether any text row crosses it".

## Second real-world set (2026-10-08, Nature 2025, 16 panels)

`regions_nature2025_9573.json` + `cleanup_nature2025_9573.json`: Fig.1 / Fig.2 / Fig.6 of Nature 2025
(Springer `41586_2025_9573`). The source plates are Springer MediaObjects `*_HTML.webp`
(**read as WebP directly, no format conversion needed**), 16 panels in total; Fig.6 among them uses a
staggered layout — "left column a/b/d + right column c/e, with the row bands of the two columns not
coinciding" — so looking for row bands across the whole plate is bound to fail; the row bands can only
be determined per column block first.

```bash
python scripts/crop_panels.py --src <source plate directory> --out <output directory> \
  --spec examples/regions_nature2025_9573.json \
  --cleanup examples/cleanup_nature2025_9573.json
```

This set yielded two criteria (already written into step 5, §2 and the self-check list of `SKILL.md`):

1. **Outer ink > 0 ⇒ you must go back and check the inner side of the same edge.** When
   `audit_crops.py` reported 80 on the outer left of n1e, 553 on the outer top of n6d and 170 on the
   outer right of n1d, I initially put them all down as "the price of a staggered layout" and let them
   pass — the result being that n1e kept an isolated `a` in its lower-left corner (the trailing letter
   of the legend `Dementia` of neighbouring panel d), and n6d kept a half-cut axis label at its top
   (the `log2[FC] (ageing)` of neighbouring panel b, measured y1812–1833, while the top edge of the
   box had been set at y1830). **The larger the number, the more you must check.**
2. **Set the dividing line by the maximum extent of all elements of the neighbouring panel, not by
   the single one you happened to measure.** The d/e boundary was originally set at x1398, on the
   grounds that "e's annotation starts at 1398", without checking that d's legend measures out to
   **x1404** — those 7 px were enough to cause trouble. The correct approach: measure the endpoints of
   **every element adjacent on both sides of the dividing line** (axis title / legend / annotation /
   rotated label / bar end / panel letter), take the extremes and then place the line. When the
   elements on the two sides **overlap in x only and not in y**, a single vertical line cannot
   separate them, so "each side erases its own": put the line on the side that preserves your own
   elements, and let each side white out the few px that the other has bled in.

(The intermediate products and the report for this set remain in the workspace, under the
`multipanel-figure-cropping` skill-verification directory, in the `C_nature_2025_9573` subdirectory.)

## About the source plates: why there are no images in examples

This directory **holds coordinate specs only, not the source plates**. Two reasons: journal figures
are copyrighted (the Nat Commun set is CC BY, the Nature set may not be), and the skill does not
redistribute images; also, coordinate specs are only a few hundred bytes to a few KB, whereas source
plates are tens of MB.

The `--src` of `crop_panels.py --src <source plate directory>` means **the directory where you
yourself put the source plates**; the **top-level keys of `regions_*.json` are the filenames**, and
they must match the filenames in that directory word for word:

```
<source plate directory>/
  source_fig1.png … source_fig5.png          # the first sample set uses these 5 names
  nat2025_9573_fig1.webp … fig2 / fig6       # the second sample set uses these 3 names
```

Both sets of source plates are the official Springer Nature MediaObjects versions: open the article's
figure page → right-click that image → "Copy image address"; the URL looks like
`https://media.springernature.com/full/springer-static/image/art%3A10.1038%2F<DOI>/MediaObjects/<ID>_Fig<N>_HTML.png|webp`.
When the filenames do not match, **either rename the files or change the JSON keys**; the two must
agree.

**Key prerequisite: the coordinates are hard-bound to that one specific file.** Re-encode the same
figure at another resolution or in another format (PNG ↔ WebP ↔ JPEG) and the pixels no longer line
up, so the spec must be measured again. When you obtain a source plate, check the pixel dimensions
first:

| Sample set | Source plate | Dimensions |
|---|---|---|
| First set (Nat Commun 17:6975 Fig.1–5) | `source_fig1..5.png` | 1983×2130 / 2000×1957 / 2000×1656 / 2001×1461 / 1974×1285 |
| Second set (Nature `41586_2025_9573` Fig.1/2/6) | `nat2025_9573_fig1/2/6.webp` | 2176×2038 / 2168×2620 / 2146×2623 |

If the dimensions are wrong, do not use this set of coordinates. What the spec stores are **loose
regions**, and `tight_bbox` tightens them again to the actual ink, so a drift of a dozen-odd pixels is
tolerable, but **scaling is not**.

In other words: what `examples/` delivers is **the measurement result of "what this figure's layout
looks like and where the traps are"**, while the source plates are supplied by the user — which is
also why the same JSON can reproduce, on your machine, results byte-identical to the documentation in
a single run.

## Known trade-offs that rectangles cannot resolve

`fig5g`: the legend text of panel g (`CM cell line specific` and so on) and the vertical y-axis label
of panel h **genuinely overlap over x 1304–1330**, and their y rows interleave as well. Any rectangle
will cut off one of them. The value chosen in this sample: keep g's legend text, and let the right
edge carry a thin sliver of h's label strokes (**no white-out**, because whiting out would cut off g's
own trailing letters at the same time). Conflicts of this kind must be listed separately in the
report, together with the direction of the trade-off.
