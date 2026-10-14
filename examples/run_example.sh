#!/usr/bin/env bash
# Reproduce the 2026-10-06 54-panel crop (including union crops and white-out cleanup)
# Usage: bash run_example.sh <source plate directory> <output directory>
set -euo pipefail
SRC="${1:?Usage: bash run_example.sh <source plate directory> <output directory>}"
OUT="${2:?Usage: bash run_example.sh <source plate directory> <output directory>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

python "$HERE/../scripts/crop_panels.py" \
  --src "$SRC" --out "$OUT" \
  --spec "$HERE/regions_fig1-5.json" \
  --cleanup "$HERE/cleanup_fig1-5.json" \
  --merge "fig4cd=fig4c+fig4d" \
  --merge "fig4jk=fig4j+fig4k" \
  --merge "fig5hi=fig5h+fig5i+fig5j"

python "$HERE/../scripts/audit_crops.py" --src "$SRC" --out "$OUT"
echo
echo "Reminder: audit is only a first-pass audit; you must still inspect every image one by one as verification (letters / stray fragments / truncation / colour)."

# Cleanup: remove the compiled cache in the scripts directory (it should stay clean before distribution/archiving)
rm -rf "$HERE/../scripts/__pycache__"
