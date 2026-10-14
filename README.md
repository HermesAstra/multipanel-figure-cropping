# multipanel-figure-cropping

Cut individual panels out of multi-panel journal figures (Nature / Cell / Science-style composite plates)
**pixel-exactly**, and prove the result: colour panel images, a pixel-rectangle table, normalised coordinates
and a per-image verification record.

Given a plate such as `source_fig1.png` that holds panels a–q, this skill measures each panel's rectangle,
crops it, and produces an auditable report — including which panel letter was seen in each crop, whether any
neighbouring panel's ink leaked in, and every pixel that was deliberately whited out.

```text
source_fig1.png  ──►  fig1a.png  fig1b.png  fig1c.png  …  fig1e_rna.png  fig1e_atac.png
                      _rects.json   (rect / normalised coords / source region / white-out records)
                      crop_report.md
```

- [SKILL.md](SKILL.md) — the full workflow, the three hard rules, the trade-off policy and the self-check list.
  This is the authoritative document; read it before running anything.
- `scripts/` — the tools (numpy + PIL only, no scipy / OpenCV / scikit-image).
- `examples/` — two fully worked, measured examples you can reproduce with one command.

## Why it exists

Generic "split the image on blank rows" code fails on real journal plates, and fails silently — it returns
plausible-looking crops that are wrong. The rules in [SKILL.md](SKILL.md) were each bought with a real mistake:

| Trap | What goes wrong | What this tool does |
| --- | --- | --- |
| Measuring in grayscale and writing grayscale | geometry perfect, all colour gone — invisible unless you look at colour on purpose | assertion at write-out: crop grayscale while the plate is colour → hard error |
| Assuming a blank band spans the whole plate | staggered layouts have non-zero projections everywhere | layered search: whole-image row bands → column blocks → rows within a block → tight bbox |
| Demanding zero ink in the separator | anti-aliasing, dashed connectors and grey wedges leave stray pixels | tolerance ladder (0 → 2 → 5 → 15 → 40) with the used tolerance recorded |
| Narrow glyphs `i` / `j` / `l` | width lower bound of 12–15 px silently drops them, so a panel "has no letter" | width lower bound 4 px; suspicious corners checked at 5–6× |
| Neighbour ink outside the frame | the same material usually crossed *into* the frame too (stray letter, half label) | `audit_crops.py` flags edges by outside-ink amount; flagged edges must be checked inside |
| Whiting out edges wholesale | deletes the panel's own rotated axis label (measured: 114 px lost) | guard-band criterion: ink in the edge band *and* no ink in the adjacent band |
| Hand-stitching panels for slides | mismatched scale, opaque provenance | `--merge` union crops taken from the colour plate, with `merged_from` recorded |

## Requirements

- Python 3.8+
- `numpy`, `Pillow` (PIL)

No scipy, no OpenCV, no scikit-image, and no need to convert WebP / JPEG / TIFF plates to PNG first.

## Install as a skill

Copy this directory into your skills folder, keeping the directory name:

```bash
# DeepSeek Harness
cp -r multipanel-figure-cropping ~/.dsh/skills/

# Claude-style skill folders
cp -r multipanel-figure-cropping ~/.claude/skills/
```

`SKILL.md` carries the frontmatter (`name`, `description`) the skill loaders expect. The scripts can also be
used standalone, without any skill host.

## Quick start

```bash
# 1. probe the layout: row/column separator bands + ASCII ink bar chart
python scripts/layout_probe.py --img source_fig1.png --ytol 0 15 40 --xtol 0 30 --bar

# 2. locate panel letters inside a candidate box
python scripts/layout_probe.py --img source_fig1.png --box 0 0 1176 356 --letters

# 3. crop in colour from a regions.json spec
python scripts/crop_panels.py --src <plate dir> --out <output dir> --spec regions.json

# 4. first-pass audit (colour, letter candidates, outside ink) — does not replace looking at the images
python scripts/audit_crops.py --src <plate dir> --out <output dir>
```

Reproduce a full measured example, including union crops and white-out cleanup:

```bash
bash examples/run_example.sh <plate dir> <output dir>
bash examples/run_example_nature2025.sh <plate dir> <output dir>
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Skill definition and workflow — the authoritative documentation |
| `scripts/` | `panelkit.py` (library), `layout_probe.py`, `crop_panels.py`, `auto_edge_cleanup.py`, `audit_crops.py` |
| `examples/` | Region specs, white-out specs, shell scripts and notes from two real projects |
| `output/` | Where crops land when you run the examples; **not tracked by git** |

## Outputs

- colour PNG per panel (`fig1a.png`, …), plus union images (`fig4cd.png`) when `--merge` is used
- `_rects.json`: for every panel the source plate, raw rect, width/height, normalised coordinates, source
  region, white-out records and union provenance
- `crop_report.md`: the delivered report, in the structure given by step 7 of [SKILL.md](SKILL.md)

## Limits (read these)

- **A program cannot decide whether a crop cut text.** `audit_crops.py` reports ink outside each edge; whether
  that ink is a neighbour's fragment or a corner of your own label must be judged by eye. Inspecting every
  cropped image individually is a mandatory step, and this skill does not pretend otherwise.
- Rectangular crops cannot simultaneously avoid cutting your own content and avoid including a neighbour's.
  The policy is explicit: protect the panel letter and axis labels first, then minimise neighbour fragments,
  and write every trade-off into the report.
- Single-panel rectangles are expected; panels that are split across two physical blocks are named with a
  suffix (`fig1e_rna` / `fig1e_atac`) rather than fused automatically.

## Examples included

| File | What it is |
| --- | --- |
| `examples/regions_fig1-5.json` | 54 panel regions measured on a Nature Communications 17:6975 plate set (Fig.1–5) |
| `examples/cleanup_fig1-5.json` | The 11 white-outs actually performed on that set (4 corners + 7 narrow bands along a union seam) |
| `examples/run_example.sh` | One-command reproduction of the above, including three union crops |
| `examples/regions_nature2025_9573.json` | 16 panels from Nature 2025 (`41586_2025_9573`) Fig.1/2/6 — WebP plates with a staggered layout |
| `examples/cleanup_nature2025_9573.json` | The 5 white-outs of that set |
| `examples/run_example_nature2025.sh` | One-command reproduction of the second set |

The example specs reference the source plates by file name only; the plates themselves are not redistributed
here. See [examples/README.md](examples/README.md) for the expected file names and sizes.
