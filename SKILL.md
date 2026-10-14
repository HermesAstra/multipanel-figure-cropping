---
name: multipanel-figure-cropping
description: >
  Measure and crop individual panels out of multi-panel journal figures
  (Nature/Cell/Science-style composite plates) into separate colour images,
  with per-panel pixel rectangles, normalised coordinates and a verification
  report. Use when the user asks to split a composite figure, cut panels
  a/b/c out of a plate, find the panel rectangles of source_figN.png, build
  slide-ready panel images from a paper figure, locate the "a/b/c" panel
  letters, or verify that a panel crop is not cutting labels or bleeding into
  its neighbours. Also use when a previous crop run produced grayscale or
  mis-bounded panels and needs an audit or repair.
---

# Multi-panel plate: panel location and cropping (multipanel-figure-cropping)

Cut every panel (panel a / b / c …) out of a journal composite plate **pixel-exactly**, producing colour
panel images, a pixel-rectangle table, normalised coordinates and a per-image verification record.

Applies to: plates such as `source_fig*.png` that hold several panels a–q in a single image; and to any task
that needs "split one large image into blocks along blank bands, and prove nothing was cut wrong".

---

## 0. Three hard rules (breaking any one of them ships a dud)

### Hard rule 1 — **measure in grayscale, write to disk in colour**

This is the easiest mistake to make with this skill, and the one with the worst consequences:

```python
gray = np.asarray(Image.open(p).convert("L"))   # projections / bbox / letter finding only
rgb  = np.asarray(Image.open(p).convert("RGB")) # the only data source allowed to be written
...
Image.fromarray(rgb[y0:y1, x0:x1]).save(out)    # ✅
Image.fromarray(gray[y0:y1, x0:x1]).save(out)   # ❌ ships a grayscale product
```

Grayscale does not affect geometric location, so **the geometry is entirely correct and the colour is entirely
gone**; if all you check when looking at an image is "is the letter there, is the boundary right", you will
never catch it. Journal figures almost always carry colour heatmaps, colour annotation bars and colour UMAP
clusters — the product must be colour.

- After writing to disk you **must** run a machine assertion: `panelkit.is_grayscale(crop) and not is_grayscale(master)`
  → raise immediately. `crop_panels.py` has this assertion built in.
- When inspecting each image with `read_image`, besides letters/boundaries you **must check colour on purpose**:
  is the heatmap red? do the annotation bars have colour? If the whole image looks grey, go back and check the
  write-out path at once.

### Hard rule 2 — composite plates usually have **no** blank band spanning the whole plate

Staggered layouts (left column a/b stacked, right column c/d stacked, e spanning the bottom; or three columns
over several rows) make "find the separators from whole-image row/column projections" fail outright: the
projection curve is non-zero everywhere.

The correct approach is **layering**:

```
whole-image row bands (contiguous bands where the row projection ≈ 0)
  └─ column blocks inside a row band (contiguous bands where the column projection ≈ 0)
       └─ split rows again inside a column block (panels stacked vertically in the same column)
            └─ tighten each block to the tight bbox of that block's actual ink
```

If no fully empty band exists at a given level, fall back to "the position with the least ink inside the
window" (`best_x` / `best_y`).

### Hard rule 3 — separator bands are often **not** zero-ink

Anti-aliasing, figure-level dashed connector lines and pale grey magnification wedges all leave stray pixels.
Use a **tolerance** rather than demanding exactly 0:

- Start with `maxink = 0`; if that yields nothing, relax progressively to 2 / 5 / 15 / 40, and **record which
  tolerance you used**.
- Criterion: the ink count per column inside that band must be far below the neighbouring content columns
  (e.g. ≤ 5% of the neighbour), not "exactly 0".

---

## 1. Workflow

### Step 0: preparation

```bash
mkdir <work>            # temporary scripts, probe images and candidate crops all go here
```
Only `numpy` + `PIL` are required (**no scipy / OpenCV / scikit-image**; see the FAQ at the end).

### Step 1: layout probe

```bash
python scripts/layout_probe.py --img <source plate> --ytol 0 15 40 --xtol 0 30 --bar
```

- Look at the whole-image row separator bands first; then at the column separator bands inside a given row band.
- `--bar` prints an ASCII bar chart of row/column ink — the most direct way to find separator bands: one run
  shows you "which columns are empty" and "which stretch is a dashed connector line".
- Repeat for each row band: `--y0 A --y1 B --xtol 0 30 60`.

### Step 2: locate the panel letters (the strongest evidence)

```bash
python scripts/layout_probe.py --img <source plate> --box <x0> <y0> <x1> <y1> --letters
```

