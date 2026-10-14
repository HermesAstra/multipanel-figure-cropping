#!/usr/bin/env bash
# Reproduce the second sample set of 2026-10-08: Nature 2025 (Springer 41586_2025_9573) Fig.1/2/6, 16 panels (no union crops).
# Source plates (placed under <source plate directory>; the filenames must match the top-level keys of regions_nature2025_9573.json word for word):
#   nat2025_9573_fig1.webp  2176x2038
#   nat2025_9573_fig2.webp  2168x2620
#   nat2025_9573_fig6.webp  2146x2623
# Usage: bash run_example_nature2025.sh <source plate directory> <output directory>
set -euo pipefail
SRC="${1:?Usage: bash run_example_nature2025.sh <source plate directory> <output directory>}"
OUT="${2:?Usage: bash run_example_nature2025.sh <source plate directory> <output directory>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

python "$HERE/../scripts/crop_panels.py" \
  --src "$SRC" --out "$OUT" \
  --spec "$HERE/regions_nature2025_9573.json" \
  --cleanup "$HERE/cleanup_nature2025_9573.json"

python "$HERE/../scripts/audit_crops.py" --src "$SRC" --out "$OUT"
echo
echo "Expected for this set: 16 colour PNGs, 5 white-outs (none forced), 0 grayscale outputs."
echo "Reminder 1: audit is only a first-pass audit; you must still inspect every image one by one as verification (letters / stray fragments / truncation / colour)."
echo "Reminder 2: when the outer ink > 0 you must go back and check the inner side of the same edge -- see step 5 of SKILL.md and examples/README.md."

# Cleanup: remove the compiled cache in the scripts directory (it should stay clean before distribution/archiving)
rm -rf "$HERE/../scripts/__pycache__"