- A panel letter = an isolated, bold, dark, high-density (dens ≥ 0.45) lowercase letter, roughly 19–40 px tall.
- **Pitfall: `i` / `j` / `l` are narrow glyphs (4–15 px wide)**. If you set the width lower bound to 12–15 they
  are silently missed, and you then wrongly conclude "this panel has no letter".
  → always set the `wrange` lower bound to **4**; when in doubt, crop a suspicious corner at 5–6× magnification
  and confirm with `read_image`.
- Letter position directly decides panel membership and boundary membership ("cut to the left or to the right
  of the letter").
- **When a whole-image scan is too noisy, search inside the narrow strip at the top of the row band instead**:
  measured on 2026-10-08, the panel letters of one Nature plate were only **18×18 px**, while the dot plots
  contained many solid squares with `dens=1.00` that get scored as candidates — a whole-image scan drowns in
  false positives. First fix the row bands / column blocks, then search only inside the small patch at each
  panel's top-left corner; that locks it in one pass.

### Step 3: write out the rectangles

Write each panel's **loose region** into `regions.json` (the script does the tightening to the tight bbox):

```json
{
  "source_fig1.png": {
    "fig1a":     [0, 0, 1176, 356],
    "fig1e_rna": [0, 1510, 898, 2130]
  }
}
```

- Regions may carry slack between them (the tight bbox removes the blank space).
- Naming convention: `fig<plate number><panel letter>`, letter lowercase; when one panel splits into two
  physical blocks use a suffix such as `fig1e_rna` / `fig1e_atac`.

### Step 4: crop (in colour)

```bash
python scripts/crop_panels.py --src <source plate dir> --out <output dir> --spec regions.json
```

Output: colour PNGs + `_rects.json` (holding rect / normalised coordinates / source region / white-out
records). The "the product is not grayscale" assertion is built in.

### Step 5: automatic audit (**does not replace looking at the images**)

```bash
python scripts/audit_crops.py --src <source plate dir> --out <output dir>
```

Reports per panel: whether the colour passes, the **letter candidates detected in the top-left inside the
frame**, and the ink amount in the **8 px outside** each of the four edges.

**Outside ink > 0 ⇒ you must go back and check the inside of that same edge** (a lesson bought with two real
misses on 2026-10-08): ink outside means "the neighbour's material crossed the dividing line you chose", and it
usually **crossed into your frame as well**, showing up as an isolated letter in a corner, half an axis label,
or the tail of a legend. The larger the number, the more you must look (anything from a few tens of px upwards
has to be inspected). Writing it off as an "acceptable trade-off" is the easiest miss in this skill right now —
two measured cases: `n1e` had 80 outside on the left (inside: an isolated `a` in the bottom-left corner) and
`n6d` had 553 outside on top (inside: a neighbouring panel's axis label cut in half along the top edge).

### Step 6: inspect every cropped image one by one (**mandatory, no sampling**)

Open **every** cropped image with an image viewer and confirm three things:

1. **its own panel letter (a/b/c…) is visible** — the strongest evidence;
2. **no neighbouring panel's letters or obvious stray fragments** (someone else's y-axis title, someone else's
   legend, someone else's cell-line names);
3. **no axis labels, tick numbers or title text cut off around the edges**;
4. **(added by this skill) the colour is correct** — heatmaps / annotation bars / clusters match the source plate.

If any one fails → adjust the rectangle → re-crop → **look again**; never declare success from the numbers alone.

### Step 7: write the report

Group by source plate; for each panel give: the raw rectangle `x0 y0 x1 y1`, the normalised
`(x0/W, y0/H, x1/W, y1/H)`, the size, the row-band / column-block it came from, and a one-line verification
record (**which letter you actually saw** + whether there are stray fragments or truncation).
List every "trade-off cost" in its own section; list the "panels that could not be done" honestly.

---

## 2. Boundary conflicts: the inherent contradiction of staggered layouts

The **rectangles of a composite plate interleave**: the ink of two neighbouring panels overlaps on some axis,
for example

- a long legend text of the left panel reaching right into the right panel's column (`fig1b`'s cell-line name
  reaches x≈1167, while the right panel's UMAP cluster starts as far left as x≈1140);
- a rotated label of the upper panel reaching down into the lower panel's row (`fig4c/d`'s `program11` /
  `AM vs CM patients cohort` reach y≈659, while the next row of panels starts at y≈650);
- a narrow glyph letter sitting right against the neighbouring panel's text (`fig3j`'s letter at x955,
  `fig3i`'s "Mesenchymal" extending to x979).

**A rectangular crop cannot simultaneously satisfy "don't cut myself" and "don't include the neighbour".**
The uniform trade-off principle:

> **Protect the panel letter and the axis labels first** (criteria 1 and 3),
> and only then avoid neighbouring-panel fragments (criterion 2); every trade-off must be written into the
> report with the source-plate coordinates and the cost.

Common acceptable costs: a 5–15 px wide stroke fragment of a neighbouring panel at the edge, figure-level
dashed connector lines, grey magnification wedges.
Common unacceptable costs: cutting off your own panel letter, cutting off an axis title, framing the
neighbouring panel's **letter**.

**Fix the dividing line from "the maximum extent of every element of the neighbouring panel", not from the one
element you happened to measure.** A measured lesson (2026-10-08, a Nature 2025 plate): the d/e divide was put
at x1398 on the grounds that "e's annotation starts at 1398", without checking that d's legend `Dementia`
actually reaches **x1404** — the extra 7 px landed inside e's frame and became an isolated `a` in the
bottom-left corner. The correct order: measure the endpoints of **every adjacent element on both sides** of
the line (axis titles, legends, annotations, rotated labels, bar/segment ends, panel letters), take the extreme
values on both sides, and only then drop the line into the blank space between them.
When the elements on the two sides **overlap in x but not in y**, a single vertical line cannot separate them —
switch to "white out each side separately": put the line on the side that preserves your own element, then
white out the few px by which the other side bleeds in on each side
(the two sides do not overlap in y, so they do not interfere; this kind of white-out is usually only a few tens
of px with density < 0.15, and passes the gate comfortably).

If the user demands "zero stray fragments", you may optionally do the **documented white-out cleanup** (next
section).

### 2.1 White-out cleanup (`--cleanup`): the only permitted manual pixel edit

White-out = set the rectangle holding fragments already confirmed to belong to a **neighbouring panel** to
255. It is "erasing someone else's material", not "erasing your own", and therefore has three hard rules:

1. **Measure first, white out second.** The white-out rectangle must land where the image was already close to
   blank. `crop_panels.py` has a **two-level gate** built in:
   - ink density ≤ `--cleanup-soft-density` (default **0.30**) → white out directly, leaving a record;
   - soft threshold < density ≤ `--cleanup-hard-density` (default **0.60**) → requires
     `--cleanup-ack "<reason>"` before it goes through, and the reason is written into `_rects.json`;
   - density > the hard ceiling → refused outright (almost certainly a content block); if you really must erase
     it, add `--force-cleanup`.

   Why the soft threshold is 0.30 and not lower: **a text-fragment area naturally has an ink density of
   0.05–0.20**. A measured lesson: the threshold was first set to 0.12 and fig1d's normal text fragment
   (density 0.127) was wrongly blocked; conversely, setting the threshold even lower cannot protect you from
   judgement errors other than "erasing a whole heatmap" — the criterion has to work together with the vetted
   channel below.
2. **Edge white-out computed by the tool goes through the vetted channel.** The narrow bands produced by
   `auto_edge_cleanup.py` from the "guard band" criterion **sit right against ink**, with a natural density as
   high as 0.4–0.9, so density cannot be used to gate them. `cleanup.json` entries therefore support two
   forms:

   ```json
   {
     "fig1c": [[1140, 0, 1206, 216]],
     "fig5hi": {"rects": [[1304, 963, 1312, 976]],
                "vetted_by": "auto_edge_cleanup",
                "reason": "union left seam: only whites out the tail of g's legend; h's vertical label is avoided by the guard band"}
   }
   ```

   A bare list = a hand-written rectangle → goes through the density gate; a dict with `vetted_by` = already
   verified by the tool → gate waived, but the **source and the reason must be recorded** (they are written
   into `_rects.json`).

3. **Everything must leave a record.** Every white-out (coordinates / how much ink was erased / density /
   whether it was forced / the verification source) is written into the `cleaned` field of `_rects.json`, and
   `audit_crops.py` prints them one by one. The delivered report must carry a matching "white-out record"
   section; if the two do not match, pixels were changed silently, which is not allowed.
4. **Never white out to make things look nicer.** White-out only solves "a neighbour's fragment pressing into
   a blank corner"; it cannot solve "you cut through your own axis title" — that has to be fixed by changing or
   widening the rectangle (see the trade-off principle in §2).

Measured example (2026-10-06, five plates from Nature Communications 17:6975):

```json
{
  "fig1c": [[1140, 0, 1206, 216]],        // erase panel a's header / the tail of panel b's legend (rotated fragment)
  "fig1d": [[1128, 757, 1196, 832]],      // erase the tail of panel b's legend "1833, 1834,"
  "fig2i": [[405, 1647, 1338, 1664]],     // erase the rotated cell-line-name footnote of panel h above
  "fig3i": [[948, 679, 985, 716]]         // after widening the rectangle to keep "Mesenchymal", erase the neighbouring panel's letter j in the corner
}
```

Note the difference in the last two: `fig1c` / `fig1d` / `fig2i` are "the rectangle is right, there is a
fragment in the corner"; `fig3i` is "the rectangle was widened so as not to cut off my own text, the widening
framed the neighbouring panel's letter, and then it was erased" — the latter is a common combination, and the
report **must state the order "widen first, white out second" and the reason for it**.

### 2.2 Union cropping (`--merge`): when the layout needs "several adjacent blocks as one image"

Slides very often need "c and d on the same image". Do **not** stitch two PNGs by hand (the scales do not
match, the provenance is opaque); use:

```bash
python scripts/crop_panels.py --src <source plate dir> --out <output dir> \
  --spec regions.json --cleanup cleanup.json \
  --merge "fig4cd=fig4c+fig4d" --merge "fig4jk=fig4j+fig4k" --merge "fig5hi=fig5h+fig5i+fig5j"
```

It takes the **union of the constituent panels' tight bboxes**, crops that union from the **colour source
plate**, and records `merged_from` in `_rects.json`. White-out on the union image also goes through
`--cleanup` (keyed by the union image name, e.g. `{"fig5hi": [[1304, 780, 1312, 1250]]}` — erasing the tail of
a neighbouring panel's text pulled in at the left edge).

**The unavoidable cost of a union image**: a union means "the seam between the two panels is included as well",
and the seam may hold a neighbour's text, so a union image almost always needs one left/right edge white-out;
remember to account for it in the report.

**Edge white-out must be computed with the guard-band criterion, not by "white out every row of the edge that
has ink"**: use `auto_edge_cleanup.py` — a row is judged a neighbouring-panel fragment only when
`[edge, edge+w)` has ink **and** the immediately adjacent `[edge+w, edge+w+gap)` has **no ink**. A measured
lesson: the ink at the left edge of fig4cd runs continuously to the right — it is the panel's own rotated axis
label — so "white out the whole edge" **wrongly deleted 114 px of its own content**; with the guard-band
criterion fig4cd / fig4jk should white out 0 segments, and fig5hi needs only 7 narrow bands (266 px) instead of
the whole edge (876 px).


---

## 3. Output and naming

```
<out>/
  fig1a.png  fig1b.png  ...  fig1e_rna.png  fig1e_atac.png
  fig4cd.png            # union image (produced by --merge), named the same way: plate number + letter string
  _rects.json          # {panel name: {source, rect, w, h, norm, region, cleaned, merged_from}}
  crop_report.md        # see step 7
```

Report template:

```markdown
# <plate set name> composite-plate crop report

## 0. Overall layering
| source plate | size | whole-image row separator bands | row bands |

## 1..N. <source plate>
| file | raw rectangle | normalised | size | source (row band / column block) |
**Verification record** (one line per panel: the letter seen / stray fragments / truncation)

## Boundary conflicts and trade-offs
| position | conflict | my trade-off |

## Unfinished / open questions
```

---

## 4. Self-check list (tick every line before delivering)

- [ ] every output PNG is **colour** (`audit_crops.py` reports "grayscale products: 0")
- [ ] every panel's rectangle is the **tight** bbox of that panel's ink (no large blank areas)
- [ ] **every single one** was inspected image by image, and its own panel letter was seen in each
- [ ] not one of them cut off its own axis labels / ticks / title
- [ ] every edge flagged **`<< re-check the inside`** by `audit_crops.py` was **looked at again, and the inside of
      that same edge confirmed free of neighbouring fragments**, before any explanation was written
- [ ] narrow glyphs such as `i` / `j` / `l` were **specifically checked at magnification** (whether present or
      absent, there must be a conclusion)
- [ ] **every white-out** reported by `audit_crops.py` matches a line in the report's "white-out record", and
      none of them was silently forced after exceeding the density limit
- [ ] union images (produced by `--merge`) state in the report which panels they consist of and what was
      erased in the seam
- [ ] the report's "unfinished items" section is filled in honestly (better to leave things out than to fake
      success)
- [ ] the number of rectangles = the number of panels in the user's list; if the actual number of letters on
      the plate disagrees with the list (more or fewer), say so in a dedicated section of the report — do
      **not** quietly pad to match the list
- [ ] every dividing line was fixed from "the maximum extent of **all** elements of the neighbouring panel",
      not just from the one element that happened to be measured

---

## 5. Script inventory (`scripts/`)

| file | purpose |
|---|---|
| `panelkit.py` | toolbox: loading (dual grayscale/colour entry points), ink mask, row/column separator bands, tight bbox, optimal cut line, connected-component letter detection, ASCII bar chart, grid overlay |
| `layout_probe.py` | layout probe: row/column separator bands (multiple tolerances) + ASCII bar chart + letter candidates |
| `crop_panels.py` | crop according to `regions.json` (colour write-out + grayscale assertion); `--cleanup` white-out cleanup (with density safety gate); `--merge` union cropping |
| `auto_edge_cleanup.py` | computes "which rows of an edge should be whited out": the **guard-band criterion** (only when the edge band has ink and the immediately adjacent guard band has none is it a neighbouring-panel fragment), avoiding deletion of this panel's own continuous strokes / vertical labels |
| `audit_crops.py` | automatic first-pass audit: colour, letter candidates inside the frame, ink outside each of the four edges, **white-out records printed one by one**, union provenance; when the outside ink of an edge is ≥ `--edge-warn` (default **50 px**) that line is flagged **`<< re-check the inside`** and summarised at the end — **anything flagged must be followed by looking at the inside of that same edge** |

## 5.1 Reusable measured examples (`examples/`)

| file | description |
|---|---|
| `examples/regions_fig1-5.json` | the 54 panel loose regions measured on 2026-10-06 (Fig.1–5 of Nature Commun. 17:6975) |
| `examples/cleanup_fig1-5.json` | the **11 white-outs actually performed**: 4 single-panel corners (bare lists, passing the gate) + 7 narrow bands along fig5hi's left seam (vetted channel); fig4cd / fig4jk measured 0 segments under the guard-band criterion (the left-edge ink belongs to their own content) |
| `examples/run_example.sh` | reproduces the whole crop with a single command (including unions and white-outs) |
| `examples/regions_nature2025_9573.json` | the second real example, 2026-10-08: Fig.1/2/6 of Nature 2025 (`41586_2025_9573`), **16 panels**, WebP source plates, **staggered layout** (Fig.6 has column a/b/d on the left and c/e on the right; the row bands of the two columns do not coincide) |
| `examples/cleanup_nature2025_9573.json` | the 5 white-outs of that set (density 0.05–0.26, none forced), corresponding to the two new criteria above |

Reproduce with a single command:

```bash
python scripts/crop_panels.py \
  --src <source plate dir> --out <output dir> \
  --spec examples/regions_fig1-5.json \
  --cleanup examples/cleanup_fig1-5.json \
  --merge "fig4cd=fig4c+fig4d" --merge "fig4jk=fig4j+fig4k" --merge "fig5hi=fig5h+fig5i+fig5j"
```

---

## 6. FAQ

**Q: do I need scipy?**
No. This skill only ever uses: array slicing, axis sums, `argwhere`, boolean masks, and a pure-Python BFS for
connected components — numpy + PIL is enough. The **only** conceivable uses of scipy here would be
`scipy.ndimage.label` (connected components), `binary_erosion/dilation` (morphological denoising) and
`find_objects`; all of them fall into the "a few dozen lines and you write it yourself" category, and the BFS
version is more readable and adds no dependency. What actually needs scipy is **scientific-computing** work
(sparse matrices, interpolation, optimisation, signal filtering, statistical tests), which has nothing to do
with "cutting images".

**Q: would `pyvips` / `OpenCV` be faster?**
For extremely large images (> 100 million pixels) `pyvips` has an advantage; at the scale of this task
(2000×2000) numpy is enough, and cropping is itself an O(pixels) slicing operation.

**Q: can I skip looking at the images and let a program decide "did the crop cut any text"?**
No, it cannot be decided reliably. A program can check "is there ink outside the rectangle"
(`audit_crops.py`), but whether that ink is a neighbouring panel's fragment or a corner cut off your own label
has to be judged by eye. Inspecting every image individually is a mandatory step of this skill.

**Q: what if the source plate is WebP / JPEG / TIFF?**
Use it directly. `panelkit.load_gray/load_rgb` go through PIL, which decodes these formats natively — **no need
to convert to PNG first**; the grayscale assertion, the white-out gate and union cropping all work as usual. On
2026-10-08 three Springer `*_HTML.webp` images with 16 panels passed without any difference.

**Q: running the scripts leaves a `scripts/__pycache__` behind — should I keep it?**
No. Delete it before copying / distributing / archiving this skill (`rm -rf scripts/__pycache__`);
`examples/run_example.sh` already cleans it up at the end.
